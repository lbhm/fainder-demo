package de.tuberlin.dima.fainder;

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
import java.util.List;
import java.util.Set;

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
            maxResults = Integer.parseInt(config.get("LUCENE_MAX_RESULTS", "100"));
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

        grpcServer = ServerBuilder.forPort(port).addService(new KeywordQueryImpl()).build().start();
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

    static class KeywordQueryImpl extends KeywordQueryGrpc.KeywordQueryImplBase {
        @Override
        public void evaluate(QueryRequest queryRequest, StreamObserver<QueryResponse> responseObserver) {
            String query = queryRequest.getQuery();
            Set<Integer> docIds = new HashSet<>(queryRequest.getDocIdsList());

            Pair<List<Integer>, List<Float>> searchResults = luceneSearch.search(query, docIds, minScore, maxResults);
            QueryResponse response = QueryResponse.newBuilder()
                    .addAllResults(searchResults.getFirst()).addAllScores(searchResults.getSecond())
                    .build();

            responseObserver.onNext(response);
            responseObserver.onCompleted();
        }
    }
}
