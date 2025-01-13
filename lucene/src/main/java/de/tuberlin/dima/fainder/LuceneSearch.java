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

public class LuceneSearch {
    private static final Logger logger = LoggerFactory.getLogger(LuceneSearch.class);
    private final IndexSearcher searcher;
    private final QueryParser parser;

    public LuceneSearch(Path indexPath) throws IOException {
        Directory indexDir = FSDirectory.open(indexPath);
        IndexReader reader = DirectoryReader.open(indexDir);
        searcher = new IndexSearcher(reader);
        // Configure analyzer to keep stop words
        StandardAnalyzer analyzer = new StandardAnalyzer(CharArraySet.EMPTY_SET);
        parser = new QueryParser("all", analyzer);
        // parser.setAllowLeadingWildcard(true); // Allow wildcards at start of term
    }

    /**
     * @param query      The query string
     * @param docIds     List of document IDs to filter (optional)
     * @param minScore   The minimum score for a document to be included in the results
     * @param maxResults The maximum number of documents to return
     * @return A pair of lists: document IDs and their scores
     */
    public Pair<List<Integer>, List<Float>> search(String query, List<Integer> docIds, Float minScore, int maxResults) {
        if (query == null || query.isEmpty()) {
            return new Pair<>(List.of(), List.of());
        }

        try {
            // Escape special characters
            String escapedQuery = QueryParser.escape(query);

            // Create a boolean query combining exact and fuzzy matching
            BooleanQuery.Builder queryBuilder = new BooleanQuery.Builder();
            // Exact match gets highest boost
            queryBuilder.add(parser.parse(escapedQuery), BooleanClause.Occur.SHOULD);
            // Fuzzy match for typos
            queryBuilder.add(parser.parse(escapedQuery + "~"), BooleanClause.Occur.SHOULD);
            // Prefix match for partial words
            queryBuilder.add(parser.parse(escapedQuery + "*"), BooleanClause.Occur.SHOULD);

            if (docIds != null && !docIds.isEmpty()) {
                // Create filter for allowed document IDs
                // TODO: Does the docFilter actually help to reduce query execution time?
                Query docFilter = createDocFilter(docIds);
                queryBuilder.add(docFilter, BooleanClause.Occur.FILTER);
            }

            Query parsedQuery = queryBuilder.build();
            logger.info("Executing query {}", parsedQuery);

            ScoreDoc[] hits = searcher.search(parsedQuery, maxResults).scoreDocs;
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

    private Query createDocFilter(List<Integer> docIds) {
        // TODO: Improve efficiency of this
        // just or TermQueries for id in filter
        BooleanQuery.Builder builder = new BooleanQuery.Builder();
        for (int docId : docIds) {
            builder.add(new TermQuery(new Term("id", String.valueOf(docId))), BooleanClause.Occur.SHOULD);
        }
        BooleanQuery.Builder filterQuery = new BooleanQuery.Builder();
        filterQuery.add(builder.build(), BooleanClause.Occur.MUST);
        return builder.build();
    }

}
