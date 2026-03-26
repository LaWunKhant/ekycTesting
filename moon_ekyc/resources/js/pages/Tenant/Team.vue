<script setup lang="ts">
import AppLayout from '@/layouts/AppLayout.vue';
import { Head } from '@inertiajs/vue3';
import type { BreadcrumbItem } from '@/types';

defineProps<{
    staff: Array<{
        email: string;
        role: string;
    }>;
}>();

const breadcrumbs: BreadcrumbItem[] = [
    { title: 'Dashboard', href: '/dashboard' },
    { title: 'Team', href: '/team' },
];
</script>

<template>
    <Head title="Team" />

    <AppLayout :breadcrumbs="breadcrumbs">
        <div class="flex flex-1 flex-col gap-6 rounded-2xl p-4 md:p-6">
            <section class="rounded-[28px] border border-slate-200 bg-gradient-to-br from-white via-emerald-50 to-slate-100 p-6 shadow-sm dark:border-slate-800 dark:from-slate-900 dark:via-slate-900 dark:to-slate-950">
                <div class="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
                    <div>
                        <div class="text-xs font-medium uppercase tracking-[0.24em] text-emerald-700 dark:text-emerald-300">Tenant Team</div>
                        <h1 class="mt-3 text-3xl font-semibold tracking-tight text-slate-950 dark:text-white">Manage tenant staff accounts</h1>
                        <p class="mt-2 text-sm text-slate-600 dark:text-slate-400">This replaces the dark starter page and mirrors the Django tenant team function with a cleaner Laravel shell.</p>
                    </div>
                    <a href="/dashboard" class="inline-flex items-center justify-center rounded-2xl border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-white dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800">Back to Dashboard</a>
                </div>
            </section>

            <section class="grid gap-6 lg:grid-cols-2">
                <article class="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
                    <h2 class="text-xl font-semibold text-slate-950 dark:text-white">Add Staff Member</h2>
                    <div class="mt-5 space-y-4">
                        <input type="email" placeholder="Email" class="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm outline-none focus:border-cyan-500 dark:border-slate-700 dark:bg-slate-950" />
                        <select class="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm outline-none focus:border-cyan-500 dark:border-slate-700 dark:bg-slate-950">
                            <option>Owner</option>
                            <option>Admin</option>
                            <option>Staff</option>
                        </select>
                        <input type="password" placeholder="Temporary password" class="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm outline-none focus:border-cyan-500 dark:border-slate-700 dark:bg-slate-950" />
                        <button type="button" class="w-full rounded-2xl bg-cyan-500 px-5 py-3 text-sm font-semibold text-slate-950 hover:bg-cyan-400">Add Staff</button>
                    </div>
                </article>

                <article class="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
                    <h2 class="text-xl font-semibold text-slate-950 dark:text-white">Current Staff</h2>
                    <div class="mt-5 divide-y divide-slate-200 dark:divide-slate-800">
                        <div v-for="member in staff" :key="member.email" class="flex items-center justify-between py-4">
                            <div class="text-sm font-medium text-slate-900 dark:text-slate-100">{{ member.email }}</div>
                            <div class="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium uppercase tracking-[0.2em] text-slate-600 dark:bg-slate-800 dark:text-slate-300">{{ member.role }}</div>
                        </div>
                    </div>
                </article>
            </section>
        </div>
    </AppLayout>
</template>
