<script setup lang="ts">
import { useI18n } from 'vue-i18n'


const { t } = useI18n()
</script>

<template>
  <main class="page">
    <h1>{{ t('create.title') }}</h1>
    <RouterLink class="link" to="/">{{ t('app.backHome') }}</RouterLink>
  </main>
</template>
