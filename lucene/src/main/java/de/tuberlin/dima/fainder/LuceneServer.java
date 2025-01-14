package de.tuberlin.dima.fainder;

import io.grpc.Server;
import io.grpc.ServerBuilder;
import io.grpc.stub.StreamObserver;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.HashSet;
import java.util.List;
import java.util.Properties;
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
        server.loadConfig("config.properties");
        server.loadIndex(indexPath, dataPath);
        server.start(port);
        server.blockUntilShutdown();
    }

    public void loadConfig(String fileName) {
        Properties properties = new Properties();
        try (InputStream inputStream = LuceneServer.class.getClassLoader().getResourceAsStream(fileName)) {
            String fainderHome = System.getenv("FAINDER_DEMO_HOME");
            if (fainderHome == null) {
                logger.error("FAINDER_DEMO_HOME environment variable is not set");
                System.exit(1);
            }
            if (inputStream == null) {
                logger.error("Property file '{}' not found in the classpath", fileName);
                System.exit(1);
            }

            properties.load(inputStream);
            indexPath = Paths.get(fainderHome, properties.getProperty("indexPath"));
            dataPath = Paths.get(fainderHome, properties.getProperty("dataPath"));
            maxResults = Integer.parseInt(properties.getProperty("maxResults"));
            port = Integer.parseInt(properties.getProperty("port"));
            minScore = Float.parseFloat(properties.getProperty("minScore"));
            logger.info("Loaded config: {}", properties);
        } catch (IOException e) {
            logger.error("Failed to load properties: {}", e.getMessage());
            System.exit(1);
        }
    }

    public void loadIndex(Path indexPath, Path dataPath) throws IOException {
        if (Files.exists(indexPath) && Files.isDirectory(indexPath)) {
            logger.info("Index directory already exists. Skipping index creation");
        } else {
            logger.info("Creating index");
            try {
                LuceneIndexer.createIndex(indexPath, dataPath);
            } catch (RuntimeException e) {
                logger.error("Index creation failed: {}", e.getMessage());
                System.exit(1);
            }
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
            QueryResponse response = QueryResponse
                    .newBuilder()
                    .addAllResults(searchResults.getFirst())
                    .addAllScores(searchResults.getSecond())
                    .build();

            responseObserver.onNext(response);
            responseObserver.onCompleted();
        }
    }
}
