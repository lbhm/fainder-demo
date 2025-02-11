<template>
  <div class="logo" :class="size">
    <img src="/logo.svg" :alt="alt" />
  </div>
</template>

<script setup>
defineProps({
  size: {
    type: String,
    default: "small", // 'small', 'medium', 'large'
  },
  alt: {
    type: String,
    default: "Fainder Logo",
  },
});
</script>

<style scoped>
.logo {
  display: inline-flex;
  align-items: center;
}

.logo img {
  object-fit: contain;
}

.small img {
  height: 32px;
}

.medium img {
  height: 48px;
}

.large img {
  height: 120px;
}
</style>
