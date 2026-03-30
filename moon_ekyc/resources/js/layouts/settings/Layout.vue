<script setup lang="ts">
import { useAppearance } from '@/composables/useAppearance';
import { Link, usePage } from '@inertiajs/vue3';
import { computed } from 'vue';

const page = usePage();
const { appearance } = useAppearance();

const isLightTheme = computed(() => appearance.value === 'light');
const isDarkTheme = computed(() => appearance.value === 'dark');
const isSystemTheme = computed(() => appearance.value === 'system');

const items = [
    { title: 'Profile', href: '/settings/profile' },
    { title: 'Password', href: '/settings/password' },
    { title: 'Appearance', href: '/settings/appearance' },
];

const isCurrentRoute = (href: string) => page.url === href;
</script>

<template>
    <div
        class="relative mx-auto w-full max-w-7xl px-4 py-6 md:px-6"
        :class="isLightTheme ? 'text-slate-950' : 'text-slate-100'"
    >
        <div v-if="isDarkTheme" class="pointer-events-none absolute inset-x-0 top-0 h-80">
            <div class="absolute left-8 top-0 h-40 w-40 rounded-full bg-indigo-500/10 blur-3xl" />
            <div class="absolute right-12 top-12 h-44 w-44 rounded-full bg-slate-500/10 blur-3xl" />
        </div>
        <div v-if="isSystemTheme" class="pointer-events-none absolute inset-x-0 top-0 h-80">
            <div class="absolute left-0 top-0 h-44 w-44 rounded-full bg-cyan-400/8 blur-3xl" />
            <div class="absolute right-10 top-16 h-52 w-52 rounded-full bg-slate-400/10 blur-3xl" />
            <div class="absolute left-1/3 top-24 h-32 w-32 rounded-full bg-sky-300/6 blur-3xl" />
        </div>
        <div class="flex flex-col gap-8 md:gap-10 lg:flex-row lg:gap-12">
            <aside class="w-full max-w-xl lg:w-48">
                <div
                    class="relative overflow-hidden rounded-[28px] p-4 md:p-5"
                    :class="
                        isLightTheme
                            ? 'border border-slate-200 bg-white shadow-sm'
                            : isDarkTheme
                              ? 'border border-slate-800/80 bg-[#10182b]/78 shadow-[0_24px_50px_rgba(2,6,23,0.35)]'
                              : 'border border-slate-800/80 bg-[linear-gradient(180deg,rgba(10,22,35,0.88),rgba(4,11,20,0.96))] shadow-[0_24px_50px_rgba(2,6,23,0.32)]'
                    "
                >
                    <div
                        class="pointer-events-none absolute inset-x-0 top-0 h-24"
                        :class="
                            isLightTheme
                                ? 'bg-gradient-to-r from-cyan-50 via-white to-slate-100'
                                : isDarkTheme
                                  ? 'bg-gradient-to-r from-indigo-500/8 via-transparent to-slate-200/5'
                                  : 'bg-gradient-to-r from-cyan-300/8 via-slate-200/5 to-transparent'
                        "
                    />
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
                                        : isDarkTheme
                                          ? 'border-indigo-400/35 bg-indigo-400/10 text-indigo-100'
                                          : 'border-slate-600/80 bg-slate-800 text-slate-100'
                                    : isLightTheme
                                      ? 'border-slate-200 bg-white text-slate-700 hover:bg-slate-50'
                                      : isDarkTheme
                                        ? 'border-slate-700 bg-slate-900/70 text-slate-200 hover:border-slate-600 hover:bg-slate-800'
                                        : 'border-slate-800 bg-slate-950/50 text-slate-200 hover:border-slate-700 hover:bg-slate-900/80'
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
                                    : isDarkTheme
                                      ? 'border-slate-700 bg-slate-900/70 text-slate-200 hover:border-slate-600 hover:bg-slate-800'
                                      : 'border-slate-800 bg-slate-950/50 text-slate-100 hover:border-slate-700 hover:bg-slate-900/80'
                            "
                        >
                            Back to Dashboard
                        </Link>
                    </div>
                </div>
            </aside>

            <div class="min-w-0 flex-1 lg:max-w-4xl">
                <section
                    class="relative overflow-hidden rounded-[28px] p-6 md:p-8"
                    :class="
                        isLightTheme
                            ? 'border border-slate-200 bg-white shadow-sm'
                            : isDarkTheme
                              ? 'border border-slate-800/80 bg-[linear-gradient(180deg,rgba(17,24,39,0.88),rgba(10,15,28,0.96))] shadow-[0_24px_50px_rgba(2,6,23,0.34)]'
                              : 'border border-slate-800/80 bg-[linear-gradient(180deg,rgba(10,22,35,0.88),rgba(4,11,20,0.96))] shadow-[0_24px_50px_rgba(2,6,23,0.32)]'
                    "
                >
                    <div
                        class="pointer-events-none absolute inset-x-0 top-0 h-28"
                        :class="
                            isLightTheme
                                ? 'bg-gradient-to-r from-cyan-50 via-white to-slate-100'
                                : isDarkTheme
                                  ? 'bg-gradient-to-r from-indigo-400/8 via-transparent to-slate-200/5'
                                  : 'bg-gradient-to-r from-cyan-300/8 via-slate-200/5 to-transparent'
                        "
                    />
                    <div class="space-y-10">
                        <slot />
                    </div>
                </section>
            </div>
        </div>
    </div>
</template>
