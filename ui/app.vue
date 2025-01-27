<template>
  <v-app>
    <v-app-bar :elevation="0" height="85">
      <Logo size="medium" class="mr-4 ml-4" @click="gotoHome"/>
      <v-spacer></v-spacer>

      <!-- Add search component in app bar only on results page -->
      <template v-if="route.path === '/results'">
        <Search_Component
          :key="searchComponentKey"
          :searchQuery="internalSearchQuery"
          :inline="true"
          :lines="1"
          :queryBuilder="false"
          @searchData="searchData"
          class="app-bar-search mx-2"
        />
        <v-btn
          icon
          @click="showSearchDialog = true"
          density="compact"
        >
          <v-icon>mdi-arrow-expand</v-icon>
        </v-btn>
      </template>

      <v-spacer></v-spacer>

      <v-menu class="mr">
        <template v-slot:activator="{ props }">
          <v-btn icon v-bind="props">
            <v-icon>mdi-menu</v-icon>
          </v-btn>
        </template>

        <v-list>
          <v-list-item @click="navigateTo('/upload')">
            <template v-slot:prepend>
              <v-icon icon="mdi-upload"></v-icon>
            </template>
            <v-list-item-title>Upload Datasets</v-list-item-title>
          </v-list-item>

          <v-list-item @click="navigateTo('/about')">
            <template v-slot:prepend>
              <v-icon icon="mdi-information"></v-icon>
            </template>
            <v-list-item-title>About</v-list-item-title>
          </v-list-item>

          <v-divider class="mx-3"></v-divider>

          <v-list-item @click="toggleHighlight">
            <template v-slot:prepend>
              <v-icon icon="mdi-marker"></v-icon>
            </template>
            <v-list-item-title>
              {{ highlightEnabled ? 'Disable Syntax Highlight' : 'Enable Syntax Highlight' }}
            </v-list-item-title>
          </v-list-item>

          <v-list-item @click="toggleTheme">
            <template v-slot:prepend>
              <v-icon :icon="theme.global.current.value.dark ? 'mdi-weather-sunny' : 'mdi-weather-night'"
                     :color="theme.global.current.value.dark ? 'yellow' : 'indigo'">
              </v-icon>
            </template>
            <v-list-item-title>
              {{ theme.global.current.value.dark ? 'Light Mode' : 'Dark Mode' }}
            </v-list-item-title>
          </v-list-item>
        </v-list>
      </v-menu>
    </v-app-bar>

    <!-- Add expandable search dialog -->
    <v-dialog
      v-model="showSearchDialog"
      transition="dialog-top-transition"
      maxWidth="56rem"
    >
      <v-card>
        <v-toolbar dark color="primary">
          <v-btn icon dark @click="showSearchDialog = false">
            <v-icon>mdi-close</v-icon>
          </v-btn>
          <v-toolbar-title>Query Builder</v-toolbar-title>
        </v-toolbar>

        <v-container class="pt-6">
          <Search_Component
            :key="searchComponentKey"
            :searchQuery="route.query.query"
            :inline="true"
            :lines="3"
            :queryBuilder="false"
            :simpleBuilder="true"
            @searchData="(data) => { searchData(data); showSearchDialog = false; }"
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
  import { useTheme } from 'vuetify'
  import { useRoute } from 'vue-router'
  import Logo from '~/components/Logo.vue'


  function gotoHome() {
    console.log('go to home')
    return navigateTo({path:'/'})
  }

  const { loadResults } = useSearchOperations();
  const route = useRoute();
  const theme = useTheme();
  const { query, fainder_mode, currentPage, selectedResultIndex } = useSearchState();
  const colorMode = useColorMode();
  const highlightEnabled = useCookie('highlight-enabled', { default: () => true })

  const internalSearchQuery = computed(() => route.query.query);
  const searchComponentKey = ref(0);

  let currentTheme = route.query.theme || colorMode.value;
  theme.global.name.value = currentTheme === "dark" ? "dark" : "light";

  function toggleTheme() {
    theme.global.name.value = theme.global.name.value === 'dark' ? "light" : "dark";


    navigateTo({
      path: route.path,
      query: {
        ...route.query,
        theme: theme.global.name.value
      }
    });

  }

  function toggleHighlight() {
    highlightEnabled.value = !highlightEnabled.value
  }

  const showSearchDialog = ref(false);

  async function searchData({ query: searchQuery, fainder_mode: newfainder_mode }) {
    console.log(searchQuery)
    query.value = searchQuery;
    fainder_mode.value = newfainder_mode;

    currentPage.value = 1;
    selectedResultIndex.value = 0;

    await loadResults(searchQuery, 1, newfainder_mode);

    await navigateTo({
      path: '/results',
      query: {
        query: searchQuery,
        page: 1,
        index: 0,
        fainder_mode: newfainder_mode,
        theme: theme.global.name.value,
      },
    });

    searchComponentKey.value++; // Increment key to force component reload
  }
</script>

<style scoped>
.app-bar-search {
  max-width: 800px;  /* Increased from 600px */
  flex-grow: 1;
}

.app-bar-search :deep(.v-field) {
  border-radius: 20px;
}
</style>
