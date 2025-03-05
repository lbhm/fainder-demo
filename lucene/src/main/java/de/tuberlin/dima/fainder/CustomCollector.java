package de.tuberlin.dima.fainder;

import org.apache.lucene.document.Document;
import org.apache.lucene.index.LeafReader;
import org.apache.lucene.index.LeafReaderContext;
import org.apache.lucene.index.NumericDocValues;
import org.apache.lucene.index.StoredFields;
import org.apache.lucene.search.*;

import java.io.IOException;
import java.util.Set;
import java.util.BitSet;
import java.util.Collections;

public class CustomCollector implements Collector {
    private final BitSet filterBitSet;
    private final TopScoreDocCollector topScoreDocCollector;

    public CustomCollector(BitSet filterBitSet, int numHits) {
        this.filterBitSet = filterBitSet;
        TopScoreDocCollectorManager topScoreDocCollectorManager = new TopScoreDocCollectorManager(numHits, Integer.MAX_VALUE);
        this.topScoreDocCollector = topScoreDocCollectorManager.newCollector();
    }

    @Override
    public LeafCollector getLeafCollector(LeafReaderContext context) throws IOException {
        LeafCollector leafCollector = topScoreDocCollector.getLeafCollector(context);
        final NumericDocValues idValues = context.reader().getNumericDocValues("id");

        return new LeafCollector() {
            private Scorable scorer;

            @Override
            public void setScorer(Scorable scorer) throws IOException {
                this.scorer = scorer;
                leafCollector.setScorer(scorer);
            }

            @Override
            public void collect(int doc) throws IOException {
                if (idValues != null && idValues.advanceExact(doc)) {
                    long docId = idValues.longValue();
                    if (filterBitSet.get((int) docId)) {
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
