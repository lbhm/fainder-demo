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
          <v-infinite-scroll
            v-if="!isLoading && !error && results && results.length > 0"
            mode="manual"
          >
            <template v-for="result in results" :key="result.id">
              <v-card @click="selectResult(result)" :height="100">
                <v-card-title>{{ result.name }}</v-card-title>
                <v-card-subtitle>{{ result.alternateName }}</v-card-subtitle>
              </v-card>
            </template>
          </v-infinite-scroll>
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

// read query and theme from query params
const query = ref(q.value.query);
const selectedIndex = ref(parseInt(q.value.index) || 0);


const descriptionPanel = ref([0]); // Array with 0 means first panel is open
const recordSetPanels = ref([]); // Array of arrays for each file panel

// reset recordSetPanels and descriptionPanel when selectedResult changes

console.log(query.value);

const selectResult = (result) => {
  const index = results.value.indexOf(result);
  selectedIndex.value = index;
  selectedResult.value = result;

  if (result.recordSet) {
    descriptionPanel.value = [0];
    recordSetPanels.value = result.recordSet.map(() => [0]); // Initialize each file panel with an array containing 0
    console.log(recordSetPanels.value);
  }

  // Update URL with new index
  navigateTo({
    path: '/results',
    query: {
      query: query.value,
      index: index,
      theme: theme.global.name.value // Add theme to query
    }
  });
};

await loadResults(query.value);

async function loadResults(queryStr) {
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
        query: queryStr
      })
    });

    if (!response.ok) {
      throw new Error(`Search failed with status: ${response.status}`);
    }

    const r = await response.json();
    results.value = r.results;

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
</style>
