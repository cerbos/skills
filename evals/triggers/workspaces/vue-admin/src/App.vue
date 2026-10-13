<script setup>
import AdminMenu from "./components/AdminMenu.vue";
</script>

<template>
  <div class="layout">
    <AdminMenu />
    <main><router-view /></main>
  </div>
</template>
