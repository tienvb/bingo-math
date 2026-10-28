<script setup lang="ts">
import LanguageSwitch from '@/components/LanguageSwitch.vue'
</script>

<template>
  <header class="topbar">
    <LanguageSwitch />
  </header>
  <RouterView />
</template>
