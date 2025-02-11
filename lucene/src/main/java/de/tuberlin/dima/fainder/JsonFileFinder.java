package de.tuberlin.dima.fainder;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.nio.file.FileVisitResult;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.SimpleFileVisitor;
import java.nio.file.attribute.BasicFileAttributes;
import java.util.ArrayList;
import java.util.List;

public class JsonFileFinder {
    private static final Logger logger = LoggerFactory.getLogger(JsonFileFinder.class);

    public static List<Path> getJsonFiles(Path directory) throws IOException {
        List<Path> jsonFiles = new ArrayList<>();
        Files.walkFileTree(directory, new SimpleFileVisitor<>() {
            @Override
            public FileVisitResult visitFile(Path file, BasicFileAttributes attrs) {
                if (file.toString().endsWith(".json")) {
                    jsonFiles.add(file);
                }
                return FileVisitResult.CONTINUE;
            }
        });

        logger.info("Found {} JSON files", jsonFiles.size());
        return jsonFiles;
    }
}
