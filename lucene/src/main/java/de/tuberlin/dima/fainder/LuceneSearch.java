package de.tuberlin.dima.fainder;

import org.apache.lucene.analysis.CharArraySet;
import org.apache.lucene.analysis.standard.StandardAnalyzer;
import org.apache.lucene.document.Document;
import org.apache.lucene.index.DirectoryReader;
import org.apache.lucene.index.IndexReader;
import org.apache.lucene.index.StoredFields;
import org.apache.lucene.index.Term;
import org.apache.lucene.queryparser.classic.ParseException;
import org.apache.lucene.queryparser.classic.QueryParser;
import org.apache.lucene.search.*;
import org.apache.lucene.store.Directory;
import org.apache.lucene.store.FSDirectory;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.apache.lucene.search.highlight.*;

import java.io.IOException;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.HashMap;

public class LuceneSearch {
    private static final Logger logger = LoggerFactory.getLogger(LuceneSearch.class);
    private final IndexSearcher searcher;
    private final Map<String, Float> searchFields = Map.of(
        "name", 2.0f,           // Boost name matches
        "description", 1.0f,    // Normal weight for description
        "keywords", 1.5f,       // Slightly boost keyword matches
        "creator_name", 0.8f,   // Lower weight for creator
        "publisher_name", 0.8f, // Lower weight for publisher
        "alternateName", 0.5f   // Lowest weight for alternate names
    );
    private final QueryParser[] fieldParsers;
    private final StandardAnalyzer analyzer;

    // Constant flag for testing different implementations
    private final Boolean BOOL_FILTER;

    private static final float MIN_BOOST = 0.1f;
    private static final float EXACT_MATCH_MULTIPLIER = 2.0f;
    private static final float PREFIX_MATCH_MULTIPLIER = 0.5f;

    public LuceneSearch(Path indexPath) throws IOException {
        Directory indexDir = FSDirectory.open(indexPath);
        IndexReader reader = DirectoryReader.open(indexDir);
        searcher = new IndexSearcher(reader);
        // Configure analyzer to keep stop words
        analyzer = new StandardAnalyzer(CharArraySet.EMPTY_SET);

        // Create a parser for each field
        fieldParsers = searchFields.entrySet().stream()
            .map(entry -> {
                QueryParser parser = new QueryParser(entry.getKey(), analyzer);
                parser.setDefaultOperator(QueryParser.Operator.OR);
                return parser;
            })
            .toArray(QueryParser[]::new);

        BOOL_FILTER = false;
    }

    private Query createMultiFieldQuery(String queryText) throws ParseException {
        BooleanQuery.Builder queryBuilder = new BooleanQuery.Builder();
        String escapedQuery = QueryParser.escape(queryText);

        int i = 0;
        for (Map.Entry<String, Float> field : searchFields.entrySet()) {
            // Base boost - ensure it's positive
            Float baseBoost = Math.max(MIN_BOOST, field.getValue());
            QueryParser parser = fieldParsers[i++];

            // Calculate derived boosts, ensuring they remain positive
            float exactBoost = baseBoost * EXACT_MATCH_MULTIPLIER;
            float fuzzyBoost = baseBoost;
            float prefixBoost = Math.max(MIN_BOOST, baseBoost * PREFIX_MATCH_MULTIPLIER);

            // Exact match (highest boost)
            Query exactQuery = parser.parse("(" + escapedQuery + ")^" + exactBoost);
            queryBuilder.add(exactQuery, BooleanClause.Occur.SHOULD);

            // Fuzzy match for typos
            Query fuzzyQuery = parser.parse("(" + escapedQuery + "~)^" + fuzzyBoost);
            queryBuilder.add(fuzzyQuery, BooleanClause.Occur.SHOULD);

            // Prefix match for partial words
            Query prefixQuery = parser.parse("(" + escapedQuery + "*)^" + prefixBoost);
            queryBuilder.add(prefixQuery, BooleanClause.Occur.SHOULD);
        }

        return queryBuilder.build();
    }

    private Query createHighlightQuery(String queryText) throws ParseException {
        BooleanQuery.Builder queryBuilder = new BooleanQuery.Builder();
        String escapedQuery = QueryParser.escape(queryText);

        for (Map.Entry<String, Float> field : searchFields.entrySet()) {
            QueryParser parser = new QueryParser(field.getKey(), analyzer);
            parser.setDefaultOperator(QueryParser.Operator.OR);

            // Add exact match
            Query exactQuery = parser.parse(escapedQuery);
            queryBuilder.add(exactQuery, BooleanClause.Occur.SHOULD);

        }
        return queryBuilder.build();
    }

    public static class SearchResult {
        public List<Integer> docIds;
        public List<Float> scores;
        public Map<Integer, Map<String, String>> highlights;  // Changed to Map<Integer, Map<String, String>>

        public SearchResult(List<Integer> docIds, List<Float> scores, Map<Integer, Map<String, String>> highlights) {
            this.docIds = docIds;
            this.scores = scores;
            this.highlights = highlights;
        }
    }

    /**
     * @param query      The query string
     * @param docIds     Set of document IDs to filter (optional)
     * @param minScore   The minimum score for a document to be included in the results
     * @param maxResults The maximum number of documents to return
     * @param enableHighlighting Flag to enable or disable highlighting
     * @return A pair of lists: document IDs and their scores
     */
    public SearchResult search(String query, Set<Integer> docIds, Float minScore, int maxResults, boolean enableHighlighting) {
        if (query == null || query.isEmpty()) {
            return new SearchResult(List.of(), List.of(), Map.of());
        }

        try {
            Query multiFieldQuery = createMultiFieldQuery(query);
            Highlighter highlighter = null;

            if (enableHighlighting) {
                Query highlightQuery = createHighlightQuery(query);
                QueryScorer scorer = new QueryScorer(highlightQuery);
                SimpleHTMLFormatter htmlFormatter = new SimpleHTMLFormatter("<mark>", "</mark>");
                highlighter = new Highlighter(htmlFormatter, scorer);
                highlighter.setMaxDocCharsToAnalyze(Integer.MAX_VALUE);
            }

            logger.info("Executing query {}. With filter: {} ", multiFieldQuery, docIds);

            ScoreDoc[] hits = null;
            if (docIds != null && !docIds.isEmpty()) {
                // Create filter for allowed document IDs
                // TODO: Does the docFilter actually help to reduce query execution time?
                if (BOOL_FILTER) {
                    Query docFilter = createDocFilter(docIds);
                    BooleanQuery.Builder queryBuilder = new BooleanQuery.Builder();
                    queryBuilder.add(multiFieldQuery, BooleanClause.Occur.MUST);
                    queryBuilder.add(docFilter, BooleanClause.Occur.FILTER);
                    Query parsedQuery = queryBuilder.build();
                    hits = searcher.search(parsedQuery, maxResults).scoreDocs;
                } else {
                    CustomCollectorManager collectorManager = new CustomCollectorManager(maxResults, docIds);
                    hits = searcher.search(multiFieldQuery, collectorManager).scoreDocs;
                }
            } else {
                logger.info("No filter applied");
                hits = searcher.search(multiFieldQuery, maxResults).scoreDocs;
            }

            StoredFields storedFields = searcher.storedFields();
            List<Integer> results = new ArrayList<>();
            List<Float> scores = new ArrayList<>();
            Map<Integer, Map<String, String>> highlights = new HashMap<>();

            for (ScoreDoc scoreDoc : hits) {
                if (minScore != null && scoreDoc.score < minScore) continue;

                Document doc = storedFields.document(scoreDoc.doc);
                int resultId = Integer.parseInt(doc.get("id"));
                Map<String, String> docHighlights = new HashMap<>();

                if (enableHighlighting && highlighter != null) {
                    // Only process highlights if enabled
                    for (String fieldName : searchFields.keySet()) {
                        String fieldContent = doc.get(fieldName);
                        if (fieldContent != null && !fieldContent.isEmpty()) {
                            try {
                                String[] fragments = highlighter.getBestFragments(analyzer, fieldName, fieldContent, 1000);
                                String highlighted = String.join(" ... ", fragments);
                                if (highlighted != null && !highlighted.isEmpty()) {
                                    docHighlights.put(fieldName, highlighted);
                                }
                            } catch (InvalidTokenOffsetsException e) {
                                logger.warn("Failed to highlight field {}: {}", fieldName, e.getMessage());
                            }
                        }
                    }
                }
                // logger.info("Hit {}: {} (Score: {})", resultId, doc.get("name"), scoreDoc.score);
                results.add(resultId);
                scores.add(scoreDoc.score);
                if (!docHighlights.isEmpty()) {
                    highlights.put(resultId, docHighlights);
                }
            }

            return new SearchResult(results, scores, highlights);
        } catch (ParseException e) {
            logger.error("Query parsing error: {}", e.getMessage());
            e.printStackTrace();
            return new SearchResult(List.of(), List.of(), Map.of());

        } catch (IOException e) {
            logger.error("Query IO error: {}", e.getMessage());
            e.printStackTrace();
            return new SearchResult(List.of(), List.of(), Map.of());
        }
    }

    private Query createDocFilter(Set<Integer> docIds) {
        // TODO: Improve efficiency off this
        // just or TermQueries for id in filter
        BooleanQuery.Builder builder = new BooleanQuery.Builder();
        for (int docId : docIds) {
            builder.add(new TermQuery(new Term("id", String.valueOf(docId))), BooleanClause.Occur.SHOULD);
        }
        BooleanQuery.Builder filterQuery = new BooleanQuery.Builder();
        filterQuery.add(builder.build(), BooleanClause.Occur.MUST);
        return builder.build();
    }

    public void close() throws IOException {
        searcher.getIndexReader().close();
    }

}
