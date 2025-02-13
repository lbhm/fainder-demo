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
            SearchResult searchResults;
            try {
                searchResults = luceneSearch.search(query, docIds, minScore, maxResults, queryRequest.getEnableHighlighting());
            }
            catch (IOException e) {
                logger.error("Failed to search index: {}", e.getMessage());
                responseObserver.onNext(responseBuilder.build());
                responseObserver.onCompleted();
                return;
            }

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
        public void recreateIndex(RecreateIndexRequest request, StreamObserver<RecreateIndexResponse> responseObserver) {
            try {
                synchronized (this) {
                    // Create new index in a temporary location
                    Path tempIndexPath = indexPath.resolveSibling(indexPath.getFileName() + "_temp");
                    LuceneIndexer.createIndex(tempIndexPath, dataPath);

                    // Close existing searcher
                    if (luceneSearch != null) {
                        luceneSearch.close();
                    }

                    // Delete existing index directory
                    if (Files.exists(indexPath)) {
                        try (Stream<Path> paths = Files.walk(indexPath)) {
                            paths.sorted(java.util.Comparator.reverseOrder())
                                .forEach(path -> {
                                    try {
                                        Files.delete(path);
                                    } catch (IOException e) {
                                        logger.warn("Failed to delete: {}", path, e);
                                    }
                                });
                        }
                    }

                    // Move new index to proper location
                    Files.move(tempIndexPath, indexPath);

                    // Create new searcher
                    luceneSearch = new LuceneSearch(indexPath);

                    RecreateIndexResponse response = RecreateIndexResponse.newBuilder()
                            .setSuccess(true)
                            .setMessage("Index successfully recreated")
                            .build();

                    responseObserver.onNext(response);
                    responseObserver.onCompleted();
                }
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
