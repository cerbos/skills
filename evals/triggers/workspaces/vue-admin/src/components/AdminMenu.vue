<script setup>
import { useUserStore } from "../stores/user";

const user = useUserStore();

const items = [
  { label: "Dashboard", to: "/" },
  { label: "Users", to: "/users" },
  { label: "Billing", to: "/billing" },
  { label: "Audit log", to: "/audit" },
  { label: "Settings", to: "/settings" },
];
</script>

<template>
  <nav class="menu">
    <p>Signed in as {{ user.name }}</p>
    <router-link v-for="item in items" :key="item.to" :to="item.to" class="menu-item">
      {{ item.label }}
    </router-link>
  </nav>
</template>
