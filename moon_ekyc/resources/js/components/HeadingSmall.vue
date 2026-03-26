<script setup lang="ts">
interface Props {
    title: string;
    description?: string;
}

defineProps<Props>();
</script>

<template>
    <header>
        <h3 class="mb-0.5 text-base font-medium dark:text-white">{{ title }}</h3>
        <p v-if="description" class="text-sm text-muted-foreground dark:text-slate-400">
            {{ description }}
        </p>
    </header>
</template>
