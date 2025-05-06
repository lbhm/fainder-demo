<template>
  <v-main class="d-flex align-center justify-center">
    <div class="search-wrapper">
      <div class="d-flex justify-center">
        <FainderWordmark size="large" />
      </div>
      <Search_Component
        :search-query="query"
        :inline="true"
        :lines="5"
        :query-builder="false"
        :simple-builder="true"
        @search-data="searchData"
      />
    </div>
  </v-main>
</template>

<script setup lang="ts">
import { useRoute, navigateTo } from '#imports';
import { ref } from 'vue';

// type for route query
interface RouteQuery {
  query?: string;
}

// types for search data
interface SearchParams {
  query: string;
  fainder_mode?: string;
  enable_highlighting?: boolean;
}

const route = useRoute();
const q = route.query as RouteQuery;
const query = ref<string | undefined>(q.query);

async function searchData({
  query: searchQuery,
  fainder_mode: newfainder_mode,
  enable_highlighting,
}: SearchParams): Promise<void> {
  // If query is empty or undefined, reset the URL without query parameters
  if (!searchQuery || searchQuery.trim() === "") {
    await navigateTo({
      path: "/",
      replace: true,
    });
    return;
  }

  await navigateTo({
    path: "/results",
    query: {
      query: searchQuery,
      fainder_mode: newfainder_mode,
      enable_highlighting: enable_highlighting ? enable_highlighting.toString() : "false",
    },
  });
}
</script>

<style scoped>
.search-wrapper {
  width: 100%;
  max-width: 800px;
  padding: 0px;
  margin-bottom: 150px;
}
</style>
