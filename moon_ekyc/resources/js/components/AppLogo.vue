<script setup lang="ts">
import AppLogoIcon from '@/components/AppLogoIcon.vue';

interface Props {
    class?: string;
}

defineProps<Props>();
</script>

<template>
    <div class="flex aspect-square size-8 items-center justify-center rounded-xl bg-cyan-500/15 text-cyan-700 ring-1 ring-cyan-500/20 dark:text-cyan-300">
        <AppLogoIcon class="size-5 fill-current" />
    </div>
    <div class="ml-1 grid flex-1 text-left text-sm">
        <span class="mb-0.5 truncate font-semibold leading-none">MoonKYC Tenant</span>
        <span class="truncate text-xs text-slate-500">Portal</span>
    </div>
</template>
