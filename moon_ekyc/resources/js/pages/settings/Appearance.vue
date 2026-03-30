<script setup lang="ts">
import { useAppearance } from '@/composables/useAppearance';
import { Head } from '@inertiajs/vue3';
import { computed } from 'vue';

import AppearanceTabs from '@/components/AppearanceTabs.vue';
import HeadingSmall from '@/components/HeadingSmall.vue';
import { type BreadcrumbItem } from '@/types';

import AppLayout from '@/layouts/AppLayout.vue';
import SettingsLayout from '@/layouts/settings/Layout.vue';

const breadcrumbItems: BreadcrumbItem[] = [
    {
        title: 'Appearance settings',
        href: '/settings/appearance',
    },
];

const { appearance } = useAppearance();

const previewClasses = computed(() =>
    appearance.value === 'light'
        ? 'border-slate-200 bg-gradient-to-br from-white via-cyan-50 to-slate-100'
        : appearance.value === 'dark'
          ? 'border-slate-800/80 bg-gradient-to-br from-[#101827] via-[#0b1220] to-[#050816]'
          : 'border-slate-800/80 bg-gradient-to-br from-[#0a1623] via-[#08131d] to-[#040b13]',
);
</script>

<template>
    <AppLayout :breadcrumbs="breadcrumbItems">
        <Head title="Appearance settings" />

        <SettingsLayout>
            <div class="space-y-8">
                <div class="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                    <HeadingSmall title="Appearance settings" description="Update your account's appearance settings" />
                    <div
                        class="inline-flex items-center rounded-full border px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.24em]"
                        :class="
                            appearance === 'light'
                                ? 'border-cyan-200 bg-cyan-50 text-cyan-700'
                                : appearance === 'dark'
                                  ? 'border-indigo-400/30 bg-indigo-400/10 text-indigo-100'
                                  : 'border-slate-600/70 bg-slate-800/60 text-slate-100'
                        "
                    >
                        {{ appearance }} mode
                    </div>
                </div>

                <div class="rounded-[32px] border p-5 md:p-6" :class="previewClasses">
                    <div class="flex flex-col gap-7">
                        <div class="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
                            <div class="max-w-2xl">
                                <div class="mb-2 text-[11px] font-semibold uppercase tracking-[0.24em]" :class="appearance === 'light' ? 'text-slate-500' : 'text-slate-400'">
                                    Workspace Theme
                                </div>
                                <p class="text-sm leading-6" :class="appearance === 'light' ? 'text-slate-600' : 'text-slate-300'">
                                The workspace defaults to the navy dashboard for a cleaner trust-first experience. Dark mode stays available as the primary workspace option, while system follows the device preference without switching to a decorative accent-heavy palette.
                                </p>
                            </div>
                            <div
                                class="inline-flex items-center self-start rounded-full border px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.22em]"
                                :class="
                                    appearance === 'light'
                                        ? 'border-cyan-200/80 bg-white/90 text-cyan-700'
                                        : appearance === 'dark'
                                          ? 'border-indigo-400/25 bg-indigo-400/10 text-indigo-100'
                                          : 'border-slate-600/70 bg-slate-800/70 text-slate-100'
                                "
                            >
                                Default: Navy workspace
                            </div>
                        </div>
                        <AppearanceTabs />
                    </div>
                </div>
            </div>
        </SettingsLayout>
    </AppLayout>
</template>
