package de.tuberlin.dima.fainder;

import com.google.gson.Gson;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import org.apache.lucene.analysis.standard.StandardAnalyzer;
import org.apache.lucene.document.*;
import org.apache.lucene.index.IndexWriter;
import org.apache.lucene.index.IndexWriterConfig;
import org.apache.lucene.store.Directory;
import org.apache.lucene.store.FSDirectory;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.time.LocalDateTime;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeParseException;
import java.util.Arrays;
import java.util.List;
import java.util.Map;

public class LuceneIndexer {
    private static final Logger logger = LoggerFactory.getLogger(LuceneIndexer.class);

    // Field configuration map defines how each field should be indexed
    private static final Map<String, FieldConfig> FIELD_CONFIGS = Map.of(
        "id", new FieldConfig(FieldType.NUMERIC),
        "dateModified", new FieldConfig(FieldType.DATE),
        "alternateName", new FieldConfig(FieldType.TEXT),
        "name", new FieldConfig(FieldType.TEXT),
        "description", new FieldConfig(FieldType.TEXT),
        "keywords", new FieldConfig(FieldType.TEXT, true), // isArray=true
        "creator.name", new FieldConfig(FieldType.TEXT),   // nested field
        "publisher.name", new FieldConfig(FieldType.TEXT)  // nested field
    );

    private enum FieldType {
        NUMERIC, TEXT, DATE
    }

    private static class FieldConfig {
        final FieldType type;
        final boolean isArray;

        FieldConfig(FieldType type) {
            this(type, false);
        }

        FieldConfig(FieldType type, boolean isArray) {
            this.type = type;
            this.isArray = isArray;
        }
    }

    private static JsonElement getNestedValue(JsonObject jsonObject, String fieldPath) {
        String[] parts = fieldPath.split("\\.");
        JsonElement current = jsonObject;

        for (String part : parts) {
            if (current == null || !current.isJsonObject()) {
                return null;
            }
            current = current.getAsJsonObject().get(part);
        }

        return current;
    }

    private static long parseDate(String dateStr) throws DateTimeParseException {
        try {
            // Try parsing as Instant (with timezone)
            return Instant.parse(dateStr).toEpochMilli();
        } catch (DateTimeParseException e1) {
            try {
                // Try parsing as LocalDateTime (without timezone) and convert to UTC
                LocalDateTime localDateTime = LocalDateTime.parse(dateStr);
                return localDateTime.toInstant(ZoneOffset.UTC).toEpochMilli();
            } catch (DateTimeParseException e2) {
                try {
                    // Try parsing with custom formatter for other formats
                    DateTimeFormatter formatter = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss[.SSS]");
                    LocalDateTime localDateTime = LocalDateTime.parse(dateStr, formatter);
                    return localDateTime.toInstant(ZoneOffset.UTC).toEpochMilli();
                } catch (DateTimeParseException e3) {
                    logger.error("Failed to parse date '{}' with all attempted formats", dateStr);
                    throw e3;
                }
            }
        }
    }

    private static void addFieldToDocument(Document document, String fieldName, JsonElement value, FieldConfig config) {
        if (value == null || value.isJsonNull()) return;

        Field field = switch (config.type) {
            case NUMERIC -> {
                int numValue = value.getAsInt();
                document.add(new StoredField(fieldName, numValue));
                yield new NumericDocValuesField(fieldName, numValue);
            }
            case DATE -> {
                String dateStr = value.getAsString();
                document.add(new StoredField(fieldName, dateStr));
                try {
                    long timestamp = parseDate(dateStr);
                    yield new NumericDocValuesField(fieldName, timestamp);
                } catch (DateTimeParseException e) {
                    logger.error("Date parsing failed for '{}': {}", value.getAsString(), e.getMessage());
                    yield null;
                }
            }
            case TEXT -> {
                String textValue;
                if (config.isArray) {
                    JsonArray array = value.getAsJsonArray();
                    StringBuilder sb = new StringBuilder();
                    for (JsonElement element : array) {
                        sb.append(element.getAsString()).append(" ");
                    }
                    textValue = sb.toString().trim();
                } else {
                    textValue = value.getAsString();
                }
                document.add(new StoredField(fieldName, textValue));  // For retrieval
                yield new TextField(fieldName, textValue, Field.Store.NO);  // For searching
            }
        };
        if (field != null) {
            document.add(field);
        }
    }

    public static void createIndex(Path indexPath, Path dataPath) {
        try {
            // Check if the data directory exists
            if (!Files.exists(dataPath)) {
                logger.error("Data directory {} does not exist", dataPath);
                throw new RuntimeException("Data directory does not exist!");
            }

            List<Path> jsonFiles = JsonFileFinder.getJsonFiles(dataPath);
            if (jsonFiles.isEmpty()) {
                logger.error("No JSON files found in the data directory");
                throw new RuntimeException("No JSON files found in the data directory!");
            }

            // Create index for the selected files
            Files.createDirectories(indexPath);
            Directory directory = FSDirectory.open(indexPath);
            StandardAnalyzer analyzer = new StandardAnalyzer();
            IndexWriterConfig config = new IndexWriterConfig(analyzer);
            IndexWriter writer = new IndexWriter(directory, config);
            Gson gson = new Gson();
            for (Path filePath : jsonFiles) {
                // Read the content of the file
                String jsonContent = new String(Files.readAllBytes(filePath));

                // Parse the JSON content into a JsonObject
                JsonObject jsonObject = gson.fromJson(jsonContent, JsonObject.class);

                // check if the JSON object has an "id" field and if not, raise an error
                if (!jsonObject.has("id")) {
                    logger.error("JSON object does not have an 'id' field");
                    throw new RuntimeException("JSON object does not have an 'id' field!");
                }

                // Create a new Lucene Document
                Document document = new Document();

                // Add configured fields
                for (Map.Entry<String, FieldConfig> entry : FIELD_CONFIGS.entrySet()) {
                    String fieldName = entry.getKey();
                    JsonElement value = fieldName.contains(".") ?
                        getNestedValue(jsonObject, fieldName) :
                        jsonObject.get(fieldName);

                    if (value != null) {
                        addFieldToDocument(document, fieldName.replace(".", "_"),
                            value, entry.getValue());
                    }
                }

                // Add file path
                document.add(new StringField("path", filePath.toString(), Field.Store.YES));

                // Add document to index
                writer.addDocument(document);
            }
            writer.commit();
            writer.close();
        } catch (IOException e) {
            logger.error(Arrays.toString(e.getStackTrace()));
        }
    }
}
