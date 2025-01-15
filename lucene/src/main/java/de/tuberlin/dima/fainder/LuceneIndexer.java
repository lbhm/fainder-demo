package de.tuberlin.dima.fainder;

import com.google.gson.Gson;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonPrimitive;
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
import java.util.Arrays;
import java.util.List;
import java.util.Map;

public class LuceneIndexer {
    private static final Logger logger = LoggerFactory.getLogger(LuceneIndexer.class);

    public static void createIndex(Path indexPath, Path dataPath) {
        try {
            // Check if the data directory exists
            if (!Files.exists(dataPath)) {
                logger.error("Data directory does not exist");
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


                // Iterate through all key-value pairs in the JSON object
                for (Map.Entry<String, JsonElement> entry : jsonObject.entrySet()) {
                    String key = entry.getKey();
                    JsonElement value = entry.getValue();
                    // Convert the value to a string
                    String valueStr = value.isJsonNull() ? "" : value.toString();
                    if (valueStr.equals(("NaN"))) valueStr = "";
                    if(key.equals("id")){
                        document.add(new NumericDocValuesField("id", value.getAsInt()));
                        document.add(new StoredField("id", valueStr));
                    } else if (key.equals("dateModified")) {
                        // Assuming dateModified is best represented as a StringField
                        document.add(new StringField(key, valueStr, Field.Store.YES));
                    } else if (key.equals("isAccessibleForFree")) {
                        // Assuming dateModified is best represented as a StringField
                        document.add(new StringField(key, valueStr, Field.Store.YES));
                    } else if (value.isJsonPrimitive()) {
                        JsonPrimitive primitive = value.getAsJsonPrimitive();
                        if (primitive.isString()) {
                            document.add(new TextField(key, primitive.getAsString(), Field.Store.YES));
                        } else {
                            document.add(new StringField(key, valueStr, Field.Store.YES));
                        }
                    } else {
                        document.add(new TextField(key, valueStr, Field.Store.YES));
                    }
                }
                // add the file path as a field named "path"
                document.add(new StringField("path", filePath.toString(), Field.Store.YES));

                // add the full file as a field named "all" to make it searchable
                document.add(new TextField("all", jsonContent, Field.Store.YES));

                // Add the document to the index
                writer.addDocument(document);
                fileCounter++;
            }
            writer.commit();
            writer.close();
        } catch (IOException e) {
            logger.error(Arrays.toString(e.getStackTrace()));
        }
    }
}
