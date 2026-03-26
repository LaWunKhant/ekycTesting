<script setup lang="ts">
import AppLayout from '@/layouts/AppLayout.vue';
import { Head } from '@inertiajs/vue3';
import type { BreadcrumbItem } from '@/types';

defineProps<{
    queue: Array<{
        id: string;
        customerName: string;
        reviewStatus: string;
    }>;
}>();

const breadcrumbs: BreadcrumbItem[] = [
    { title: 'Dashboard', href: '/dashboard' },
    { title: 'Review', href: '/review' },
];
</script>

<template>
    <Head title="Review Queue" />

    <AppLayout :breadcrumbs="breadcrumbs">
        <div class="flex flex-1 flex-col gap-6 rounded-2xl p-4 md:p-6">
            <section class="rounded-[28px] border border-slate-200 bg-gradient-to-br from-white via-amber-50 to-slate-100 p-6 shadow-sm dark:border-slate-800 dark:from-slate-900 dark:via-slate-900 dark:to-slate-950">
                <div class="text-xs font-medium uppercase tracking-[0.24em] text-amber-700 dark:text-amber-300">Review Queue</div>
                <h1 class="mt-3 text-3xl font-semibold tracking-tight text-slate-950 dark:text-white">Manual approval queue</h1>
                <p class="mt-2 text-sm text-slate-600 dark:text-slate-400">Use this page for the Laravel reviewer handoff once you connect tenant verification sessions and reviewer actions.</p>
            </section>

            <section class="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
                <div v-if="queue.length === 0" class="text-sm text-slate-500 dark:text-slate-400">
                    No queued reviews yet. Connect your KYC sessions table and review status fields to populate this page.
                </div>
            </section>
        </div>
    </AppLayout>
</template>
