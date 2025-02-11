package de.tuberlin.dima.fainder;

import org.apache.lucene.analysis.CharArraySet;
import org.apache.lucene.analysis.standard.StandardAnalyzer;
import org.apache.lucene.document.Document;
import org.apache.lucene.index.DirectoryReader;
import org.apache.lucene.index.IndexReader;
import org.apache.lucene.index.StoredFields;
import org.apache.lucene.index.Term;
import org.apache.lucene.queryparser.classic.ParseException;
import org.apache.lucene.queryparser.flexible.core.QueryNodeException;
import org.apache.lucene.queryparser.flexible.standard.StandardQueryParser;
import org.apache.lucene.queryparser.flexible.standard.config.StandardQueryConfigHandler;
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
        "name", 5.0f,           // Boost name matches
        "description", 2.0f,    // Normal weight for description
        "keywords", 4.0f,       // Slightly boost keyword matches
        "creator_name", 1.6f,   // Lower weight for creator
        "publisher_name", 1.6f, // Lower weight for publisher
        "alternateName", 3.0f
    );
    private final StandardAnalyzer analyzer;
    private final StandardQueryParser qpHelper;


    // Constant flag for testing different implementations
    private final Boolean BOOL_FILTER;

    public LuceneSearch(Path indexPath) throws IOException {
        Directory indexDir = FSDirectory.open(indexPath);
        IndexReader reader = DirectoryReader.open(indexDir);
        BOOL_FILTER = false;
        searcher = new IndexSearcher(reader);
        // Configure analyzer to keep stop words
        analyzer = new StandardAnalyzer(CharArraySet.EMPTY_SET);

        qpHelper = new StandardQueryParser();
        StandardQueryConfigHandler config = (StandardQueryConfigHandler) qpHelper.getQueryConfigHandler();
        config.set(StandardQueryConfigHandler.ConfigurationKeys.ALLOW_LEADING_WILDCARD, true);
        config.set(StandardQueryConfigHandler.ConfigurationKeys.ANALYZER, analyzer);
        config.set(StandardQueryConfigHandler.ConfigurationKeys.FIELD_BOOST_MAP, searchFields);
        config.set(StandardQueryConfigHandler.ConfigurationKeys.MULTI_FIELDS, searchFields.keySet().toArray(new String[0]));
        config.set(StandardQueryConfigHandler.ConfigurationKeys.DEFAULT_OPERATOR, StandardQueryConfigHandler.Operator.AND);
        config.set(StandardQueryConfigHandler.ConfigurationKeys.MULTI_TERM_REWRITE_METHOD, MultiTermQuery.SCORING_BOOLEAN_REWRITE);
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

    private Query createMultiFieldQuery(String queryText) throws ParseException, QueryNodeException {

        Query query = qpHelper.parse(queryText, null);
        return new BoostQuery(query, 5.0f);  // Boost entire query by 5x
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
                QueryScorer scorer = new QueryScorer(multiFieldQuery);
                SimpleHTMLFormatter htmlFormatter = new SimpleHTMLFormatter("<mark>", "</mark>");
                highlighter = new Highlighter(htmlFormatter, scorer);
                highlighter.setMaxDocCharsToAnalyze(Integer.MAX_VALUE);
            }

            logger.info("Input query {}. Executing query {}. With filter: {} ", query, multiFieldQuery, docIds);

            ScoreDoc[] hits;
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
                hits = searcher.search(multiFieldQuery, maxResults).scoreDocs;
            }

            StoredFields storedFields = searcher.storedFields();
            List<Integer> results = new ArrayList<>();
            List<Float> scores = new ArrayList<>();
            Map<Integer, Map<String, String>> highlights = new HashMap<>();

            logger.info("Found {} hits", hits.length);

            for (ScoreDoc scoreDoc : hits) {
                Document doc = storedFields.document(scoreDoc.doc);
                int resultId = Integer.parseInt(doc.get("id"));
                // logger.info("Hit {}: {} (Score: {})", resultId, doc.get("name"), scoreDoc.score);
                if (minScore != null && scoreDoc.score < minScore) continue;

                Map<String, String> docHighlights = new HashMap<>();

                if (enableHighlighting) {
                    // Only process highlights if enabled
                    for (String fieldName : searchFields.keySet()) {
                        String fieldContent = doc.get(fieldName);
                        if (fieldContent != null && !fieldContent.isEmpty()) {
                            try {
                                String[] fragments = highlighter.getBestFragments(analyzer, fieldName, fieldContent, 1000);
                                String highlighted = String.join(" ... ", fragments);
                                if (!highlighted.isEmpty()) {
                                    docHighlights.put(fieldName, highlighted);
                                }
                            } catch (InvalidTokenOffsetsException e) {
                                logger.warn("Failed to highlight field {}: {}", fieldName, e.getMessage());
                            }
                        }
                    }
                }
                results.add(resultId);
                scores.add(scoreDoc.score);
                if (!docHighlights.isEmpty()) {
                    highlights.put(resultId, docHighlights);
                }
            }
            logger.info("Returning {} results over min Score {}", results.size(), minScore);

            return new SearchResult(results, scores, highlights);
        } catch (ParseException e) {
            logger.error("Query parsing error: {}", e.getMessage());
            return new SearchResult(List.of(), List.of(), Map.of());

        } catch (IOException | QueryNodeException e) {
            logger.error("Query IO error: {}", e.getMessage());
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
