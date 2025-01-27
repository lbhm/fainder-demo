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

import java.io.IOException;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Set;

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

    // Constant flag for testing different implementations
    private final Boolean BOOL_FILTER;

    public LuceneSearch(Path indexPath) throws IOException {
        Directory indexDir = FSDirectory.open(indexPath);
        IndexReader reader = DirectoryReader.open(indexDir);
        searcher = new IndexSearcher(reader);
        // Configure analyzer to keep stop words
        StandardAnalyzer analyzer = new StandardAnalyzer(CharArraySet.EMPTY_SET);

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
        // TODO: Investigate performance and if this breaks the query
        BooleanQuery.Builder queryBuilder = new BooleanQuery.Builder();
        String escapedQuery = QueryParser.escape(queryText);

        // Add a subquery for each field with its boost
        int i = 0;
        for (Map.Entry<String, Float> field : searchFields.entrySet()) {
            // Create boosted queries for each type of match
            Float boost = field.getValue();
            QueryParser parser = fieldParsers[i++];

            // Exact match (highest boost)
            Query exactQuery = parser.parse("(" + escapedQuery + ")^" + (boost * 2.0f));
            queryBuilder.add(exactQuery, BooleanClause.Occur.SHOULD);

            // Fuzzy match for typos
            Query fuzzyQuery = parser.parse("(" + escapedQuery + "~)^" + boost);
            queryBuilder.add(fuzzyQuery, BooleanClause.Occur.SHOULD);

            // Prefix match for partial words
            Query prefixQuery = parser.parse("(" + escapedQuery + "*)^" + (boost * 0.5f));
            queryBuilder.add(prefixQuery, BooleanClause.Occur.SHOULD);
        }

        return queryBuilder.build();
    }

    /**
     * @param query      The query string
     * @param docIds     Set of document IDs to filter (optional)
     * @param minScore   The minimum score for a document to be included in the results
     * @param maxResults The maximum number of documents to return
     * @return A pair of lists: document IDs and their scores
     */
    public Pair<List<Integer>, List<Float>> search(String query, Set<Integer> docIds, Float minScore, int maxResults) {
        if (query == null || query.isEmpty()) {
            return new Pair<>(List.of(), List.of());
        }

        try {
            Query multiFieldQuery = createMultiFieldQuery(query);

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
                hits = searcher.search(multiFieldQuery, maxResults).scoreDocs;
            }

            StoredFields storedFields = searcher.storedFields();
            List<Integer> results = new ArrayList<>();
            List<Float> scores = new ArrayList<>();
            for (ScoreDoc scoreDoc : hits) {
                int docId = scoreDoc.doc;
                Document doc = storedFields.document(docId);
                logger.info("Hit {}: {} (Score: {})", docId, doc.get("name"), scoreDoc.score);
                int result = Integer.parseInt(doc.get("id"));

                if (minScore == null || scoreDoc.score >= minScore) {
                    results.add(result);
                    scores.add(scoreDoc.score);
                }
            }

            return new Pair<List<Integer>, List<Float>>(results, scores);
        } catch (ParseException e) {
            logger.error("Query parsing error: {}", e.getMessage());
            return new Pair<>(List.of(), List.of());
        } catch (IOException e) {
            logger.error("Query IO error: {}", e.getMessage());
            return new Pair<>(List.of(), List.of());
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
