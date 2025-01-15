# This results page will display the results of the search query # The list of
the results will be displayed in a card format on the left side of the page and
the details of the selected result will be displayed on the right side of the
page

<template>
  <div class="pa-400">
    <div class="app-container pa-10">
      <!-- Inline Search Component -->
      <div class="search-container">
        <Search_Component
          :searchQuery="query"
          :inline="true"
          @searchData="searchData"
        />
      </div>

      <!-- Main Content -->
      <div class="results-wrapper">
        <div class="list-container">
          <!-- Add search stats -->
          <div v-if="!isLoading && !error && results && results.length > 0" class="search-stats mb-4">
            Found {{ resultCount }} results in {{ (searchTime).toFixed(4) }}s
          </div>

          <!-- Remove the Modify Search button since we have inline search now -->

          <!-- Loading state -->
          <v-progress-circular
            v-if="isLoading"
            indeterminate
            color="primary"
            class="mt-4"
          ></v-progress-circular>

          <!-- Error message -->
          <v-alert
            v-if="error"
            type="error"
            class="mt-4"
            prominent
          >
            <v-alert-title>Error</v-alert-title>
            {{ error }}
          </v-alert>

          <!-- Empty results message -->
          <v-alert
            v-if="!isLoading && !error && (!results || results.length === 0)"
            type="info"
            class="mt-4"
          >
            No results found for your search criteria
          </v-alert>

          <!-- Results list -->
          <v-virtual-scroll
            v-if="!isLoading && !error && results && results.length > 0"
            mode="manual"
            :items="results"
          >
            <template v-slot:default="{ item }">
              <v-card @click="selectResult(item)" :height="100">
                <v-card-title>{{ item.name }}</v-card-title>
                <v-card-subtitle>{{ item.alternateName }}</v-card-subtitle>
              </v-card>
            </template>
          </v-virtual-scroll>

          <!-- Pagination controls -->
          <div v-if="!isLoading && !error && results && results.length > 0" class="pagination-controls mt-4">
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
              <v-card-title>{{ selectedResult.name }}</v-card-title>
              <v-card-subtitle>{{ selectedResult.alternateName }}</v-card-subtitle>

              <v-expansion-panels v-model="descriptionPanel">
                <v-expansion-panel>
                  <v-expansion-panel-title class="panel-title">Description</v-expansion-panel-title>
                  <v-expansion-panel-text>
                    <div class="markdown-wrapper">
                      <MDC :value="selectedResult.description"></MDC>
                    </div>
                  </v-expansion-panel-text>
                </v-expansion-panel>
              </v-expansion-panels>

              <v-expansion-panels v-if="selectedResult.recordSet"v-for="(file, index) in selectedResult.recordSet" :key="file.id" v-model="recordSetPanels[index]">
                <v-expansion-panel>
                  <v-expansion-panel-title class="panel-title">{{ "file: " + file.name }}</v-expansion-panel-title>
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
                        <tr v-for="(field, fieldIndex) in file.field" :key="field.id">
                          <td>{{ field.name }}</td>
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
  </div>
</template>

<script setup>

import { Bar } from 'vue-chartjs'
import { useTheme } from 'vuetify'

const runtimeConfig = useRuntimeConfig();

const results = ref(null);
const selectedResult = ref(null);
const showSearchModal = ref(false);
const isLoading = ref(false);
const error = ref(null);
const theme = useTheme();

const route = useRoute();
const q = ref(route.query);

// read query, page and theme from query params
const query = ref(q.value.query);
const selectedIndex = ref(parseInt(q.value.index) || 0);
const currentPage = ref(parseInt(q.value.page) || 1);

const descriptionPanel = ref([0]); // Array with 0 means first panel is open
const recordSetPanels = ref([]); // Array of arrays for each file panel

// reset recordSetPanels and descriptionPanel when selectedResult changes

console.log(query.value);

// Add new refs for search stats
const searchTime = ref(0);
const resultCount = ref(0);

const totalPages = ref(1);
// Remove static perPage constant
const totalVisible = ref(7);

// Add ref for window height
const windowHeight = ref(window.innerHeight);
const itemHeight = 100; // Height of each result card in pixels
const headerHeight = 200; // Approximate height of header elements (search + stats)
const paginationHeight = 56; // Height of pagination controls

// Update perPage to be calculated based on available height
const perPage = computed(() => {
  const availableHeight = windowHeight.value - headerHeight - paginationHeight;
  const itemsPerPage = Math.floor(availableHeight / itemHeight);
  // Ensure we show at least 3 items and at most 15 items
  return Math.max(3, Math.min(15, itemsPerPage));
});

const handleResize = () => {
  updateTotalVisible();
  windowHeight.value = window.innerHeight;
};
// Add window resize handler
onMounted(() => {
  updateTotalVisible();
  window.addEventListener('resize', handleResize);
  windowHeight.value = window.innerHeight; // Initial value
});

onUnmounted(() => {
  window.removeEventListener('resize', handleResize);
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
  await loadResults(query.value, newPage);
  // Update URL with new page
  navigateTo({
    path: '/results',
    query: {
      query: query.value,
      page: newPage,
      index: selectedIndex.value,
      theme: theme.global.name.value
    }
  });
});

const selectResult = (result) => {
  const index = results.value.indexOf(result);
  selectedIndex.value = index;
  selectedResult.value = result;

  if (result.recordSet) {
    descriptionPanel.value = [0];
    recordSetPanels.value = result.recordSet.map(() => [0]); // Initialize each file panel with an array containing 0
    console.log(recordSetPanels.value);
  }

  // Update URL keeping the page parameter
  navigateTo({
    path: '/results',
    query: {
      query: query.value,
      page: currentPage.value,
      index: index,
      theme: theme.global.name.value
    }
  });
};

await loadResults(query.value, currentPage.value);

async function loadResults(queryStr, page = 1) {
  isLoading.value = true;
  error.value = null;

  try {
    const response = await fetch(`${runtimeConfig.public.apiBase}/query`, {
      method: 'POST',
      mode: 'cors',
      credentials: 'include',
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*'
      },
      body: JSON.stringify({
        query: queryStr,
        page: page,
        per_page: perPage.value  // Access the computed value here
      })
    });

    if (!response.ok) {
      throw new Error(`Search failed with status: ${response.status}`);
    }

    const r = await response.json();
    results.value = r.results;
    searchTime.value = r.search_time_ms;
    resultCount.value = r.result_count;
    totalPages.value = r.total_pages;
    currentPage.value = r.page;

    if (results.value && results.value.length > 0) {
      if (results.value[selectedIndex.value]){
        selectResult(results.value[selectedIndex.value]);
      } else {
        selectResult(results.value[0]);
      }
    } else {
      results.value = null;
      selectedResult.value = null;
    }
  } catch (e) {
    error.value = e.message;
    results.value = null;
    selectedResult.value = null;
  } finally {
    isLoading.value = false;
  }
}

const chartOptions = ref({
  scales: {
    x: {
      type: 'linear',
      offset: false,
      grid: {
        offset: false
      },
      title: {
        display: true,
        text: 'Value',
        font: {
          size: 14
        }
      }
    },
    y: {
      beginAtZero: true,
      title: {
        display: true,
        text: 'Density',
        font: {
          size: 14
        }
      }
    }
  },
  plugins: {
    tooltip: {
      callbacks: {
        title: (items) => {
          if (!items.length) return '';
          const item = items[0];
          const index = item.dataIndex;
          const dataset = item.chart.data.datasets[0];
          const binEdges = dataset.binEdges;
          return `Range: ${binEdges[index].toFixed(2)} - ${binEdges[index + 1].toFixed(2)}`;
        },
        label: (item) => {
          return `Count: ${item.parsed.y.toFixed(4)}`;
        }
      }
    }
  },
  responsive: true,
  maintainAspectRatio: false
});

const chartColors = [
  'rgba(248, 121, 121, 0.6)', // red
  'rgba(121, 134, 203, 0.6)', // blue
  'rgba(77, 182, 172, 0.6)',  // teal
  'rgba(255, 183, 77, 0.6)',  // orange
  'rgba(240, 98, 146, 0.6)',  // pink
  'rgba(129, 199, 132, 0.6)', // green
  'rgba(149, 117, 205, 0.6)', // purple
  'rgba(77, 208, 225, 0.6)',  // cyan
  'rgba(255, 167, 38, 0.6)',  // amber
  'rgba(186, 104, 200, 0.6)'  // purple
];

const getChartData = (field, index) => {
  if (!field.histogram) return null;

  const binEdges = field.histogram.bins;
  const counts = field.histogram.densities;

  if (counts == null || binEdges == null) return null;

  // Create array of bar objects with correct positioning and width
  const bars = counts.map((count, i) => ({
    x0: binEdges[i],         // Start of bin
    x1: binEdges[i + 1],     // End of bin
    y: count / (binEdges[i + 1] - binEdges[i])  // Density
  }));

  return {
    datasets: [{
      label: field.name,
      backgroundColor: chartColors[index % chartColors.length],
      borderColor: 'rgba(0, 0, 0, 0.1)',
      data: bars,
      binEdges: binEdges,
      borderWidth: 1,
      borderRadius: 0,
      barPercentage: 1,
      categoryPercentage: 1,
      segment: {
        backgroundColor: context => chartColors[index % chartColors.length]
      },
      parsing: {
        xAxisKey: 'x0',
        yAxisKey: 'y'
      }
    }]
  };
};



async function searchData({query: searchQuery}) {
  showSearchModal.value = false;
  currentPage.value = 1; // Reset to first page on new search
  await loadResults(searchQuery, 1);
  query.value = searchQuery;

  return await navigateTo({
    path: '/results',
    query: {
      query: searchQuery,
      page: 1,
      index: 0,
      theme: theme.global.name.value
    }
  });

}

</script>

<style scoped>
.app-container {
  display: flex;
  flex-direction: column;
  max-width: 100%;
  min-height: calc(100vh - 64px);
  padding: 16px;  /* Reduced from 24px */
  margin-top: 16px; /* Reduced from 64px */
}

.search-container {
  margin-bottom: 16px;
  background-color: rgb(var(--v-theme-surface)) !important;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  padding: 8px; /* Added padding for inner spacing */
}

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
</style>
