package de.tuberlin.dima.fainder;

import org.apache.lucene.search.CollectorManager;
import org.apache.lucene.search.ScoreDoc;
import org.apache.lucene.search.TopDocs;
import org.apache.lucene.search.TotalHits;

import java.util.ArrayList;
import java.util.Collection;
import java.util.List;
import java.util.Set;

public class CustomCollectorManager implements CollectorManager<CustomCollector, TopDocs> {
    private final Set<Integer> filterDocIds;
    private final int numHits;

    public CustomCollectorManager(int numHits, Set<Integer> filterDocIds) {
        this.filterDocIds = filterDocIds;
        this.numHits = numHits;
    }

    @Override
    public CustomCollector newCollector() {
        return new CustomCollector(filterDocIds, numHits);
    }

    @Override
    public TopDocs reduce(Collection<CustomCollector> collectors) {
        List<ScoreDoc> allScoreDocs = new ArrayList<>();
        int totalHits = 0;

        for (CustomCollector collector : collectors) {
            TopDocs topDocs = collector.getTopDocs();
            totalHits += (int) topDocs.totalHits.value();
            allScoreDocs.addAll(List.of(topDocs.scoreDocs));
        }

        allScoreDocs.sort((d1, d2) -> Float.compare(d2.score, d1.score));
        ScoreDoc[] scoreDocs = allScoreDocs.subList(0, Math.min(numHits, allScoreDocs.size())).toArray(new ScoreDoc[0]);

        return new TopDocs(new TotalHits(totalHits, TotalHits.Relation.EQUAL_TO), scoreDocs);
    }
}
