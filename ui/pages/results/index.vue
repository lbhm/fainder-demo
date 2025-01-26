# This results page will display the results of the search query # The list of
the results will be displayed in a card format on the left side of the page and
the details of the selected result will be displayed on the right side of the
page

<template>
    <v-main>
      <v-divider></v-divider>
      <div class="pa-5">
      <!-- Remove search container -->

      <!-- Add search stats -->
      <div
        v-if="!isLoading && !error && results && results.length > 0"
        class="search-stats mb-4"
      >
        Found {{ resultCount }} results in {{ searchTime.toFixed(4) }}s
      </div>

      <!-- Error message -->
      <v-alert v-if="error" type="error" class="mt-4" prominent>
        <v-alert-title>Search Error</v-alert-title>
        <div class="error-details">
          <p>{{ error.message }}</p>
          <p v-if="error.details" class="error-technical-details mt-2">
            Technical details: {{ error.details }}
          </p>
          <v-btn
            class="mt-4"
            variant="outlined"
            color="error"
            @click="retrySearch"
          >
            Retry Search
          </v-btn>
        </div>
      </v-alert>

      <!-- Empty results message -->
      <v-alert
        v-if="!isLoading && !error && (!results || results.length === 0)"
        type="info"
        class="mt-4"
      >
        No results found for your search criteria
      </v-alert>

      <!-- Main Content -->
      <div class="results-wrapper">
        <div class="list-container">
          <!-- Remove the Modify Search button since we have inline search now -->

          <!-- Loading state -->
          <v-progress-circular
            v-if="isLoading"
            indeterminate
            color="primary"
            class="mt-4"
          ></v-progress-circular>

          <!-- Results list -->
          <v-virtual-scroll
            v-if="!isLoading && !error && results && results.length > 0"
            mode="manual"
            :items="results"
          >
            <template v-slot:default="{ item }">
              <v-card @click="selectResult(item)" :height="100">
                <v-card-title class="highlight-text" v-html="item.name"></v-card-title>
                <v-card-subtitle class="highlight-text" v-html="item.alternateName"></v-card-subtitle>
              </v-card>
            </template>
          </v-virtual-scroll>

          <!-- Pagination controls -->
          <div
            v-if="!isLoading && !error && results && results.length > 0"
            class="pagination-controls mt-4"
          >
            <v-pagination
              v-model="currentPage"
              :length="totalPages"
              :total-visible="totalVisible"
              rounded="circle"
              width="70%"
            ></v-pagination>
          </div>
        </div>

        <div class="details-container">
          <div class="pa-20">
            <v-card v-if="selectedResult">
              <v-card-title class="highlight-text" v-html="selectedResult.name">
                </v-card-title>
              <v-card-subtitle class="highlight-text" v-html="selectedResult.alternateName"></v-card-subtitle>

              <v-expansion-panels v-model="descriptionPanel">
                <v-expansion-panel>
                  <v-expansion-panel-title class="panel-title"
                    >Description</v-expansion-panel-title
                  >
                  <v-expansion-panel-text>
                    <div class="markdown-wrapper highlight-text">
                      <MDC :value="selectedResult.description"></MDC>
                    </div>
                  </v-expansion-panel-text>
                </v-expansion-panel>
              </v-expansion-panels>

              <v-expansion-panels
                v-if="selectedResult.recordSet"
                v-for="(file, index) in selectedResult.recordSet"
                :key="file.id"
                v-model="recordSetPanels[index]"
              >
                <v-expansion-panel>
                  <v-expansion-panel-title class="panel-title">{{
                    "file: " + file.name
                  }}</v-expansion-panel-title>
                  <v-expansion-panel-text>
                    <v-table>
                      <thead>
                        <tr>
                          <th>Field</th>
                          <th>Type</th>
                          <th>Histogram</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr
                          v-for="(field, fieldIndex) in file.field"
                          :key="field.id"
                        >
                          <td v-if="field.marked_name" v-html="field.marked_name"></td>
                          <td v-else>{{ field.name }}</td>
                          <td>{{ field.dataType[0] }}</td>
                          <td v-if="field.histogram">
                            <Bar
                              :chart-data="getChartData(field, fieldIndex)"
                              :chart-options="chartOptions"
                            />
                          </td>
                        </tr>
                      </tbody>
                    </v-table>
                  </v-expansion-panel-text>
                </v-expansion-panel>
              </v-expansion-panels>
            </v-card>
          </div>
        </div>
      </div>
    </div>
  </v-main>
</template>

<script setup>
import { Bar } from "vue-chartjs";
import { useTheme } from "vuetify";

const route = useRoute();
const theme = useTheme();
const searchOperations = useSearchOperations();

// Use the search state
const {
  results,
  selectedResultIndex, // Change to selectedResultIndex
  isLoading,
  error,
  searchTime,
  resultCount,
  currentPage,
  totalPages,
  query,
  fainder_mode,
  perPage
} = useSearchState();

console.log(selectedResultIndex.value);

// Add computed for selected result
const selectedResult = computed(() =>
  results.value ? results.value[selectedResultIndex.value] : null
);

// Initialize state from route
query.value = route.query.query;
fainder_mode.value = route.query.fainder_mode || 'low_memory';

const descriptionPanel = ref([0]);
const recordSetPanels = ref([]);
const totalVisible = ref(7);

// Add ref for window height
const windowHeight = ref(window.innerHeight);
const itemHeight = 100; // Height of each result card in pixels
const headerHeight = 200; // Approximate height of header elements (search + stats)
const paginationHeight = 56; // Height of pagination controls

// Update perPage to be calculated based on available height
const updatePerPage = computed(() => {
  const availableHeight = windowHeight.value - headerHeight - paginationHeight;
  const itemsPerPage = Math.floor(availableHeight / itemHeight);
  // Ensure we show at least 3 items and at most 15 items
  perPage.value = Math.max(3, Math.min(15, itemsPerPage));
  return perPage.value;
});

const handleResize = () => {
  updateTotalVisible();
  windowHeight.value = window.innerHeight;
};
// Add window resize handler
onMounted(() => {
  updateTotalVisible();
  window.addEventListener("resize", handleResize);
  windowHeight.value = window.innerHeight; // Initial value
});

onUnmounted(() => {
  window.removeEventListener("resize", handleResize);
});

function updateTotalVisible() {
  const width = window.innerWidth;
  if (width < 600) {
    totalVisible.value = 2;
  } else if (width < 960) {
    totalVisible.value = 3;
  } else {
    totalVisible.value = 4;
  }
}

watch(currentPage, async (newPage) => {
  await searchOperations.loadResults(
    query.value,
    newPage,
    fainder_mode.value
  );

  // Update URL with new page
  navigateTo({
    path: "/results",
    query: {
      query: query.value,
      page: newPage,
      index: selectedResultIndex.value,
      fainder_mode: fainder_mode.value,
      theme: theme.global.name.value,
    },
  });
});

watch(updatePerPage, (newPerPage) => {
  if (currentPage.value > 0) {
    perPage.value = newPerPage;
    searchOperations.loadResults(query.value, currentPage.value);
  }
});

const selectResult = (result) => {
  const index = results.value.indexOf(result);
  selectedResultIndex.value = index;

  if (result.recordSet) {
    descriptionPanel.value = [0];
    recordSetPanels.value = result.recordSet.map(() => [0]);
  }

  // Update URL with all necessary parameters
  navigateTo({
    path: "/results",
    query: {
      ...route.query, // Keep existing query parameters
      index: index,   // Update index
    },
  });
};

// Initialize from route on mount
onMounted(() => {
  if (route.query.index && results.value) {
    const index = parseInt(route.query.index);
    if (index >= 0 && index < results.value.length) {
      selectedResultIndex.value = index;
    }
  }
});

// Add retry function
const retrySearch = async () => {
  await searchOperations.loadResults(
    query.value,
    currentPage.value,
    route.query.fainder_mode
  );
};

// Initial load
await searchOperations.loadResults(
  query.value,
  currentPage.value,
  fainder_mode.value
);

const chartOptions = ref({
  scales: {
    x: {
      type: "linear",
      offset: false,
      grid: {
        offset: false,
      },
      title: {
        display: true,
        text: "Value",
        font: {
          size: 14,
        },
      },
    },
    y: {
      beginAtZero: true,
      title: {
        display: true,
        text: "Density",
        font: {
          size: 14,
        },
      },
    },
  },
  plugins: {
    tooltip: {
      callbacks: {
        title: (items) => {
          if (!items.length) return "";
          const item = items[0];
          const index = item.dataIndex;
          const dataset = item.chart.data.datasets[0];
          const binEdges = dataset.binEdges;
          return `Range: ${binEdges[index].toFixed(2)} - ${binEdges[
            index + 1
          ].toFixed(2)}`;
        },
        label: (item) => {
          return `Count: ${item.parsed.y.toFixed(4)}`;
        },
      },
    },
  },
  responsive: true,
  maintainAspectRatio: false,
});

const chartColors = [
  "rgba(248, 121, 121, 0.6)", // red
  "rgba(121, 134, 203, 0.6)", // blue
  "rgba(77, 182, 172, 0.6)", // teal
  "rgba(255, 183, 77, 0.6)", // orange
  "rgba(240, 98, 146, 0.6)", // pink
  "rgba(129, 199, 132, 0.6)", // green
  "rgba(149, 117, 205, 0.6)", // purple
  "rgba(77, 208, 225, 0.6)", // cyan
  "rgba(255, 167, 38, 0.6)", // amber
  "rgba(186, 104, 200, 0.6)", // purple
];

const getChartData = (field, index) => {
  if (!field.histogram) return null;

  const binEdges = field.histogram.bins;
  const counts = field.histogram.densities;

  if (counts == null || binEdges == null) return null;

  // Create array of bar objects with correct positioning and width
  const bars = counts.map((count, i) => ({
    x0: binEdges[i], // Start of bin
    x1: binEdges[i + 1], // End of bin
    y: count / (binEdges[i + 1] - binEdges[i]), // Density
  }));

  return {
    datasets: [
      {
        label: field.name,
        backgroundColor: chartColors[index % chartColors.length],
        borderColor: "rgba(0, 0, 0, 0.1)",
        data: bars,
        binEdges: binEdges,
        borderWidth: 1,
        borderRadius: 0,
        barPercentage: 1,
        categoryPercentage: 1,
        segment: {
          backgroundColor: (context) => chartColors[index % chartColors.length],
        },
        parsing: {
          xAxisKey: "x0",
          yAxisKey: "y",
        },
      },
    ],
  };
};



</script>

<style scoped>
.app-container {
  display: flex;
  flex-direction: column;
  max-width: 100%;
  min-height: calc(100vh - 64px);
  padding: 16px;
  margin-top: 0; /* Remove top margin since search is in app bar now */
}

/* Remove .search-container styles */

.results-wrapper {
  display: flex;
  gap: 24px;
  flex: 1;
}

.list-container {
  flex: 0 0 30%;
  min-width: 300px;
  max-width: 400px;
  position: sticky;
  top: 24px; /* Adjust based on your layout's top spacing */
  height: calc(100vh - 48px); /* Adjust based on your layout's spacing */
  overflow-y: auto; /* Allow scrolling within the container */
}

.details-container {
  flex: 1;
  min-width: 0; /* Prevents flex child from overflowing */
}

.mb-6 {
  margin-bottom: 24px;
}

.bg-grey-lighten-3 {
  background-color: #f5f5f5;
}

.markdown-wrapper {
  padding: 24px;
}

.mt-4 {
  margin-top: 16px;
}

.search-button {
  margin-bottom: 24px;
  width: 100%;
  font-weight: 500;
  letter-spacing: 0.5px;
  text-transform: none;
  height: 56px;
}

.error-container {
  width: 100%;
  max-width: 800px;
  margin: 0 auto;
  padding: 16px;
}

.panel-title {
  font-size: 1.25rem !important;
  font-weight: 500;
}

.search-stats {
  color: rgba(var(--v-theme-on-surface), 0.7);
  font-size: 0.875rem;
}

.pagination-controls {
  display: flex;
  justify-content: center;
  margin-top: 1rem;
  width: 100%;
}

.pagination-controls :deep(.v-pagination) {
  width: 100%;
  justify-content: center;
}

.error-details {
  white-space: pre-wrap;
  word-break: break-word;
}

.error-technical-details {
  font-family: monospace;
  font-size: 0.9em;
  color: rgba(var(--v-theme-on-error), 0.7);
}

/* Update highlight styles for details container */
.highlight-text :deep(mark) {
  background-color: rgba(var(--v-theme-warning), 0.2);
  color: inherit;
  padding: 0 2px;
  border-radius: 2px;
  font-weight: 500;
}

.highlight-text {
  line-height: 1.6;
  font-size: 1rem;
}

.description-preview {
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  font-size: 0.875rem;
  line-height: 1.4;
}

/* Update highlight text styles to handle all text variants */
.highlight-text,
:deep(.v-card-title),
:deep(.v-card-subtitle),
:deep(.v-card-text) {
  line-height: 1.6;
}

:deep(.v-card-title mark),
:deep(.v-card-subtitle mark),
:deep(.v-card-text mark),
.highlight-text :deep(mark) {
  background-color: rgba(var(--v-theme-warning), 0.2);
  color: inherit;
  padding: 0 2px;
  border-radius: 2px;
  font-weight: 500;
}
</style>
