<script setup lang="ts">
import { useAppearance } from '@/composables/useAppearance';
import { Link, usePage } from '@inertiajs/vue3';
import { computed } from 'vue';

const page = usePage();
const { appearance } = useAppearance();

const isLightTheme = computed(() => appearance.value === 'light');

const items = [
    { title: 'Profile', href: '/settings/profile' },
    { title: 'Password', href: '/settings/password' },
    { title: 'Appearance', href: '/settings/appearance' },
];

const isCurrentRoute = (href: string) => page.url === href;
</script>

<template>
    <div class="relative mx-auto w-full max-w-7xl px-4 py-6 md:px-6">
        <div class="flex flex-col gap-8 md:gap-10 lg:flex-row lg:gap-12">
            <aside class="w-full max-w-xl lg:w-48">
                <div
                    class="rounded-[24px] p-4 md:p-5"
                    :class="
                        isLightTheme
                            ? 'border border-slate-200 bg-white shadow-sm'
                            : 'border border-slate-800/80 bg-[#141b31]/70 shadow-[0_18px_40px_rgba(2,6,23,0.22)]'
                    "
                >
                    <div class="px-2 pb-3">
                        <div class="text-xs font-semibold uppercase tracking-[0.24em]" :class="isLightTheme ? 'text-slate-500' : 'text-slate-400'">
                            Settings
                        </div>
                        <p class="mt-2 text-sm leading-6" :class="isLightTheme ? 'text-slate-600' : 'text-slate-300'">
                            Manage your account preferences and workspace access.
                        </p>
                    </div>

                    <nav class="space-y-2">
                        <Link
                            v-for="item in items"
                            :key="item.href"
                            :href="item.href"
                            class="inline-flex w-full items-center justify-between rounded-2xl border px-4 py-3 text-sm font-medium transition"
                            :class="
                                isCurrentRoute(item.href)
                                    ? isLightTheme
                                        ? 'border-cyan-200 bg-cyan-50 text-cyan-700'
                                        : 'border-cyan-500/30 bg-cyan-500/10 text-cyan-200'
                                    : isLightTheme
                                      ? 'border-slate-200 bg-white text-slate-700 hover:bg-slate-50'
                                      : 'border-slate-700 bg-slate-900/70 text-slate-200 hover:border-slate-600 hover:bg-slate-800'
                            "
                        >
                            <span>{{ item.title }}</span>
                            <span class="text-xs" :class="isCurrentRoute(item.href) ? '' : isLightTheme ? 'text-slate-400' : 'text-slate-500'">Open</span>
                        </Link>
                    </nav>

                    <div class="mt-6">
                        <Link
                            href="/dashboard"
                            class="inline-flex w-full items-center justify-center rounded-2xl border px-4 py-2.5 text-sm font-medium transition"
                            :class="
                                isLightTheme
                                    ? 'border-slate-200 bg-white text-slate-700 hover:bg-slate-50'
                                    : 'border-slate-700 bg-slate-900/70 text-slate-200 hover:border-slate-600 hover:bg-slate-800'
                            "
                        >
                            Back to Dashboard
                        </Link>
                    </div>
                </div>
            </aside>

            <div class="min-w-0 flex-1 md:max-w-2xl">
                <section
                    class="rounded-[24px] p-6 md:p-8"
                    :class="
                        isLightTheme
                            ? 'border border-slate-200 bg-white shadow-sm'
                            : 'border border-slate-800/80 bg-[#141b31]/75 shadow-[0_18px_40px_rgba(2,6,23,0.22)]'
                    "
                >
                    <div class="space-y-10">
                        <slot />
                    </div>
                </section>
            </div>
        </div>
    </div>
</template>
