<template>
  <v-main class="d-flex align-center justify-center">
    <div class="search-wrapper">
      <div class="d-flex justify-center">
        <Wordmark size="large" />
      </div>
      <Search_Component
        :searchQuery="query"
        :inline="true"
        :lines="5"
        :queryBuilder="false"
        :simpleBuilder="true"
        @searchData="searchData"
      />
    </div>
  </v-main>
</template>

<script setup>
const route = useRoute();
const q = route.query;
const query = ref(q.query);

async function searchData({
  query: searchQuery,
  fainder_mode: newfainder_mode,
  enable_highlighting,
}) {
  // If query is empty or undefined, reset the URL without query parameters
  if (!searchQuery || searchQuery.trim() === "") {
    return await navigateTo({
      path: "/",
      replace: true,
    });
  }

  return await navigateTo({
    path: "/results",
    query: {
      query: searchQuery,
      fainder_mode: newfainder_mode,
      enable_highlighting: enable_highlighting,
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
