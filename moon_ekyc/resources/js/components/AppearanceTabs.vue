<script setup lang="ts">
import { useAppearance } from '@/composables/useAppearance';
import { Monitor, Moon, Sun } from 'lucide-vue-next';

interface Props {
    class?: string;
}

const { class: containerClass = '' } = defineProps<Props>();

const { appearance, updateAppearance } = useAppearance();

const tabs = [
    { value: 'light', Icon: Sun, label: 'Light' },
    { value: 'dark', Icon: Moon, label: 'Dark' },
    { value: 'system', Icon: Monitor, label: 'System' },
] as const;
</script>

<template>
    <div
        :class="[
            'inline-flex gap-1 rounded-lg border border-neutral-200 bg-neutral-100 p-1 dark:border-slate-700 dark:bg-slate-900/80',
            containerClass,
        ]"
    >
        <button
            v-for="{ value, Icon, label } in tabs"
            :key="value"
            @click="updateAppearance(value)"
            :class="[
                'flex items-center rounded-md border border-transparent px-3.5 py-1.5 transition-colors',
                appearance === value
                    ? 'border-neutral-300 bg-neutral-50 text-neutral-900 dark:border-slate-700 dark:bg-slate-800 dark:text-white'
                    : 'text-neutral-500 hover:bg-neutral-200/60 hover:text-black dark:text-slate-400 dark:hover:bg-slate-800/70 dark:hover:text-slate-200',
            ]"
        >
            <component :is="Icon" class="-ml-1 h-4 w-4" />
            <span class="ml-1.5 text-sm">{{ label }}</span>
        </button>
    </div>
</template>
