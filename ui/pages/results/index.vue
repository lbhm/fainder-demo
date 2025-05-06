# This results page will display the results of the search query # The list of
the results will be displayed in a card format on the left side of the page and
the details of the selected result will be displayed on the right side of the
page


import "./index.css";


<template>
  <v-main>
    <v-divider />
    <div class="pa-5">
      <!-- Error message -->
      <v-alert v-if="hasError" type="error" class="mt-4" prominent>
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
        v-if="!isLoading && !hasError && (!results || results.length === 0)"
        type="info"
        class="mt-4"
      >
        No results found for your search criteria
      </v-alert>

      <!-- Main Content -->
      <div class="results-wrapper">
        <div class="list-container">
          <!-- Add search stats -->
          <div
            v-if="!isLoading && !hasError && results && results.length > 0"
            class="search-stats mb-4"
          >
            Found {{ resultCount }} results in {{ searchTime.toFixed(4) }}s
          </div>
          <!-- Remove the Modify Search button since we have inline search now -->

          <!-- Loading state -->
          <v-progress-circular
            v-if="isLoading"
            indeterminate
            color="primary"
            class="mt-4"
          />

          <!-- Results list -->
          <v-virtual-scroll
            v-if="!isLoading && !hasError && results && results.length > 0"
            mode="manual"
            :items="results"
          >
            <template #default="{ item }">
              <v-card :height="80" elevation="0" @click="selectResult(item)">
                <div class="d-flex align-center">
                  <v-img
                    :src="item.thumbnailUrl"
                    :alt="item.name"
                    height="70"
                    width="70"
                    max-height="70"
                    max-width="70"
                    cover
                    class="flex-shrink-0 rounded-image"
                  >
                    <!-- Fallback for failed image load -->
                    <template #placeholder>
                      <v-icon size="48" color="grey-lighten-2"
                        >mdi-image</v-icon
                      >
                    </template>
                  </v-img>
                  <div class="flex-grow-1 min-w-0">
                    <v-card-title
                      class="text-truncate highlight-text"
                      v-html="'<strong>' + item.name + '</strong>'"
                    />
                    <v-card-subtitle
                      class="text-truncate highlight-text"
                      v-html="item.alternateName"
                    />
                  </div>
                </div>
              </v-card>
            </template>
          </v-virtual-scroll>

          <!-- Pagination controls -->
          <div
            v-if="!isLoading && !hasError && results && results.length > 0"
            class="pagination-controls mt-4"
          >
            <v-pagination
              v-model="currentPage"
              :length="totalPages"
              :total-visible="totalVisible"
              rounded="circle"
              width="70%"
            />
          </div>
        </div>

        <div class="details-container">
          <v-card v-if="selectedResult" elevation="0">
            <div class="d-flex align-center">
              <div class="flex-grow-1">
                <!-- Wrap title and subtitle in a container -->
                <div class="content-container">
                  <v-card-title
                    class="highlight-text"
                    v-html="'<strong>' + selectedResult.name + '</strong>'"
                  />
                  <v-card-subtitle
                    class="highlight-text"
                    v-html="selectedResult.alternateName"
                  />
                </div>
              </div>

              <div
                v-if="selectedResult.distribution?.length"
                class="flex-shrink-0"
              >
                <v-menu location="bottom">
                  <template #activator="{ props }">
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
                      v-for="file in selectedResult.distribution.filter(
                        (file) => file.contentSize,
                      )"
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
                        {{ file.contentSize }}
                      </v-list-item-subtitle>
                    </v-list-item>
                  </v-list>
                </v-menu>
              </div>
            </div>

            <v-expansion-panels v-model="descriptionPanel" elevation="0">
              <v-expansion-panel>
                <v-expansion-panel-title class="panel-title"
                  >Details</v-expansion-panel-title
                >
                <v-expansion-panel-text>
                  <div class="content-wrapper highlight-text">
                    <div class="description-section">
                      <MDC :value="displayedContent" />
                      <v-btn
                        v-if="isLongDescription"
                        variant="text"
                        density="comfortable"
                        class="mt-2 text-medium-emphasis"
                        @click="toggleDescription"
                      >
                        {{ showFullDescription ? "Show less" : "Show more" }}
                        <v-icon
                          :icon="
                            showFullDescription
                              ? 'mdi-chevron-up'
                              : 'mdi-chevron-down'
                          "
                          class="ml-1"
                        />
                      </v-btn>
                    </div>

                    <div class="metadata-section">
                      <div class="metadata-item">
                        <span class="metadata-label">Creator</span>
                        <span
                          v-if="selectedResult?.['creator-name']"
                          class="metadata-value highlight-text"
                          v-html="selectedResult?.['creator-name']"
                        />
                        <span
                          v-else
                          class="metadata-value highlight-text"
                          v-html="selectedResult?.creator?.name || '-'"
                        />
                      </div>
                      <div class="metadata-item">
                        <span class="metadata-label">License</span>
                        <span class="metadata-value">{{
                          selectedResult?.license?.name || "-"
                        }}</span>
                      </div>
                      <div class="metadata-item">
                        <span class="metadata-label">Keywords</span>
                        <span
                          class="metadata-value keywords-value"
                          v-html="selectedResult?.keywords || '-'"
                        />
                      </div>
                    </div>
                  </div>
                </v-expansion-panel-text>
              </v-expansion-panel>
            </v-expansion-panels>

            <v-expansion-panels
              v-if="(selectedResult?.recordSet ?? []).length > 0"
              v-model="recordSetPanel"
              elevation="0"
            >
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
                      <div
                        v-for="(field, fieldIndex) in selectedFile.field"
                        :key="field.id"
                        class="field-item mb-6"
                      >
                        <div class="field-header mb-2">
                          <span
                            v-if="field.marked_name"
                            class="text-h6 highlight-text"
                            v-html="field.marked_name"
                          />
                          <span v-else class="text-h6"> {{ field.name }}</span>
                          <v-chip class="ml-2" density="compact">{{
                            field.dataType[0]
                          }}</v-chip>
                        </div>
                        <!-- Numerical Data with Histogram -->
                        <div v-if="field.histogram" class="field-content">
                          <div class="histogram-container">
                            <Bar
                              :data="
                                getChartData(field, fieldIndex) || {
                                  datasets: [],
                                }
                              "
                              :options="chartOptions"
                            />
                          </div>
                          <div
                            v-if="field.statistics"
                            class="statistics-container"
                          >
                            <table class="statistics-table">
                              <tbody>
                                <tr>
                                  <td class="stat-label">Count:</td>
                                  <td class="stat-value">
                                    {{ formatNumber(field.statistics.count) }}
                                  </td>
                                </tr>
                                <tr>
                                  <td class="stat-label">Mean:</td>
                                  <td class="stat-value">
                                    {{ formatNumber(field.statistics.mean) }}
                                  </td>
                                </tr>
                                <tr>
                                  <td class="stat-label">Std Dev:</td>
                                  <td class="stat-value">
                                    {{ formatNumber(field.statistics.std) }}
                                  </td>
                                </tr>
                                <tr>
                                  <td class="stat-label">Min:</td>
                                  <td class="stat-value">
                                    {{ formatNumber(field.statistics.min) }}
                                  </td>
                                </tr>
                                <tr>
                                  <td class="stat-label">25%:</td>
                                  <td class="stat-value">
                                    {{ formatNumber(field.statistics["25%"]) }}
                                  </td>
                                </tr>
                                <tr>
                                  <td class="stat-label">Median:</td>
                                  <td class="stat-value">
                                    {{ formatNumber(field.statistics["50%"]) }}
                                  </td>
                                </tr>
                                <tr>
                                  <td class="stat-label">75%:</td>
                                  <td class="stat-value">
                                    {{ formatNumber(field.statistics["75%"]) }}
                                  </td>
                                </tr>
                                <tr>
                                  <td class="stat-label">Max:</td>
                                  <td class="stat-value">
                                    {{ formatNumber(field.statistics.max) }}
                                  </td>
                                </tr>
                              </tbody>
                            </table>
                          </div>
                        </div>
                        <!-- Boolean Data -->
                        <div
                          v-else-if="
                            field.counts?.Yes !== undefined &&
                            field.counts?.No !== undefined
                          "
                          class="field-content boolean"
                        >
                          <div class="boolean-summary">
                            <Bar
                              :data="getBooleanChartData(field)"
                              :options="booleanChartOptions"
                            />
                          </div>
                        </div>
                        <!-- Date Data -->
                        <div
                          v-else-if="field.min_date && field.max_date"
                          class="field-content date"
                        >
                          <div class="date-timeline">
                            <div class="timeline-container">
                              <div class="timeline-wrapper">
                                <div class="timeline-bar">
                                  <div class="timeline-start">
                                    {{ formatDate(field.min_date) }}
                                  </div>
                                  <div class="timeline-line" />
                                  <div class="timeline-end">
                                    {{ formatDate(field.max_date) }}
                                  </div>
                                </div>
                                <div class="timeline-duration">
                                  {{
                                    calculateDateDifference(
                                      field.min_date,
                                      field.max_date,
                                    )
                                  }}
                                </div>
                              </div>
                            </div>
                          </div>
                          <div class="date-statistics">
                            <table class="statistics-table">
                              <tbody>
                                <tr>
                                  <td class="stat-label">Earliest Date:</td>
                                  <td class="stat-value">
                                    {{ formatDateFull(field.min_date) }}
                                  </td>
                                </tr>
                                <tr>
                                  <td class="stat-label">Latest Date:</td>
                                  <td class="stat-value">
                                    {{ formatDateFull(field.max_date) }}
                                  </td>
                                </tr>
                                <tr v-if="field.unique_dates !== undefined">
                                  <td class="stat-label">Unique Dates:</td>
                                  <td class="stat-value">
                                    {{ formatNumber(field.unique_dates) }}
                                  </td>
                                </tr>
                                <tr>
                                  <td class="stat-label">Time Span:</td>
                                  <td class="stat-value">
                                    {{
                                      calculateDateDifference(
                                        field.min_date,
                                        field.max_date,
                                        true,
                                      )
                                    }}
                                  </td>
                                </tr>
                              </tbody>
                            </table>
                          </div>
                        </div>
                        <!-- Categorical Data -->
                        <div v-else class="field-content categorical">
                          <div class="categorical-summary">
                            <div class="categorical-layout">
                              <div class="unique-values-section">
                                <div v-if="field.n_unique" class="large-stat">
                                  <div class="stat-title">Unique Values</div>
                                  <div class="stat-number">
                                    {{ formatNumber(field.n_unique) }}
                                  </div>
                                </div>
                              </div>
                              <div class="value-distribution">
                                <table
                                  v-if="field.most_common"
                                  class="statistics-table"
                                >
                                  <thead>
                                    <tr>
                                      <th class="text-left">
                                        Most Common Values
                                      </th>
                                      <th class="text-right">Count</th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    <template
                                      v-for="[value, count] in Object.entries(
                                        field.most_common,
                                      ).slice(0, 3)"
                                      :key="value"
                                    >
                                      <tr>
                                        <td class="value-label">{{ value }}</td>
                                        <td class="stat-value">
                                          {{ formatNumber(count) }}
                                        </td>
                                      </tr>
                                    </template>
                                  </tbody>
                                </table>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </v-expansion-panel-text>
              </v-expansion-panel>
            </v-expansion-panels>
            <v-expansion-panels v-model="metadataPanel" elevation="0">
              <v-expansion-panel>
                <v-expansion-panel-title class="panel-title"
                  >Metadata</v-expansion-panel-title
                >
                <v-expansion-panel-text>
                  <v-table>
                    <tbody>
                      <tr>
                        <td><strong>Creator</strong></td>
                        <td
                          v-if="selectedResult?.['creator-name']"
                          class="highlight-text"
                          v-html="selectedResult?.['creator-name']"
                        />
                        <td
                          v-else
                          class="highlight-text"
                          v-html="selectedResult?.creator?.name || '-'"
                        />
                      </tr>
                      <tr>
                        <td><strong>Publisher</strong></td>
                        <td
                          v-if="selectedResult?.['publisher-name']"
                          class="highlight-text"
                          v-html="selectedResult?.['publisher-name']"
                        />
                        <td
                          v-else
                          class="highlight-text"
                          v-html="selectedResult?.publisher?.name || '-'"
                        />
                      </tr>
                      <tr>
                        <td><strong>License</strong></td>
                        <td
                          class="highlight-text"
                          v-html="selectedResult?.license?.name || '-'"
                        />
                      </tr>
                      <tr>
                        <td><strong>Date Published</strong></td>
                        <td
                          class="highlight-text"
                          v-html="
                            selectedResult?.datePublished?.substring(0, 10) ||
                            '-'
                          "
                        />
                      </tr>
                      <tr>
                        <td><strong>Date Modified</strong></td>
                        <td
                          class="highlight-text"
                          v-html="
                            selectedResult?.dateModified?.substring(0, 10) ||
                            '-'
                          "
                        />
                      </tr>
                      <tr>
                        <td><strong>Keywords</strong></td>
                        <td
                          style="white-space: pre-line"
                          class="highlight-text"
                          v-html="selectedResult?.keywords || '-'"
                        />
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
  </v-main>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from "vue";
import { Bar } from "vue-chartjs";
import { useTheme } from "vuetify";
import { useRoute, navigateTo } from "#imports";
import { useSearchState } from "~/composables/useSearchState";
import { useSearchOperations } from "~/composables/useSearchOperations";
import * as Types from "~/types/types";

const route = useRoute();
const theme = useTheme();
const searchOperations = useSearchOperations();

// Use the search state
const {
  results,
  selectedResultIndex,
  isLoading,
  error,
  searchTime,
  resultCount,
  currentPage,
  totalPages,
  query,
  fainder_mode,
  perPage,
  enable_highlighting,
} = useSearchState();

console.log(selectedResultIndex.value);

// Add computed for selected result
const selectedResult = computed<Types.Result | null>(() =>
  results.value ? results.value[selectedResultIndex.value] : null,
);

// Initialize state from route
query.value = Array.isArray(route.query.query)
  ? route.query.query[0] || ""
  : route.query.query || "";
fainder_mode.value = Array.isArray(route.query.fainder_mode)
  ? route.query.fainder_mode[0] || "low_memory"
  : route.query.fainder_mode || "low_memory";

const descriptionPanel = ref<number[]>([0]); // Array with 0 means first panel is open
const recordSetPanel = ref<number[]>([0]); // Single panel
const metadataPanel = ref<number[]>([0]); // Initialize metadata panel
const totalVisible = ref<number>(7);
const selectedFileIndex = ref<number>(0);

const showFullDescription = ref<boolean>(false);
const maxLength = 750;

const isLongDescription = computed(() => {
  return (selectedResult.value?.description ?? "").length > maxLength;
});

const displayedContent = computed(() => {
  if (!selectedResult.value?.description) return "Description missing";
  if (!isLongDescription.value || showFullDescription.value) {
    return selectedResult.value.description;
  }
  return selectedResult.value.description.slice(0, maxLength) + "...";
});

const toggleDescription = () => {
  showFullDescription.value = !showFullDescription.value;
};

const hasError = computed(() => {
  if (!error) return true;
  return error.value.message != "";
});

// Computed property for dropdown items
const recordSetItems = computed(() => {
  if (!selectedResult.value?.recordSet) return [];
  return selectedResult.value.recordSet.map((file, index) => ({
    title: file.name,
    value: index,
  }));
});

// Computed property for the currently selected file
const selectedFile = computed<Types.RecordSetFile | null>(() => {
  if (!selectedResult.value?.recordSet) return null;
  return selectedResult.value.recordSet[selectedFileIndex.value];
});

const calculatePerPage = (height: number): number => {
  const availableHeight = height - headerHeight - paginationHeight;
  const itemsPerPage = Math.floor(availableHeight / itemHeight);
  // Ensure we show at least 3 items and at most 15 items
  return Math.max(3, Math.min(15, itemsPerPage));
};

// Add ref for window height
const windowHeight = ref<number>(window.innerHeight);
const itemHeight = 80; // Height of each result card in pixels
const headerHeight = 200; // Approximate height of header elements (search + stats)
const paginationHeight = 56; // Height of pagination controls

// Set initial perPage value
perPage.value = calculatePerPage(windowHeight.value);

// Update perPage when the window height changes
watch(windowHeight, (newHeight) => {
  perPage.value = calculatePerPage(newHeight);
  // reload results with new perPage value
  if (query.value) {
    searchOperations.loadResults(
      query.value,
      currentPage.value,
      fainder_mode.value,
      enable_highlighting.value,
    );
  }
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
    fainder_mode.value,
    enable_highlighting.value,
  );

  // Update URL with new page
  navigateTo({
    path: "/results",
    query: {
      query: query.value,
      page: newPage,
      index: selectedResultIndex.value,
      fainder_mode: fainder_mode.value,
      enable_highlighting: enable_highlighting.value.toString(),
      theme: theme.global.name.value,
    },
  });
});

const selectResult = (result: Types.Result) => {
  const index = results.value
    ? (results.value as Types.Result[]).indexOf(result)
    : -1;
  selectedResultIndex.value = index;

  if (result.recordSet) {
    descriptionPanel.value = [0];
    recordSetPanel.value = result.recordSet.map(() => 0);
    showFullDescription.value = false;
    selectedFileIndex.value = 0; // Reset to first file when selecting new result
  }

  // Update URL with all necessary parameters
  navigateTo({
    path: "/results",
    query: {
      ...route.query, // Keep existing query parameters
      index: index, // Update index
    },
  });
};

// Initialize from route on mount
onMounted(() => {
  if (route.query.index && results.value) {
    const index = parseInt(route.query.index as string);
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
    fainder_mode.value,
    enable_highlighting.value,
  );
};

// Initial load
await searchOperations.loadResults(
  query.value,
  currentPage.value,
  fainder_mode.value,
  enable_highlighting.value,
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
        text: "Bins",
        font: {
          size: 11,
        },
        padding: {
          top: 10,
        },
      },
    },
    y: {
      beginAtZero: true,
      title: {
        display: true,
        text: "Density",
        font: {
          size: 11,
        },
        padding: {
          right: 10,
        },
      },
    },
  },
  plugins: {
    tooltip: {
      callbacks: {
        title: (items: any) => {
          if (!items.length) return "";
          const item = items[0];
          const index = item.dataIndex;
          const dataset = item.chart.data.datasets[0];
          const binEdges = dataset.binEdges;
          return `Range: ${binEdges[index].toFixed(2)} - ${binEdges[
            index + 1
          ].toFixed(2)}`;
        },
        label: (item: any) => {
          return `Density: ${item.parsed.y.toFixed(4)}`;
        },
      },
    },
    legend: {
      display: false,
    },
  },
  responsive: true,
  maintainAspectRatio: false,
  layout: {
    padding: {
      left: 10,
      right: 30,
      top: 10,
      bottom: 80,
    },
  },
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

const getChartData = (field: Types.Field, index: number) => {
  if (!field.histogram) return null;

  const binEdges = field.histogram.bins;
  const densities = field.histogram.densities;

  if (densities == null || binEdges == null) return null;

  // Create array of bar objects with correct positioning and width
  const bars = densities.map((density, i) => ({
    x0: binEdges[i], // Start of bin
    x1: binEdges[i + 1], // End of bin
    y: density, // Density
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
          backgroundColor: (_: any) => chartColors[index % chartColors.length],
        },
        parsing: {
          xAxisKey: "x0",
          yAxisKey: "y",
        },
      },
    ],
  };
};

const getBooleanChartData = (field: Types.Field) => {
  return {
    labels: ["True", "False"],
    datasets: [
      {
        label: field.name,
        backgroundColor: [
          "rgba(77, 182, 172, 0.6)",
          "rgba(248, 121, 121, 0.6)",
        ], // Teal for true, Red for false
        borderColor: "rgba(0, 0, 0, 0.1)",
        borderWidth: 1,
        borderRadius: 0,
        data: [field.counts?.Yes ?? 0, field.counts?.No ?? 0],
      },
    ],
  };
};

const booleanChartOptions = ref({
  scales: {
    y: {
      beginAtZero: true,
      title: {
        display: true,
        text: "Count",
        font: {
          size: 11,
        },
        padding: {
          right: 10,
        },
      },
    },
    x: {
      title: {
        display: true,
        text: "Value",
        font: {
          size: 11,
        },
        padding: {
          top: 10,
        },
      },
    },
  },
  plugins: {
    tooltip: {
      callbacks: {
        label: (context: any) => {
          return `${context.dataset.label}: ${context.raw}`;
        },
      },
    },
    legend: {
      display: false,
    },
  },
  responsive: true,
  maintainAspectRatio: false,
  layout: {
    padding: {
      left: 10,
      right: 30,
      top: 10,
      bottom: 80,
    },
  },
});

const formatNumber = (value: number | null | undefined): string => {
  if (value === undefined || value === null) return "-";
  // Check if the value is an integer
  if (Number.isInteger(value)) return value.toLocaleString();
  // For floating point numbers, limit to 4 decimal places
  return Number(value).toLocaleString(undefined, {
    minimumFractionDigits: 0,
    maximumFractionDigits: 4,
  });
};

// Format date as YYYY-MM-DD
const formatDate = (dateString: string | undefined): string => {
  if (!dateString) return "-";
  const date = new Date(dateString);
  if (isNaN(date.getTime())) return dateString; // Return as-is if invalid

  return date.toISOString().split("T")[0];
};

// Format date with both date and time
const formatDateFull = (dateString: string | undefined): string => {
  if (!dateString) return "-";
  const date = new Date(dateString);
  if (isNaN(date.getTime())) return dateString; // Return as-is if invalid

  const options = {
    year: "numeric" as const,
    month: "long" as const,
    day: "numeric" as const,
  };

  return new Intl.DateTimeFormat("en-US", options).format(date);
};

// Calculate the difference between two dates in a human-readable format
const calculateDateDifference = (
  startDateStr: string | undefined,
  endDateStr: string | undefined,
  detailed = false,
): string => {
  if (!startDateStr || !endDateStr) return "-";

  const startDate = new Date(startDateStr);
  const endDate = new Date(endDateStr);

  if (isNaN(startDate.getTime()) || isNaN(endDate.getTime())) {
    return "Invalid date range";
  }

  // Calculate difference in milliseconds
  const diffMs = Math.abs(endDate.getTime() - startDate.getTime());

  // Convert to days, months, years
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  const diffMonths = Math.floor(diffDays / 30.44); // Average days in a month
  const diffYears = Math.floor(diffDays / 365.25); // Account for leap years

  if (!detailed) {
    // Simple format for timeline display
    if (diffYears > 0) {
      return `${diffYears} year${diffYears !== 1 ? "s" : ""}`;
    } else if (diffMonths > 0) {
      return `${diffMonths} month${diffMonths !== 1 ? "s" : ""}`;
    } else {
      return `${diffDays} day${diffDays !== 1 ? "s" : ""}`;
    }
  } else {
    // Detailed format for statistics table
    const remainingMonths = diffMonths % 12;
    const remainingDays = diffDays % 30;

    let result = "";

    if (diffYears > 0) {
      result += `${diffYears} year${diffYears !== 1 ? "s" : ""} `;
    }

    if (remainingMonths > 0) {
      result += `${remainingMonths} month${remainingMonths !== 1 ? "s" : ""} `;
    }

    if (remainingDays > 0 || result === "") {
      result += `${remainingDays} day${remainingDays !== 1 ? "s" : ""}`;
    }

    return result.trim();
  }
};
</script>

