<script setup lang="ts">
import { getInitials } from '@/composables/useInitials';
import { useAppearance } from '@/composables/useAppearance';
import AppLayout from '@/layouts/AppLayout.vue';
import { type BreadcrumbItem } from '@/types';
import { Head, Link, useForm, usePage } from '@inertiajs/vue3';
import { ChevronDown } from 'lucide-vue-next';
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';

const breadcrumbs: BreadcrumbItem[] = [
    {
        title: 'Dashboard',
        href: '/dashboard',
    },
];

const page = usePage();
const authUser = computed(() => page.props.auth.user);
const accountName = computed(() => authUser.value?.name ?? '');
const accountEmail = computed(() => authUser.value?.email ?? '');
const accountInitials = computed(() => getInitials(accountName.value || accountEmail.value));
const { appearance } = useAppearance();
const accountMenuOpen = ref(false);
const accountMenuRef = ref<HTMLElement | null>(null);
const isLightTheme = computed(() => appearance.value === 'light');
const isSystemTheme = computed(() => appearance.value === 'system');
const customerForm = useForm({
    full_name: '',
    email: '',
    phone: '',
    external_ref: '',
});

const toggleAccountMenu = () => {
    accountMenuOpen.value = !accountMenuOpen.value;
};

const closeAccountMenu = () => {
    accountMenuOpen.value = false;
};

const handleAccountMenuClick = (event: MouseEvent) => {
    if (!accountMenuRef.value) {
        return;
    }

    if (!accountMenuRef.value.contains(event.target as Node)) {
        closeAccountMenu();
    }
};

onMounted(() => {
    document.addEventListener('click', handleAccountMenuClick);
});

onBeforeUnmount(() => {
    document.removeEventListener('click', handleAccountMenuClick);
});

const generateVerificationLink = () => {
    customerForm.post(route('dashboard.store'));
};

defineProps<{
    workspace: {
        name: string;
        subtitle: string;
        tenantName: string;
    };
    stats: Array<{
        label: string;
        value: string;
        caption: string;
        tone: string;
    }>;
    actions: Array<{
        label: string;
        href: string;
        caption: string;
    }>;
    quickStart: {
        title: string;
        description: string;
        fields: string[];
    };
    latestLink: {
        url: string | null;
        status: string;
    };
    status?: string;
    mailError?: string;
}>();
</script>

<template>
    <Head title="Tenant Dashboard">
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin="anonymous" />
        <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&display=swap" rel="stylesheet" />
    </Head>

    <AppLayout :breadcrumbs="breadcrumbs">
        <div
            class="relative flex flex-1 flex-col overflow-hidden font-['Space_Grotesk']"
            :class="isLightTheme
                ? 'bg-gradient-to-br from-slate-100 via-white to-slate-100 text-slate-950'
                : isSystemTheme
                    ? 'bg-gradient-to-br from-slate-950 via-[#0f172a] to-slate-950 text-white'
                    : 'bg-[#05070f] text-white'"
        >
            <div v-if="isSystemTheme" class="pointer-events-none absolute inset-0">
                <div class="absolute -left-16 -top-24 h-72 w-72 rounded-full bg-cyan-500/10 blur-3xl" />
                <div class="absolute right-[-6rem] top-28 h-80 w-80 rounded-full bg-emerald-500/8 blur-3xl" />
                <div class="absolute bottom-[-4rem] left-1/3 h-64 w-64 rounded-full bg-sky-500/10 blur-3xl" />
            </div>

            <div class="relative mx-auto flex w-full max-w-7xl flex-1 flex-col gap-5 px-4 py-6 md:px-6 md:py-8">
            <section class="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
                <div class="max-w-2xl">
                    <div
                        class="inline-flex items-center rounded-full px-3 py-1 text-[11px] font-medium tracking-[0.18em] backdrop-blur"
                        :class="isLightTheme
                            ? 'border border-cyan-500/30 bg-white/80 text-slate-700'
                            : 'border border-cyan-400/20 bg-slate-900/70 text-slate-300'"
                    >
                        <span class="mr-2 inline-block h-2 w-2 rounded-full bg-cyan-300 shadow-[0_0_12px_rgba(103,232,249,0.9)]" />
                        {{ workspace.name }}
                    </div>
                    <h1 class="mt-4 text-[2.6rem] font-semibold leading-[1.02] tracking-[-0.04em] md:text-[3.2rem]">{{ workspace.tenantName }} Dashboard</h1>
                    <p class="mt-2.5 max-w-xl text-[15px]" :class="isLightTheme ? 'text-slate-600' : 'text-slate-400'">{{ workspace.subtitle }}</p>
                </div>

                <div class="flex flex-wrap items-center gap-3 lg:justify-end">
                    <a
                        href="/team"
                        class="inline-flex items-center justify-center rounded-full px-5 py-2.5 text-sm font-medium backdrop-blur transition"
                        :class="isLightTheme
                            ? 'border border-slate-200 bg-white text-slate-700 hover:bg-slate-100'
                            : 'border border-slate-700/80 bg-slate-900/70 text-slate-100 hover:border-slate-500 hover:bg-slate-800'"
                    >
                        Manage Team
                    </a>
                    <a
                        href="/review"
                        class="inline-flex items-center justify-center rounded-full border border-cyan-500/40 bg-cyan-500/10 px-5 py-2.5 text-sm font-medium backdrop-blur transition hover:bg-cyan-500/20"
                        :class="isLightTheme ? 'text-cyan-700' : 'text-cyan-100'"
                    >
                        Review Queue
                    </a>
                    <div ref="accountMenuRef" class="relative">
                        <button
                            type="button"
                            class="inline-flex shrink-0 items-center gap-3 whitespace-nowrap rounded-full px-4 py-2.5 text-sm backdrop-blur transition"
                            :class="isLightTheme
                                ? 'border border-slate-200 bg-white text-slate-700 hover:bg-slate-100'
                                : 'border border-slate-700/80 bg-slate-900/70 text-slate-200 hover:border-slate-500 hover:bg-slate-800'"
                            @click="toggleAccountMenu"
                        >
                            <span class="flex h-7 w-7 items-center justify-center rounded-full text-xs font-semibold" :class="isLightTheme ? 'bg-slate-200 text-slate-700' : 'bg-slate-700 text-slate-100'">
                                {{ accountInitials }}
                            </span>
                            <span class="max-w-[9rem] truncate">{{ accountName }}</span>
                            <ChevronDown class="h-4 w-4 text-slate-400 transition" :class="{ 'rotate-180': accountMenuOpen }" />
                        </button>

                        <div
                            v-if="accountMenuOpen"
                            class="absolute right-0 top-[calc(100%+12px)] z-20 w-[320px] rounded-[18px] p-3 shadow-[0_24px_50px_rgba(2,6,23,0.4)]"
                            :class="isLightTheme ? 'border border-slate-200 bg-white text-slate-900' : 'border border-slate-700 bg-[#141b31] text-white'"
                        >
                            <div class="rounded-2xl px-4 py-3" :class="isLightTheme ? 'border border-slate-200 bg-slate-50' : 'border border-slate-700 bg-slate-800/60'">
                                <div class="text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-500">Signed in as</div>
                                <div class="mt-2 text-sm font-semibold" :class="isLightTheme ? 'text-slate-900' : 'text-white'">{{ accountName }}</div>
                                <div class="text-sm text-slate-400">{{ accountEmail }}</div>
                            </div>
                            <div class="my-2 h-px" :class="isLightTheme ? 'bg-slate-200' : 'bg-slate-700'" />
                            <Link
                                :href="route('profile.edit')"
                                class="flex w-full items-center justify-between rounded-xl px-3 py-2.5 text-sm outline-none"
                                :class="isLightTheme ? 'text-slate-700 hover:bg-slate-100' : 'text-slate-200 hover:bg-slate-800/70'"
                                @click="closeAccountMenu"
                            >
                                <span>Settings</span>
                                <span class="text-xs text-slate-400">Open</span>
                            </Link>
                            <Link
                                :href="route('logout')"
                                method="post"
                                as="button"
                                class="flex w-full items-center justify-between rounded-xl px-3 py-2.5 text-sm text-rose-300 outline-none hover:bg-rose-500/10"
                                @click="closeAccountMenu"
                            >
                                <span>Log Out</span>
                                <span class="text-xs text-rose-300/80">Exit</span>
                            </Link>
                            <div class="my-2 h-px" :class="isLightTheme ? 'bg-slate-200' : 'bg-slate-700'" />
                            <div class="px-3 py-2 text-xs font-semibold text-amber-300">Temp: Liveness Debug</div>
                        </div>
                    </div>
                </div>
            </section>

            <section class="grid gap-4 md:grid-cols-2">
                <article
                    v-for="stat in stats"
                    :key="stat.label"
                    class="rounded-[20px] p-5 shadow-[0_18px_40px_rgba(2,6,23,0.16)] backdrop-blur"
                    :class="isLightTheme
                        ? 'border border-slate-200 bg-gradient-to-br from-white to-slate-100/80'
                        : 'border border-slate-800/80 bg-gradient-to-br from-slate-900/80 to-slate-950/90'"
                >
                    <div class="flex items-start justify-between gap-4">
                        <div>
                            <div class="text-[11px] font-medium uppercase tracking-[0.22em] text-slate-500">{{ stat.label }}</div>
                            <div class="mt-3 text-[3rem] leading-none font-semibold" :class="isLightTheme ? 'text-slate-950' : 'text-white'">{{ stat.value }}</div>
                            <p class="mt-3 max-w-sm text-[13px] leading-6" :class="isLightTheme ? 'text-slate-600' : 'text-slate-500'">{{ stat.caption }}</p>
                        </div>
                        <div
                            class="rounded-full px-3 py-1 text-[11px] font-medium"
                            :class="stat.tone === 'amber'
                                ? 'bg-amber-500/10 text-amber-300 ring-1 ring-amber-500/20'
                                : 'bg-cyan-500/10 text-cyan-300 ring-1 ring-cyan-500/20'"
                        >
                            {{ stat.tone === 'amber' ? 'Queue' : 'Live' }}
                        </div>
                    </div>
                </article>
            </section>

            <section class="grid gap-5 xl:grid-cols-[1.7fr_0.8fr]">
                <article
                    class="rounded-[22px] p-5 shadow-[0_22px_46px_rgba(2,6,23,0.16)] backdrop-blur"
                    :class="isLightTheme ? 'border border-slate-200 bg-white/90' : 'border border-slate-800/80 bg-slate-900/60'"
                >
                    <div v-if="mailError" class="mb-4 rounded-2xl border border-amber-500/20 bg-amber-500/10 px-4 py-3 text-sm text-amber-300">
                        {{ mailError }}
                    </div>
                    <div v-if="status" class="mb-4 rounded-2xl border border-emerald-500/20 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-300">
                        {{ status }}
                    </div>
                    <div class="flex items-start justify-between gap-4">
                        <div>
                            <h2 class="text-[1.95rem] font-semibold tracking-[-0.03em]" :class="isLightTheme ? 'text-slate-950' : 'text-white'">{{ quickStart.title }}</h2>
                            <p class="mt-2 max-w-2xl text-[14px] leading-6" :class="isLightTheme ? 'text-slate-600' : 'text-slate-400'">{{ quickStart.description }}</p>
                        </div>
                        <span class="rounded-full px-3 py-1 text-[11px] font-medium text-slate-400">
                            Step 1 of 2
                        </span>
                    </div>

                    <form class="mt-5 grid gap-4 md:grid-cols-2" @submit.prevent="generateVerificationLink">
                        <label class="block">
                            <span class="text-[13px] font-medium" :class="isLightTheme ? 'text-slate-600' : 'text-slate-300'">Full Name</span>
                            <input
                                v-model="customerForm.full_name"
                                type="text"
                                class="mt-2 h-11 w-full rounded-[18px] px-4 py-3 text-sm outline-none transition placeholder:text-slate-500 focus:border-cyan-400 focus:ring-1 focus:ring-cyan-500/30"
                                :class="isLightTheme
                                    ? 'border border-slate-200 bg-white text-slate-900'
                                    : 'border border-slate-800 bg-slate-950/90 text-white'"
                            >
                        </label>
                        <label class="block">
                            <span class="text-[13px] font-medium" :class="isLightTheme ? 'text-slate-600' : 'text-slate-300'">Email</span>
                            <input
                                v-model="customerForm.email"
                                type="email"
                                class="mt-2 h-11 w-full rounded-[18px] px-4 py-3 text-sm outline-none transition placeholder:text-slate-500 focus:border-cyan-400 focus:ring-1 focus:ring-cyan-500/30"
                                :class="isLightTheme
                                    ? 'border border-slate-200 bg-white text-slate-900'
                                    : 'border border-slate-800 bg-slate-950/90 text-white'"
                            >
                        </label>
                        <label class="block">
                            <span class="text-[13px] font-medium" :class="isLightTheme ? 'text-slate-600' : 'text-slate-300'">Phone</span>
                            <input
                                v-model="customerForm.phone"
                                type="text"
                                class="mt-2 h-11 w-full rounded-[18px] px-4 py-3 text-sm outline-none transition placeholder:text-slate-500 focus:border-cyan-400 focus:ring-1 focus:ring-cyan-500/30"
                                :class="isLightTheme
                                    ? 'border border-slate-200 bg-white text-slate-900'
                                    : 'border border-slate-800 bg-slate-950/90 text-white'"
                            >
                        </label>
                        <label class="block">
                            <span class="text-[13px] font-medium" :class="isLightTheme ? 'text-slate-600' : 'text-slate-300'">External Ref (optional)</span>
                            <input
                                v-model="customerForm.external_ref"
                                type="text"
                                class="mt-2 h-11 w-full rounded-[18px] px-4 py-3 text-sm outline-none transition placeholder:text-slate-500 focus:border-cyan-400 focus:ring-1 focus:ring-cyan-500/30"
                                :class="isLightTheme
                                    ? 'border border-slate-200 bg-white text-slate-900'
                                    : 'border border-slate-800 bg-slate-950/90 text-white'"
                            >
                        </label>

                        <div class="md:col-span-2">
                            <div v-if="customerForm.errors.full_name || customerForm.errors.email || customerForm.errors.phone || customerForm.errors.external_ref" class="mb-3 rounded-2xl border border-rose-500/20 bg-rose-500/10 px-4 py-3 text-sm text-rose-300">
                                {{ customerForm.errors.full_name || customerForm.errors.email || customerForm.errors.phone || customerForm.errors.external_ref }}
                            </div>

                            <button
                                type="submit"
                                class="inline-flex h-11 w-full items-center justify-center rounded-[18px] bg-cyan-400 px-5 py-3 text-[15px] font-semibold text-slate-950 shadow-lg shadow-cyan-500/20 transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:opacity-70"
                                :disabled="customerForm.processing"
                            >
                                Generate Verification Link
                            </button>
                        </div>
                    </form>
                </article>

                <article
                    class="rounded-[22px] p-5 shadow-[0_22px_46px_rgba(2,6,23,0.16)] backdrop-blur"
                    :class="isLightTheme ? 'border border-slate-200 bg-white/90' : 'border border-slate-800/80 bg-slate-900/60'"
                >
                    <div class="flex items-start justify-between gap-4">
                        <div>
                            <h2 class="text-[1.95rem] font-semibold tracking-[-0.03em]" :class="isLightTheme ? 'text-slate-950' : 'text-white'">Latest Verification Link</h2>
                        </div>
                        <span class="rounded-full px-3 py-1 text-[11px] font-medium text-slate-400">
                            Step 2 of 2
                        </span>
                    </div>

                    <div class="mt-4 text-[14px] leading-6" :class="isLightTheme ? 'text-slate-600' : 'text-slate-300'">
                        <template v-if="latestLink.url">
                            {{ latestLink.url }}
                        </template>
                        <template v-else>
                            {{ latestLink.status }}
                        </template>
                    </div>

                    <div class="mt-5 rounded-[18px] p-4" :class="isLightTheme ? 'border border-slate-200 bg-slate-50/80' : 'border border-slate-800 bg-slate-950/60'">
                        <div class="text-[11px] uppercase tracking-[0.22em] text-slate-500">Quick Actions</div>
                        <div class="mt-3 space-y-2.5">
                            <a
                                v-for="action in actions"
                                :key="`${action.label}-quick`"
                                :href="action.href"
                                class="flex items-center justify-between rounded-[14px] px-4 py-2.5 text-[14px] font-medium transition"
                                :class="isLightTheme
                                    ? 'border border-slate-200 bg-white text-slate-700 hover:bg-slate-100'
                                    : 'border border-slate-800 bg-slate-900/80 text-slate-200 hover:border-slate-600 hover:bg-slate-800'"
                            >
                                <span>{{ action.label === 'Customer Sessions' ? 'Review pending sessions' : action.label === 'Team Management' ? 'Invite or manage team' : 'Change your password' }}</span>
                                <span class="text-xs text-slate-400">Go</span>
                            </a>
                        </div>
                    </div>
                </article>
            </section>

            <section
                class="rounded-[22px] p-5 shadow-[0_22px_46px_rgba(2,6,23,0.16)] backdrop-blur"
                :class="isLightTheme ? 'border border-slate-200 bg-white/90' : 'border border-slate-800/80 bg-slate-900/60'"
            >
                <div class="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                    <div>
                        <h2 class="text-[1.7rem] font-semibold tracking-[-0.03em]" :class="isLightTheme ? 'text-slate-950' : 'text-white'">Customer Sessions</h2>
                        <p class="mt-2 max-w-3xl text-[14px] leading-6" :class="isLightTheme ? 'text-slate-600' : 'text-slate-400'">
                            The customer sessions page is where search, review-state filtering, and pagination should live once the tenant session data is wired in.
                        </p>
                    </div>
                    <a
                        href="/sessions"
                        class="inline-flex items-center justify-center rounded-[18px] bg-cyan-400 px-5 py-2.5 text-[14px] font-semibold text-slate-950 shadow-lg shadow-cyan-500/20 transition hover:bg-cyan-300"
                    >
                        View Customer Sessions
                    </a>
                </div>

                <div class="mt-5 grid gap-3 md:grid-cols-3">
                    <div class="rounded-[18px] p-4" :class="isLightTheme ? 'border border-slate-200 bg-slate-50/80' : 'border border-slate-800 bg-slate-950/60'">
                        <div class="text-[11px] uppercase tracking-[0.24em] text-slate-500">Search</div>
                        <div class="mt-2 text-[14px]" :class="isLightTheme ? 'text-slate-700' : 'text-slate-300'">Customer name or email</div>
                    </div>
                    <div class="rounded-[18px] p-4" :class="isLightTheme ? 'border border-slate-200 bg-slate-50/80' : 'border border-slate-800 bg-slate-950/60'">
                        <div class="text-[11px] uppercase tracking-[0.24em] text-slate-500">Filter</div>
                        <div class="mt-2 text-[14px]" :class="isLightTheme ? 'text-slate-700' : 'text-slate-300'">Pending, approved, rejected, needs info</div>
                    </div>
                    <div class="rounded-[18px] p-4" :class="isLightTheme ? 'border border-slate-200 bg-slate-50/80' : 'border border-slate-800 bg-slate-950/60'">
                        <div class="text-[11px] uppercase tracking-[0.24em] text-slate-500">Pagination</div>
                        <div class="mt-2 text-[14px]" :class="isLightTheme ? 'text-slate-700' : 'text-slate-300'">Designed for long-running tenant queues</div>
                    </div>
                </div>
            </section>
            </div>
        </div>
    </AppLayout>
</template>
