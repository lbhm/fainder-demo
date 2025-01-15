<template>
  <v-main class="d-flex align-center justify-center">
    <div class="search-wrapper">
      <div class="d-flex justify-center">
        <Logo size="large" class="mb-8"/>
      </div>
      <Search_Component
        :searchQuery="query"
        @searchData="searchData"
      />
    </div>
  </v-main>
</template>

<script setup>
import Logo from '~/components/Logo.vue'

const route = useRoute();
const q = route.query;

const query = ref(q.query);

async function searchData({query: searchQuery}) {
  return await navigateTo({
    path: '/results',
    query: {
      query: searchQuery
    }
  });
}

</script>

<style scoped>
.search-wrapper {
  width: 100%;
  max-width: 800px;
  padding: 24px;
}
</style>
