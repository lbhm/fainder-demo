package de.tuberlin.dima.fainder;

import org.apache.lucene.analysis.CharArraySet;
import org.apache.lucene.analysis.standard.StandardAnalyzer;
import org.apache.lucene.document.Document;
import org.apache.lucene.index.DirectoryReader;
import org.apache.lucene.index.IndexReader;
import org.apache.lucene.index.StoredFields;
import org.apache.lucene.index.Term;
import org.apache.lucene.queryparser.flexible.core.QueryNodeException;
import org.apache.lucene.queryparser.flexible.standard.StandardQueryParser;
import org.apache.lucene.queryparser.flexible.standard.config.StandardQueryConfigHandler;
import org.apache.lucene.search.*;
import org.apache.lucene.search.highlight.Highlighter;
import org.apache.lucene.search.highlight.InvalidTokenOffsetsException;
import org.apache.lucene.search.highlight.QueryScorer;
import org.apache.lucene.search.highlight.SimpleHTMLFormatter;
import org.apache.lucene.store.Directory;
import org.apache.lucene.store.FSDirectory;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.nio.file.Path;
import java.util.*;

public class LuceneSearch {
    private static final Logger logger = LoggerFactory.getLogger(LuceneSearch.class);
    private final Object searchLock = new Object();
    private volatile IndexReader reader;
    private volatile IndexSearcher searcher;
    private final Directory indexDir;
    private final Map<String, Float> searchFields = Map.of(
            "name", 5.0f,           // Boost name matches
            "description", 2.0f,    // Normal weight for description
            "keywords", 4.0f,       // Slightly boost keyword matches
            "creator_name", 1.6f,   // Lower weight for creator
            "publisher_name", 1.6f, // Lower weight for publisher
            "alternateName", 3.0f);
    private final StandardAnalyzer analyzer;
    private final StandardQueryParser parser;

    // Constant flag for testing different implementations
    private final Boolean BOOL_FILTER;

    public LuceneSearch(Path indexPath) throws IOException {
        this(indexPath, true);
    }

    public LuceneSearch(Path indexPath, boolean useBoolFilter) throws IOException {
        indexDir = FSDirectory.open(indexPath);
        reader = DirectoryReader.open(indexDir);
        BOOL_FILTER = useBoolFilter;
        searcher = new IndexSearcher(reader);


        // Configure analyzer to keep stop words
        analyzer = new StandardAnalyzer(CharArraySet.EMPTY_SET);

        parser = new StandardQueryParser();
        StandardQueryConfigHandler config = (StandardQueryConfigHandler) parser.getQueryConfigHandler();
        config.set(StandardQueryConfigHandler.ConfigurationKeys.ALLOW_LEADING_WILDCARD, true);
        config.set(StandardQueryConfigHandler.ConfigurationKeys.ANALYZER, analyzer);
        config.set(StandardQueryConfigHandler.ConfigurationKeys.FIELD_BOOST_MAP, searchFields);
        config.set(StandardQueryConfigHandler.ConfigurationKeys.MULTI_FIELDS, searchFields.keySet().toArray(new String[0]));
        config.set(StandardQueryConfigHandler.ConfigurationKeys.DEFAULT_OPERATOR, StandardQueryConfigHandler.Operator.AND);

        IndexSearcher.setMaxClauseCount(Integer.MAX_VALUE);

        // Use constant score rewrite for wildcard queries to improve performance
        config.set(StandardQueryConfigHandler.ConfigurationKeys.MULTI_TERM_REWRITE_METHOD,
                  MultiTermQuery.CONSTANT_SCORE_REWRITE);
    }

    public void refresh() throws IOException {
        synchronized (searchLock) {
            if (reader != null) {
                reader.close();
            }
            reader = DirectoryReader.open(indexDir);
            searcher = new IndexSearcher(reader);
        }
    }

    /**
     * @param query              The query string
     * @param docIds             Set of document IDs to filter (optional)
     * @param minScore           The minimum score for a document to be included in the results
     * @param maxResults         The maximum number of documents to return
     * @param enableHighlighting Flag to enable or disable highlighting
     * @return A pair of lists: document IDs and their scores
     */
    public SearchResult search(String query, Set<Integer> docIds, Float minScore, int maxResults, boolean enableHighlighting) throws IOException {
        synchronized (searchLock) {
            if (!reader.tryIncRef()) {
                throw new IOException("IndexReader is closed");
            }

            try {
                if (query == null || query.isEmpty()) {
                    return new SearchResult(List.of(), List.of(), Map.of());
                }

                try {
                    Query boostedQuery = new BoostQuery(parser.parse(query, null), 5.0f);
                    Highlighter highlighter = null;

                    if (enableHighlighting) {
                        QueryScorer scorer = new QueryScorer(boostedQuery);
                        SimpleHTMLFormatter htmlFormatter = new SimpleHTMLFormatter("<mark>", "</mark>");
                        highlighter = new Highlighter(htmlFormatter, scorer);
                        highlighter.setMaxDocCharsToAnalyze(Integer.MAX_VALUE);
                    }

                    logger.info("Input query {}. Executing query {}. With filter: {} ", query, boostedQuery, docIds);

                    ScoreDoc[] hits;
                    try {
                        if (docIds != null && !docIds.isEmpty()) {
                            // Create filter for allowed document IDs
                            // TODO: Does the docFilter actually help to reduce query execution time?
                            if (BOOL_FILTER) {
                                Query docFilter = createDocFilter(docIds);
                                BooleanQuery.Builder queryBuilder = new BooleanQuery.Builder();
                                queryBuilder.add(boostedQuery, BooleanClause.Occur.MUST);
                                queryBuilder.add(docFilter, BooleanClause.Occur.FILTER);
                                Query filteredQuery = queryBuilder.build();
                                hits = searcher.search(filteredQuery, maxResults).scoreDocs;
                            } else {
                                BitSet filterBitSet = new BitSet();
                                for (int docId : docIds) {
                                    filterBitSet.set(docId);
                                }
                                CustomCollectorManager collectorManager = new CustomCollectorManager(maxResults, filterBitSet);
                                hits = searcher.search(boostedQuery, collectorManager).scoreDocs;
                            }
                        } else {
                            hits = searcher.search(boostedQuery, maxResults).scoreDocs;
                        }
                    } catch (IOException e) {
                        logger.error("Search failed: {}", e.getMessage());
                        return new SearchResult(List.of(), List.of(), Map.of());
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
                    logger.info("Returning {} results with score over {}", results.size(), minScore);

                    return new SearchResult(results, scores, highlights);
                } catch (IOException | QueryNodeException e) {
                    logger.error("Query IO error: {}", e.getMessage());
                    return new SearchResult(List.of(), List.of(), Map.of());
                }
            } finally {
                reader.decRef();
            }
        }
    }

    private Query createDocFilter(Set<Integer> docIds) {
        BooleanQuery.Builder builder = new BooleanQuery.Builder();
        for (int docId : docIds) {
            builder.add(new TermQuery(new Term("id", Integer.toString(docId))), BooleanClause.Occur.SHOULD);
        }
        return builder.build();
    }

    public void close() throws IOException {
        synchronized (searchLock) {
            if (reader != null) {
                reader.close();
                reader = null;
            }
            if (indexDir != null) {
                indexDir.close();
            }
        }
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
}
