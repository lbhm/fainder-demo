package de.tuberlin.dima.fainder;

import de.tuberlin.dima.fainder.LuceneSearch.SearchResult;
import io.github.cdimascio.dotenv.Dotenv;
import io.github.cdimascio.dotenv.DotenvException;
import io.grpc.Server;
import io.grpc.ServerBuilder;
import io.grpc.stub.StreamObserver;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;
import java.util.stream.Stream;

public class LuceneServer {
    private static final Logger logger = LoggerFactory.getLogger(LuceneServer.class);
    private static Path indexPath;
    private static Path dataPath;
    private static int port;
    private static int maxResults;
    private static float minScore;
    private static int chunkSize;
    private static LuceneSearch luceneSearch;
    private Server grpcServer;

    public static void main(String[] args) throws IOException, InterruptedException {
        final LuceneServer server = new LuceneServer();
        server.loadConfig();
        server.loadIndex(indexPath, dataPath);
        server.start(port);
        server.blockUntilShutdown();
    }

    public void loadConfig() {
        try {
            Dotenv config = Dotenv.configure().ignoreIfMissing().load();
            String dataDir = config.get("DATA_DIR");
            String collectionName = config.get("COLLECTION_NAME");
            String croissantDir = config.get("CROISSANT_DIR", "croissant");
            String luceneDir = config.get("LUCENE_DIR", "lucene");
            if (dataDir == null || collectionName == null) {
                throw new DotenvException("Missing required configuration: DATA_DIR, COLLECTION_NAME");
            }

            indexPath = Paths.get(dataDir, collectionName, luceneDir);
            dataPath = Paths.get(dataDir, collectionName, croissantDir);
            port = Integer.parseInt(config.get("LUCENE_PORT", "8001"));
            maxResults = Integer.parseInt(config.get("LUCENE_MAX_RESULTS", "100000"));
            minScore = Float.parseFloat(config.get("LUCENE_MIN_SCORE", "1.0"));
            chunkSize = Integer.parseInt(config.get("LUCENE_CHUNK_SIZE", "1024"));
        } catch (DotenvException e) {
            logger.error("Failed to load config: {}", e.getMessage());
            System.exit(1);
        }
    }

    public void loadIndex(Path indexPath, Path dataPath) throws IOException {
        if (Files.exists(indexPath) && Files.isDirectory(indexPath)) {
            logger.info("Index directory {} already exists. Skipping index creation", indexPath);
        } else {
            logger.info("Creating index from data at {}", dataPath);
            try {
                LuceneIndexer.createIndex(indexPath, dataPath);
            } catch (RuntimeException e) {
                logger.error("Index creation failed: {}", e.getMessage());
                System.exit(1);
            }
            logger.info("Index successfully created and stored at {}", indexPath);
        }
        luceneSearch = new LuceneSearch(indexPath);
    }

    private void start(int port) throws IOException {
        logger.info("Starting Lucene Server");

        grpcServer = ServerBuilder.forPort(port).addService(new LuceneConnectorImpl()).build()
                .start();
        logger.info("Server started, listening on {}", grpcServer.getPort());

        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            logger.info("Shutting down gRPC server since JVM is shutting down");
            LuceneServer.this.stop();
            logger.info("Server shut down");
        }));
    }

    private void stop() {
        if (grpcServer != null) {
            grpcServer.shutdown();
        }
    }

    private void blockUntilShutdown() throws InterruptedException {
        if (grpcServer != null) {
            grpcServer.awaitTermination();
        }
    }

    static class LuceneConnectorImpl extends LuceneConnectorGrpc.LuceneConnectorImplBase {
        @Override
        public void evaluate(QueryRequest queryRequest, StreamObserver<QueryResponse> responseObserver) {
            String query = queryRequest.getQuery();
            Set<Integer> docIds = new HashSet<>(queryRequest.getDocIdsList());

            QueryResponse.Builder responseBuilder = QueryResponse.newBuilder();
            SearchResult searchResults = luceneSearch.search(query, docIds, minScore, maxResults, queryRequest.getEnableHighlighting());
            responseBuilder.addAllResults(searchResults.docIds).addAllScores(searchResults.scores);

            // Add highlights for each document
            for (Map.Entry<Integer, Map<String, String>> docEntry : searchResults.highlights.entrySet()) {
                int docId = docEntry.getKey();
                Map<String, String> fieldHighlights = docEntry.getValue();

                // Create field highlights for this document
                FieldHighlights.Builder fieldsBuilder = FieldHighlights.newBuilder();

                // Add all field highlights
                fieldsBuilder.putAllFields(fieldHighlights);

                // Add the complete highlights for this document
                responseBuilder.putHighlights(docId, fieldsBuilder.build());
            }

            responseObserver.onNext(responseBuilder.build());
            responseObserver.onCompleted();
        }

        @Override
        public void evaluateStream(QueryRequest queryRequest, StreamObserver<QueryResponseChunk> responseObserver) {
            String query = queryRequest.getQuery();
            Set<Integer> docIds = new HashSet<>(queryRequest.getDocIdsList());

            SearchResult searchResults = luceneSearch.search(query, docIds, minScore, maxResults, queryRequest.getEnableHighlighting());

            // Split results into chunks
            int totalDocs = searchResults.docIds.size();
            int numChunks = (int) Math.ceil((double) totalDocs / chunkSize);

            for (int chunkIndex = 0; chunkIndex < numChunks; chunkIndex++) {
                // Calculate start and end indices for this chunk
                int startIdx = chunkIndex * chunkSize;
                int endIdx = Math.min(startIdx + chunkSize, totalDocs);

                // Build response chunk
                QueryResponseChunk.Builder chunkBuilder = QueryResponseChunk.newBuilder();

                // Add doc IDs and scores for this chunk
                for (int i = startIdx; i < endIdx; i++) {
                    chunkBuilder.addDocIds(searchResults.docIds.get(i));
                    chunkBuilder.addScores(searchResults.scores.get(i));
                }

                // Add highlights for documents in this chunk
                for (int i = startIdx; i < endIdx; i++) {
                    int docId = searchResults.docIds.get(i);
                    if (searchResults.highlights.containsKey(docId)) {
                        Map<String, String> fieldHighlights = searchResults.highlights.get(docId);

                        // Create field highlights for this document
                        FieldHighlights.Builder fieldsBuilder = FieldHighlights.newBuilder();
                        fieldsBuilder.putAllFields(fieldHighlights);

                        // Add the highlights for this document
                        chunkBuilder.putHighlights(docId, fieldsBuilder.build());
                    }
                }

                // Mark if this is the last chunk
                chunkBuilder.setIsLastChunk(chunkIndex == numChunks - 1);

                // Send the chunk
                responseObserver.onNext(chunkBuilder.build());
            }

            // Complete the stream
            responseObserver.onCompleted();
        }

        @Override
        public void recreateIndex(RecreateIndexRequest request, StreamObserver<RecreateIndexResponse> responseObserver) {
            try {
                // Close existing searcher to release file handles
                if (luceneSearch != null) {
                    luceneSearch.close();
                }

                // Delete existing index directory
                try (Stream<Path> paths = Files.walk(indexPath)) {
                    paths.sorted(java.util.Comparator.reverseOrder()).forEach(path -> {
                        try {
                            Files.delete(path);
                        } catch (IOException e) {
                            logger.warn("Failed to delete file: {}", path, e);
                        }
                    });
                }

                // Create new index
                LuceneIndexer.createIndex(indexPath, dataPath);
                luceneSearch = new LuceneSearch(indexPath);

                RecreateIndexResponse response = RecreateIndexResponse.newBuilder()
                        .setSuccess(true)
                        .setMessage("Index successfully recreated")
                        .build();

                responseObserver.onNext(response);
                responseObserver.onCompleted();
            } catch (Exception e) {
                logger.error("Failed to recreate index: {}", e.getMessage());
                RecreateIndexResponse response = RecreateIndexResponse.newBuilder()
                        .setSuccess(false)
                        .setMessage("Failed to recreate index: " + e.getMessage())
                        .build();

                responseObserver.onNext(response);
                responseObserver.onCompleted();
            }
        }
    }
}
