<script setup lang="ts">
import { useAppearance } from '@/composables/useAppearance';
import { Monitor, Moon, Sun } from 'lucide-vue-next';
import { computed } from 'vue';

interface Props {
    class?: string;
}

const { class: containerClass = '' } = defineProps<Props>();

const { appearance, updateAppearance } = useAppearance();

const tabs = [
    {
        value: 'light',
        Icon: Sun,
        label: 'Light',
        caption: 'Clean and airy',
        shell: 'border-slate-200/80 bg-white/95 shadow-[0_16px_35px_rgba(148,163,184,0.18)]',
        topGlow: 'from-cyan-100 via-white to-slate-100',
        dot: 'bg-cyan-400',
        line: 'bg-slate-200',
    },
    {
        value: 'dark',
        Icon: Moon,
        label: 'Dark',
        caption: 'Midnight slate',
        shell: 'border-slate-700/80 bg-[#0b1220] shadow-[0_22px_44px_rgba(2,6,23,0.45)]',
        topGlow: 'from-slate-700 via-slate-900 to-[#050816]',
        dot: 'bg-indigo-300',
        line: 'bg-slate-700',
    },
    {
        value: 'system',
        Icon: Monitor,
        label: 'System',
        caption: 'Follow device',
        shell: 'border-slate-800/80 bg-[#07111b] shadow-[0_22px_44px_rgba(2,6,23,0.42)]',
        topGlow: 'from-slate-600 via-slate-800 to-[#050816]',
        dot: 'bg-cyan-300',
        line: 'bg-slate-700',
    },
] as const;

const containerClasses = computed(() =>
    appearance.value === 'light'
        ? 'border-slate-200/90 bg-white/85'
        : appearance.value === 'dark'
          ? 'border-slate-800/90 bg-slate-950/70'
          : 'border-slate-800/90 bg-[#08121c]/85',
);
</script>

<template>
    <div :class="['grid gap-4 rounded-[30px] border p-4 backdrop-blur lg:grid-cols-3', containerClasses, containerClass]">
        <button
            v-for="{ value, Icon, label, caption, shell, topGlow, dot, line } in tabs"
            :key="value"
            @click="updateAppearance(value)"
            :class="[
                'group relative overflow-hidden rounded-[24px] border p-5 text-left transition duration-300 lg:min-h-[272px]',
                appearance === value
                    ? appearance === 'light'
                        ? 'border-cyan-300 bg-cyan-50/90 text-slate-950 shadow-[0_18px_36px_rgba(103,232,249,0.22)]'
                        : appearance === 'dark'
                          ? 'border-indigo-400/70 bg-slate-900 text-white shadow-[0_22px_44px_rgba(15,23,42,0.46)]'
                          : 'border-slate-600/80 bg-slate-900/95 text-slate-50 shadow-[0_22px_44px_rgba(15,23,42,0.46)]'
                    : appearance === 'light'
                      ? 'border-slate-200/80 bg-white/65 text-slate-600 hover:border-slate-300 hover:bg-white'
                      : appearance === 'dark'
                        ? 'border-slate-800/80 bg-slate-950/40 text-slate-300 hover:border-slate-700 hover:bg-slate-900/80'
                        : 'border-slate-900/80 bg-[#031017]/75 text-slate-300 hover:border-slate-700 hover:bg-slate-900/85',
            ]"
        >
            <div class="flex items-start gap-3">
                <span
                    class="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl border"
                    :class="
                        appearance === value
                            ? appearance === 'light'
                                ? 'border-cyan-200 bg-white text-cyan-700'
                                : appearance === 'dark'
                                  ? 'border-slate-700 bg-slate-800 text-indigo-100'
                                  : 'border-slate-700 bg-slate-800 text-slate-100'
                            : 'border-transparent bg-black/5 text-current dark:bg-white/5'
                    "
                >
                    <component :is="Icon" class="h-4 w-4" />
                </span>
                <div class="min-w-0 flex-1">
                    <div class="flex flex-wrap items-center gap-2">
                        <div class="text-[1rem] font-semibold leading-none">{{ label }}</div>
                        <span
                            class="inline-flex w-fit shrink-0 whitespace-nowrap rounded-full border px-2.5 py-1 text-[9px] font-semibold uppercase tracking-[0.16em]"
                            :class="
                                appearance === value
                                    ? appearance === 'light'
                                        ? 'border-cyan-200 bg-white text-cyan-700'
                                        : appearance === 'dark'
                                          ? 'border-indigo-400/30 bg-indigo-400/10 text-indigo-100'
                                          : 'border-slate-600/70 bg-slate-800 text-slate-100'
                                    : 'border-transparent bg-black/5 text-current dark:bg-white/5'
                            "
                        >
                            {{ appearance === value ? 'Active' : 'Preview' }}
                        </span>
                    </div>
                    <div class="mt-2 max-w-[12rem] text-xs leading-5 opacity-75">{{ caption }}</div>
                </div>
            </div>

            <div class="mt-5 rounded-[22px] border p-3.5" :class="shell">
                <div class="h-24 rounded-[18px] bg-gradient-to-br" :class="topGlow" />
                <div class="mt-3.5 flex items-center gap-2">
                    <span class="h-2.5 w-2.5 rounded-full" :class="dot" />
                    <span class="h-2.5 w-20 rounded-full" :class="line" />
                </div>
                <div class="mt-2.5 space-y-2">
                    <div class="h-2.5 w-full rounded-full" :class="line" />
                    <div class="h-2.5 w-4/5 rounded-full opacity-80" :class="line" />
                    <div class="h-2.5 w-3/5 rounded-full opacity-55" :class="line" />
                </div>
            </div>
        </button>
    </div>
</template>
