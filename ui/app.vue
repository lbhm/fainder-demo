<template>
  <v-app>
    <v-app-bar :elevation="0" height="85">
      <FainderLogo
        size="medium"
        class="mr-4 ml-4 clickable"
        @click="gotoHome"
      />
      <v-spacer />

      <!-- Add search component in app bar only on results page -->
      <template v-if="route.path === '/results'">
        <Search_Component
          :key="searchComponentKey"
          :search-query="internalSearchQuery"
          :inline="true"
          :lines="1"
          :query-builder="false"
          class="app-bar-search"
          @search-data="searchData"
        />
        <v-btn
          icon
          density="compact"
          class="ml-2"
          @click="showSearchDialog = true"
        >
          <v-icon>mdi-arrow-expand</v-icon>
        </v-btn>
      </template>

      <v-spacer />

      <v-menu class="mr">
        <template #activator="{ props }">
          <v-btn icon v-bind="props">
            <v-icon>mdi-menu</v-icon>
          </v-btn>
        </template>

        <v-list>
          <v-list-item @click="navigateTo('/upload')">
            <template #prepend>
              <v-icon icon="mdi-upload" />
            </template>
            <v-list-item-title>Upload Datasets</v-list-item-title>
          </v-list-item>

          <v-list-item @click="navigateTo('/about')">
            <template #prepend>
              <v-icon icon="mdi-information" />
            </template>
            <v-list-item-title>About</v-list-item-title>
          </v-list-item>

          <v-divider class="mx-3" />

          <v-list-item @click="toggleHighlight">
            <template #prepend>
              <v-icon icon="mdi-marker" />
            </template>
            <v-list-item-title>
              {{
                syntax_highlighting
                  ? "Disable Syntax Highlight"
                  : "Enable Syntax Highlight"
              }}
            </v-list-item-title>
          </v-list-item>

          <v-list-item @click="toggleTheme">
            <template #prepend>
              <v-icon
                :icon="
                  theme.global.current.value.dark
                    ? 'mdi-weather-sunny'
                    : 'mdi-weather-night'
                "
                :color="theme.global.current.value.dark ? 'yellow' : 'indigo'"
              />
            </template>
            <v-list-item-title>
              {{ theme.global.current.value.dark ? "Light Mode" : "Dark Mode" }}
            </v-list-item-title>
          </v-list-item>
        </v-list>
      </v-menu>
    </v-app-bar>

    <!-- Add expandable search dialog -->
    <v-dialog
      v-model="showSearchDialog"
      transition="dialog-top-transition"
      max-width="56rem"
    >
      <v-card elevation="0">
        <v-toolbar dark color="primary">
          <v-btn icon dark @click="showSearchDialog = false">
            <v-icon>mdi-close</v-icon>
          </v-btn>
          <v-toolbar-title>Query Builder</v-toolbar-title>
        </v-toolbar>

        <v-container class="pt-6">
          <Search_Component
            :key="searchComponentKey"
            :search-query="route.query.query"
            :inline="false"
            :lines="6"
            :query-builder="false"
            :simple-builder="true"
            @search-data="
              (data) => {
                searchData(data);
                showSearchDialog = false;
              }
            "
          />
        </v-container>
      </v-card>
    </v-dialog>

    <NuxtLayout>
      <NuxtPage />
    </NuxtLayout>
  </v-app>
</template>

<script setup>
import { useTheme } from "vuetify";
import { useRoute } from "vue-router";

function gotoHome() {
  console.log("go to home");
  // keep everything in the query except the query string
  return navigateTo({
    path: "/",
    query: { ...route.query, query: undefined, theme: theme.global.name.value },
  });
}
const { loadResults } = useSearchOperations();
const route = useRoute();
const theme = useTheme();
const { query, fainder_mode, currentPage, selectedResultIndex } =
  useSearchState();
const colorMode = useColorMode();

const syntax_highlighting = useCookie("fainder_syntax_highlighting", {
  default: () => true,
});

const internalSearchQuery = computed(() => route.query.query);
const searchComponentKey = ref(0);

const currentTheme = route.query.theme || colorMode.value;
theme.global.name.value = currentTheme === "dark" ? "dark" : "light";

function toggleTheme() {
  theme.global.name.value =
    theme.global.name.value === "dark" ? "light" : "dark";

  navigateTo({
    path: route.path,
    query: {
      ...route.query,
      theme: theme.global.name.value,
    },
  });
}

function toggleHighlight() {
  syntax_highlighting.value = !syntax_highlighting.value;
}

const showSearchDialog = ref(false);

async function searchData({
  query: searchQuery,
  fainder_mode: newfainder_mode,
  results_highlighting,
}) {
  query.value = searchQuery;
  fainder_mode.value = newfainder_mode;

  currentPage.value = 1;
  selectedResultIndex.value = 0;

  await loadResults(searchQuery, 1, newfainder_mode, results_highlighting);

  await navigateTo({
    path: "/results",
    query: {
      query: searchQuery,
      page: 1,
      index: 0,
      fainder_mode: newfainder_mode,
      results_highlighting: results_highlighting,
      theme: theme.global.name.value,
    },
  });

  searchComponentKey.value++;
}
</script>

<style scoped>
.app-bar-search {
  max-width: 1200px; /* Increased from 800px */
  flex-grow: 1;
}

.app-bar-search :deep(.v-field) {
  border-radius: 20px;
}

.clickable {
  cursor: pointer;
}
</style>
