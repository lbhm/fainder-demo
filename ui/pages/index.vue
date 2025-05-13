<!--
  This page allows users to upload new dataset profiles to the search engine.
-->

<template>
  <v-main class="d-flex align-center justify-center">
    <div class="search-wrapper">
      <div class="d-flex justify-center">
        <FainderWordmark size="large" />
      </div>
      <Search_Component
        :search-query="query"
        :inline="false"
        :lines="1"
        :query-builder="false"
        :simple-builder="true"
        @search-data="searchData"
      />
    </div>
  </v-main>
</template>

<script setup lang="ts">
import { useRoute, navigateTo } from "#imports";
import { ref } from "vue";
import type { LocationQueryValueRaw } from "vue-router";

// type for route query
interface RouteQuery {
  query?: string;
}

// types for search data
interface SearchParams {
  query: string;
  fainder_mode?: string;
  result_highlighting?: LocationQueryValueRaw;
}

const route = useRoute();
const q = route.query as RouteQuery;
const query = ref<string | undefined>(q.query);

async function searchData({
  query: searchQuery,
  fainder_mode: newfainder_mode,
  result_highlighting,
}: SearchParams) {
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
      result_highlighting: result_highlighting,
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
