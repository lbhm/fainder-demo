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
                <div class="d-flex align-center">
                  <v-img
                    :src="item.thumbnailUrl || '/FAINDER_LOGO_SVG_01.svg'"
                    :alt="item.name"
                    height="100"
                    width="100"
                    cover
                    class="flex-shrink-0"
                  >
                    <!-- Fallback for failed image load -->
                    <template v-slot:placeholder>
                      <v-icon size="48" color="grey-lighten-2">mdi-image</v-icon>
                    </template>
                  </v-img>
                  <div class="flex-grow-1">
                    <v-card-title class="text-truncate"><strong>{{ item.name }}</strong></v-card-title>
                    <v-card-subtitle class="text-truncate">{{ item.alternateName }}</v-card-subtitle>
                  </div>
                </div>
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
              <div class="d-flex align-center pa-4">
                <div class="flex-grow-1">
                  <v-card-title><strong>{{ selectedResult.name }}</strong></v-card-title>
                  <v-card-subtitle>{{ selectedResult.alternateName }}</v-card-subtitle>
                  <v-card-subtitle><strong>Creator:</strong> {{selectedResult.creator.name }}</v-card-subtitle>
                  <v-card-subtitle><strong>License:</strong> {{selectedResult.license.name }}</v-card-subtitle>
                  <v-card-subtitle><strong>Published:</strong> {{selectedResult.datePublished.substring(0, 10) }}</v-card-subtitle>
                  <v-card-subtitle><strong>Modified:</strong> {{selectedResult.dateModified.substring(0, 10) }}</v-card-subtitle>
                </div>
                <v-img
                  :src="selectedResult.thumbnailUrl || '/FAINDER_LOGO_SVG_01.svg'"
                  :alt="selectedResult.name"
                  height="150"
                  width="150"
                  cover
                  class="flex-shrink-0 ml-4"
                >
                  <!-- Fallback for failed image load -->
                  <template v-slot:placeholder>
                    <v-icon size="48" color="grey-lighten-2">mdi-image</v-icon>
                  </template>
                </v-img>
              </div>

              <v-expansion-panels v-model="descriptionPanel">
                <v-expansion-panel>
                  <v-expansion-panel-title class="panel-title"
                    >Description</v-expansion-panel-title
                  >
                  <v-expansion-panel-text>
                    <div class="markdown-wrapper">
                      <div :class="{ 'description-truncated': !showFullDescription && isLongDescription }">
                        <MDC :value="displayedContent" />
                      </div>
                      <v-btn
                        v-if="isLongDescription"
                        variant="text"
                        density="comfortable"
                        class="mt-2 text-medium-emphasis"
                        @click="toggleDescription"
                      >
                        {{ showFullDescription ? 'Show less' : 'Show more' }}
                        <v-icon :icon="showFullDescription ? 'mdi-chevron-up' : 'mdi-chevron-down'" class="ml-1" />
                      </v-btn>
                    </div>
                  </v-expansion-panel-text>
                </v-expansion-panel>
              </v-expansion-panels>

              <v-expansion-panels v-if="selectedResult?.recordSet?.length > 0" v-model="recordSetPanel">
                <v-expansion-panel>
                  <v-expansion-panel-title class="panel-title">
                    Data Explorer
                  </v-expansion-panel-title>
                  <v-expansion-panel-text>
                  <div v-if="selectedFile">
                    <div class="d-flex align-center mb-4">
                      <v-select
                        v-model="selectedFileIndex"
                        :items="recordSetItems"
                        label="Select File"
                        density="comfortable"
                        hide-details
                        class="max-w-xs"
                      />
                    </div>
                    <div class="field-list">
                      <div v-for="(field, fieldIndex) in selectedFile.field" :key="field.id" class="field-item mb-6">
                        <div class="field-header mb-2">
                          <span class="text-h6">{{ field.name }}:</span>
                          <span class="text-subtitle-1 ml-2">{{ field.dataType[0] }}</span>
                        </div>
                        <div v-if="field.histogram" class="histogram-container" style="height: 300px;">
                          <Bar
                            :chart-data="getChartData(field, fieldIndex)"
                            :chart-options="chartOptions"
                          />
                        </div>
                      </div>
                    </div>
                  </div>
                  </v-expansion-panel-text>
                </v-expansion-panel>
              </v-expansion-panels>
              <v-expansion-panels v-model="metadataPanel">
                <v-expansion-panel>
                  <v-expansion-panel-title class="panel-title">Metadata</v-expansion-panel-title>
                  <v-expansion-panel-text>
                    <v-table>
                      <tbody>
                        <tr>
                          <td><strong>Creator</strong></td>
                          <td>{{ selectedResult?.creator?.name || '-' }}</td>
                        </tr>
                        <tr>
                          <td><strong>Publisher</strong></td>
                          <td>{{ selectedResult?.publisher?.name || '-' }}</td>
                        </tr>
                        <tr>
                          <td><strong>License</strong></td>
                          <td>{{ selectedResult?.license?.name || '-' }}</td>
                        </tr>
                        <tr>
                          <td><strong>Date Published</strong></td>
                          <td>{{ selectedResult?.datePublished.substring(0, 10) || '-' }}</td>
                        </tr>
                        <tr>
                          <td><strong>Date Modified</strong></td>
                          <td>{{ selectedResult?.dateModified.substring(0, 10) || '-' }}</td>
                        </tr>
                        <tr>
                          <td><strong>Keywords</strong></td>
                          <td style="white-space: pre-line">{{ selectedResult?.keywords?.join('\n') || '-' }}</td>
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

const descriptionPanel = ref([0]); // Array with 0 means first panel is open
const recordSetPanel = ref([0]);  // Single panel
const totalVisible = ref(7);
const selectedFileIndex = ref(0);


const showFullDescription = ref(false);
const maxLength = 1000;

const isLongDescription = computed(() => {
  return selectedResult.value?.description?.length > maxLength;
});

const displayedContent = computed(() => {
  if (!selectedResult.value?.description) return '';
  if (!isLongDescription.value || showFullDescription.value) {
    return selectedResult.value.description;
  }
  return selectedResult.value.description.slice(0, maxLength) + '...';
});

const toggleDescription = () => {
  showFullDescription.value = !showFullDescription.value;
};

// Computed property for dropdown items
const recordSetItems = computed(() => {
  if (!selectedResult.value?.recordSet) return [];
  return selectedResult.value.recordSet.map((file, index) => ({
    title: file.name,
    value: index,
  }));
});

// Computed property for the currently selected file
const selectedFile = computed(() => {
  if (!selectedResult.value?.recordSet) return null;
  return selectedResult.value.recordSet[selectedFileIndex.value];
});

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
    selectedFileIndex.value = 0; // Reset to first file when selecting new result
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
    },
    y: {
      beginAtZero: true,
    }
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
        }
      }
    },
    legend: {
      display: false
    }
  },
  responsive: true,
  maintainAspectRatio: false,
  layout: {
    padding: {
      left: 10,
      right: 30,
      top: 10,
      bottom: 20
    }
  }
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
  font-weight: bold;
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

.description-truncated {
  position: relative;
  max-height: 200px;
  overflow: hidden;
}

.description-truncated::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 50px;
  background: linear-gradient(transparent, rgb(var(--v-theme-surface)));
}

.field-list {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.field-item {
  background-color: rgb(var(--v-theme-surface));
  border-radius: 8px;
  padding: 16px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}

.field-header {
  display: flex;
  align-items: baseline;
}

.histogram-container {
  margin-top: 12px;
  border-radius: 4px;
  overflow: hidden;
}
</style>
