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
                    max-height="100"
                    max-width="100"
                    cover
                    class="flex-shrink-0"
                  >
                    <!-- Fallback for failed image load -->
                    <template v-slot:placeholder>
                      <v-icon size="48" color="grey-lighten-2">mdi-image</v-icon>
                    </template>
                  </v-img>
                  <div class="flex-grow-1 min-w-0">
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
                  <!-- Wrap title, subtitle, and download in a container with consistent padding -->
                  <div class="content-container">
                    <v-card-title><strong>{{ selectedResult.name }}</strong></v-card-title>
                    <v-card-subtitle>{{ selectedResult.alternateName }}</v-card-subtitle>

                    <!-- Download section -->
                    <div v-if="selectedResult.distribution?.length" class="mt-2">
                      <!-- Single file case -->
                      <v-btn
                        v-if="selectedResult.distribution.length === 1"
                        :href="selectedResult.distribution[0].contentUrl"
                        target="_blank"
                        color="primary"
                        prepend-icon="mdi-download"
                        variant="tonal"
                        class="download-btn"
                      >
                        Download {{ selectedResult.distribution[0].name }}
                        <template v-if="selectedResult.distribution[0].contentSize" #append>
                          ({{ selectedResult.distribution[0].contentSize }})
                        </template>
                      </v-btn>

                      <!-- Multiple files case -->
                      <v-menu
                        v-else
                        location="bottom"
                      >
                        <template v-slot:activator="{ props }">
                          <v-btn
                            color="primary"
                            v-bind="props"
                            prepend-icon="mdi-download"
                            variant="tonal"
                            class="download-btn"
                          >
                            Download
                          </v-btn>
                        </template>

                        <v-list>
                          <v-list-item
                            v-for="file in selectedResult.distribution"
                            :key="file['@id']"
                            :href="file.contentUrl"
                            target="_blank"
                            :title="file.description"
                          >
                            <v-list-item-title>
                              {{ file.name }}
                            </v-list-item-title>
                            <v-list-item-subtitle>
                              {{ file.encodingFormat }}
                              <template v-if="file.contentSize">
                                ({{ file.contentSize }})
                              </template>
                            </v-list-item-subtitle>
                          </v-list-item>
                        </v-list>
                      </v-menu>
                    </div>
                  </div>
                </div>
                <v-img
                  :src="selectedResult.thumbnailUrl || '/FAINDER_LOGO_SVG_01.svg'"
                  :alt="selectedResult.name"
                  height="150"
                  width="150"
                  cover
                  class="flex-shrink-0 ml-4"
                >
                  <template v-slot:placeholder>
                    <v-icon size="48" color="grey-lighten-2">mdi-image</v-icon>
                  </template>
                </v-img>
              </div>

              <v-expansion-panels v-model="descriptionPanel">
                <v-expansion-panel>
                  <v-expansion-panel-title class="panel-title">Details</v-expansion-panel-title>
                  <v-expansion-panel-text>
                    <div class="content-wrapper">
                      <div class="description-section">
                        <MDC :value="displayedContent" />
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

                      <div class="metadata-section">
                        <div class="metadata-item">
                          <span class="metadata-label">Creator</span>
                          <span class="metadata-value">{{ selectedResult?.creator?.name || '-' }}</span>
                        </div>
                        <div class="metadata-item">
                          <span class="metadata-label">License</span>
                          <span class="metadata-value">{{ selectedResult?.license?.name || '-' }}</span>
                        </div>
                        <div class="metadata-item">
                          <span class="metadata-label">Keywords</span>
                          <span class="metadata-value keywords-value">{{ processedKeywords.join(', ') || '-' }}</span>
                        </div>
                      </div>
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
                        <!-- Numerical Data with Histogram -->
                        <div v-if="field.histogram" class="field-content">
                          <div class="histogram-container">
                            <Bar
                              :chart-data="getChartData(field, fieldIndex)"
                              :chart-options="chartOptions"
                            />
                          </div>
                          <div class="statistics-container">
                            <table class="statistics-table">
                              <tbody>
                                <tr>
                                  <td class="stat-label">Count:</td>
                                  <td class="stat-value">{{ formatNumber(field.statistics.count) }}</td>
                                </tr>
                                <tr>
                                  <td class="stat-label">Mean:</td>
                                  <td class="stat-value">{{ formatNumber(field.statistics.mean) }}</td>
                                </tr>
                                <tr>
                                  <td class="stat-label">Std Dev:</td>
                                  <td class="stat-value">{{ formatNumber(field.statistics.std) }}</td>
                                </tr>
                                <tr>
                                  <td class="stat-label">Min:</td>
                                  <td class="stat-value">{{ formatNumber(field.statistics.min) }}</td>
                                </tr>
                                <tr>
                                  <td class="stat-label">25%:</td>
                                  <td class="stat-value">{{ formatNumber(field.statistics['25%']) }}</td>
                                </tr>
                                <tr>
                                  <td class="stat-label">Median:</td>
                                  <td class="stat-value">{{ formatNumber(field.statistics['50%']) }}</td>
                                </tr>
                                <tr>
                                  <td class="stat-label">75%:</td>
                                  <td class="stat-value">{{ formatNumber(field.statistics['75%']) }}</td>
                                </tr>
                                <tr>
                                  <td class="stat-label">Max:</td>
                                  <td class="stat-value">{{ formatNumber(field.statistics.max) }}</td>
                                </tr>
                              </tbody>
                            </table>
                          </div>
                        </div>
                        <!-- Categorical Data -->
                        <div v-else class="field-content categorical">
                          <div class="categorical-summary">
                            <table class="statistics-table">
                              <tbody>
                                <tr>
                                  <td class="stat-label">Unique Values:</td>
                                  <td class="stat-value">{{ formatNumber(field.n_unique) }}</td>
                                </tr>
                              </tbody>
                            </table>
                            <table class="statistics-table">
                              <thead>
                                <tr>
                                  <th class="text-left">Value</th>
                                  <th class="text-right">Count</th>
                                </tr>
                              </thead>
                              <tbody>
                                <template v-for="([value, count], index) in Object.entries(field.most_common).slice(0, 3)" :key="value">                                  <tr>
                                    <td class="value-label">{{ value }}</td>
                                    <td class="stat-value">{{ formatNumber(count) }}</td>
                                  </tr>
                                </template>
                              </tbody>
                            </table>
                          </div>
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
const metadataPanel = ref([0]); // Initialize metadata panel
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
          return `Density: ${item.parsed.y.toFixed(4)}`;
        }
      }
    },
    legend: {
      display: false
    }
  },
  responsive: false,
  maintainAspectRatio: false,
  layout: {
    padding: {
      left: 10,
      right: 30,
      top: 10,
      bottom: 80
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
  const densities = field.histogram.densities;

  if (densities == null || binEdges == null) return null;

  // Create array of bar objects with correct positioning and width
  const bars = densities.map((density, i) => ({
    x0: binEdges[i],     // Start of bin
    x1: binEdges[i + 1], // End of bin
    y: density           // Density
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

async function searchData({query: searchQuery}) {
  showSearchModal.value = false;
  await loadResults(searchQuery);
  query.value = searchQuery;

  return await navigateTo({
    path: '/results',
    query: {
      query: searchQuery,
      index: 0,
      theme: theme.global.name.value
    }
  });

}

const processedKeywords = computed(() => {
  if (!selectedResult.value?.keywords) return [];
  return selectedResult.value.keywords.map(keyword => {
    const parts = keyword.split(' > ');
    return parts[parts.length - 1];
  });
});

const formatNumber = (value) => {
  if (value === undefined || value === null) return '-';
  // Check if the value is an integer
  if (Number.isInteger(value)) return value.toLocaleString();
  // For floating point numbers, limit to 4 decimal places
  return Number(value).toLocaleString(undefined, {
    minimumFractionDigits: 0,
    maximumFractionDigits: 4
  });
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
  max-width: 1200px; /* Add maximum width */
  margin: 0 auto; /* Center the container */
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

.field-content {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 24px;
  align-items: start;
}

.histogram-container {
  height: 300px;
}

.statistics-container {
  background-color: rgba(var(--v-theme-surface), 0.8);
  border-radius: 8px;
  padding: 16px;
  height: fit-content;
}

.statistics-table {
  width: 100%;
  border-collapse: collapse;
}

.statistics-table tr {
  border-bottom: 1px solid rgba(var(--v-border-opacity), 0.12);
}

.statistics-table tr:last-child {
  border-bottom: none;
}

.stat-label {
  padding: 8px 0;
  font-weight: 500;
  color: rgba(var(--v-theme-on-surface), 0.7);
}

.stat-value {
  padding: 8px 0;
  text-align: right;
  font-family: monospace;
  color: rgb(var(--v-theme-on-surface));
}

.content-wrapper {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 32px;
  padding: 16px 0;
}

.description-section {
  font-size: 1rem;
  line-height: 1.6;
}

.metadata-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding-left: 32px;
  border-left: 1px solid rgba(var(--v-border-opacity), 0.12);
}

.metadata-item {
  display: grid;
  gap: 4px;
}

.metadata-label {
  font-weight: 700;
  color: rgb(var(--v-theme-on-surface));
  font-size: 1.125rem;
  margin-bottom: 4px;
}

.metadata-value {
  color: rgb(var(--v-theme-on-surface));
  font-size: 0.875rem;
}

.keywords-value {
  word-break: break-word;
}

.field-content.categorical {
  grid-template-columns: 1fr 1fr;
}

.categorical-summary {
  background-color: rgba(var(--v-theme-surface), 0.8);
  border-radius: 8px;
  padding: 16px;
}

.mt-6 {
  margin-top: 24px;
}

.value-label {
  padding: 8px 0;
  color: rgb(var(--v-theme-on-surface));
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.statistics-table thead th {
  padding: 8px 0;
  font-weight: 600;
  color: rgba(var(--v-theme-on-surface), 0.87);
  border-bottom: 2px solid rgba(var(--v-border-opacity), 0.12);
}

/* Add tooltip for truncated values */
.value-label {
  position: relative;
}

/* Make the layout responsive */
@media (max-width: 768px) {
  .content-wrapper {
    grid-template-columns: 1fr;
    gap: 24px;
  }

  .metadata-section {
    padding-left: 0;
    border-left: none;
    border-top: 1px solid rgba(var(--v-border-opacity), 0.12);
    padding-top: 24px;
  }
}

@media (max-width: 1024px) {
  .field-content {
    grid-template-columns: 1fr;
  }

  .histogram-container {
    height: 250px;
  }

  .statistics-container {
    max-width: 100%;
  }

  .field-content.categorical {
    grid-template-columns: 1fr;
  }

  .categorical-summary {
    max-width: 100%;
  }

  .value-label {
    max-width: none;
  }
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

.content-container {
  padding: 0 16px;
}

.content-container .v-card-title {
  padding-left: 0;
}

.content-container .v-card-subtitle {
  padding-left: 0;
}

.flex-grow-1.min-w-0 {
  min-width: 0;
  overflow: hidden;
}

.text-truncate {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
  display: block;
}
</style>
