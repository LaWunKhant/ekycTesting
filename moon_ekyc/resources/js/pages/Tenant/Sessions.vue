<script setup lang="ts">
import AppLayout from '@/layouts/AppLayout.vue';
import { Head } from '@inertiajs/vue3';
import type { BreadcrumbItem } from '@/types';

defineProps<{
    summary: {
        totalSessions: number;
        pendingReviews: number;
    };
    filters: {
        search: string;
        reviewStatus: string;
    };
    sessions: Array<{
        id: string;
        customerName: string;
        email: string;
        reviewStatus: string;
        submittedAt: string;
    }>;
}>();

const breadcrumbs: BreadcrumbItem[] = [
    { title: 'Dashboard', href: '/dashboard' },
    { title: 'Sessions', href: '/sessions' },
];
</script>

<template>
    <Head title="Customer Sessions" />

    <AppLayout :breadcrumbs="breadcrumbs">
        <div class="flex flex-1 flex-col gap-6 rounded-2xl p-4 md:p-6">
            <section class="rounded-[28px] border border-slate-200 bg-gradient-to-br from-white via-cyan-50 to-slate-100 p-6 shadow-sm dark:border-slate-800 dark:from-slate-900 dark:via-slate-900 dark:to-slate-950">
                <div class="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
                    <div>
                        <div class="text-xs font-medium uppercase tracking-[0.24em] text-cyan-700 dark:text-cyan-300">Customer Sessions</div>
                        <h1 class="mt-3 text-3xl font-semibold tracking-tight text-slate-950 dark:text-white">Search and review tenant sessions</h1>
                        <p class="mt-2 text-sm text-slate-600 dark:text-slate-400">This is the Laravel version of the Django customer sessions page. Wire your tenant session query and filters into this view next.</p>
                    </div>
                    <a href="/dashboard" class="inline-flex items-center justify-center rounded-2xl border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-white dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800">Back to Dashboard</a>
                </div>
            </section>

            <section class="grid gap-4 md:grid-cols-2">
                <div class="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
                    <div class="text-xs uppercase tracking-[0.24em] text-slate-500">Total Sessions</div>
                    <div class="mt-3 text-4xl font-semibold text-slate-950 dark:text-white">{{ summary.totalSessions }}</div>
                </div>
                <div class="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
                    <div class="text-xs uppercase tracking-[0.24em] text-slate-500">Pending Reviews</div>
                    <div class="mt-3 text-4xl font-semibold text-slate-950 dark:text-white">{{ summary.pendingReviews }}</div>
                </div>
            </section>

            <section class="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
                <div class="grid gap-4 md:grid-cols-[2fr_1fr_auto]">
                    <input type="text" :value="filters.search" placeholder="Search by customer name or email" class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm outline-none focus:border-cyan-500 dark:border-slate-700 dark:bg-slate-950" />
                    <select :value="filters.reviewStatus" class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm outline-none focus:border-cyan-500 dark:border-slate-700 dark:bg-slate-950">
                        <option value="">All review statuses</option>
                        <option value="pending">Pending</option>
                        <option value="approved">Approved</option>
                        <option value="rejected">Rejected</option>
                        <option value="needs_info">Needs Info</option>
                    </select>
                    <button type="button" class="rounded-2xl bg-cyan-500 px-5 py-3 text-sm font-semibold text-slate-950 hover:bg-cyan-400">Apply</button>
                </div>

                <div class="mt-6 overflow-hidden rounded-2xl border border-slate-200 dark:border-slate-800">
                    <table class="min-w-full divide-y divide-slate-200 dark:divide-slate-800">
                        <thead class="bg-slate-50 dark:bg-slate-950">
                            <tr>
                                <th class="px-4 py-3 text-left text-xs font-medium uppercase tracking-[0.2em] text-slate-500">Customer</th>
                                <th class="px-4 py-3 text-left text-xs font-medium uppercase tracking-[0.2em] text-slate-500">Email</th>
                                <th class="px-4 py-3 text-left text-xs font-medium uppercase tracking-[0.2em] text-slate-500">Review Status</th>
                                <th class="px-4 py-3 text-left text-xs font-medium uppercase tracking-[0.2em] text-slate-500">Submitted</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-slate-200 bg-white dark:divide-slate-800 dark:bg-slate-900">
                            <tr v-if="sessions.length === 0">
                                <td colspan="4" class="px-4 py-10 text-center text-sm text-slate-500 dark:text-slate-400">No sessions yet. Connect your tenant verification session table here.</td>
                            </tr>
                            <tr v-for="session in sessions" :key="session.id">
                                <td class="px-4 py-4 text-sm text-slate-900 dark:text-slate-100">{{ session.customerName }}</td>
                                <td class="px-4 py-4 text-sm text-slate-600 dark:text-slate-300">{{ session.email }}</td>
                                <td class="px-4 py-4 text-sm text-slate-600 dark:text-slate-300">{{ session.reviewStatus }}</td>
                                <td class="px-4 py-4 text-sm text-slate-600 dark:text-slate-300">{{ session.submittedAt }}</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </section>
        </div>
    </AppLayout>
</template>
