package de.tuberlin.dima.fainder;

import org.apache.lucene.document.Document;
import org.apache.lucene.index.LeafReader;
import org.apache.lucene.index.LeafReaderContext;
import org.apache.lucene.index.StoredFields;
import org.apache.lucene.search.*;

import java.io.IOException;
import java.util.Set;

public class CustomCollector implements Collector {
    private final Set<Integer> filterDocIds;
    private final TopScoreDocCollector topScoreDocCollector;

    public CustomCollector(Set<Integer> filterDocIds, int numHits) {
        this.filterDocIds = filterDocIds;
        TopScoreDocCollectorManager topScoreDocCollectorManager = new TopScoreDocCollectorManager(numHits, Integer.MAX_VALUE);
        this.topScoreDocCollector = topScoreDocCollectorManager.newCollector();
    }

    @Override
    public LeafCollector getLeafCollector(LeafReaderContext context) throws IOException {
        LeafCollector leafCollector = topScoreDocCollector.getLeafCollector(context);
        final StoredFields storedFields;
        try (LeafReader reader = context.reader()) {
            storedFields = reader.storedFields();
        }

        return new LeafCollector() {
            @Override
            public void setScorer(Scorable scorer) throws IOException {
                leafCollector.setScorer(scorer);
            }

            @Override
            public void collect(int doc) throws IOException {
                Document document = storedFields.document(doc);
                String idString = document.get("id");
                if (idString != null) {
                    int id = Integer.parseInt(idString);
                    if (filterDocIds.contains(id)) {
                        leafCollector.collect(doc);
                    }
                }
            }
        };
    }

    @Override
    public ScoreMode scoreMode() {
        return ScoreMode.COMPLETE;
    }

    public TopDocs getTopDocs() {
        return topScoreDocCollector.topDocs();
    }
}
