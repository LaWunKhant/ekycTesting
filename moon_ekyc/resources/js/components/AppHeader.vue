<script setup lang="ts">
import AppLogo from '@/components/AppLogo.vue';
import AppLogoIcon from '@/components/AppLogoIcon.vue';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Button } from '@/components/ui/button';
import { DropdownMenu, DropdownMenuContent, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from '@/components/ui/sheet';
import UserMenuContent from '@/components/UserMenuContent.vue';
import { getInitials } from '@/composables/useInitials';
import type { BreadcrumbItem, NavItem } from '@/types';
import { Link, usePage } from '@inertiajs/vue3';
import { LayoutGrid, Menu, ShieldCheck, Users, WalletCards } from 'lucide-vue-next';
import { computed } from 'vue';

interface Props {
    breadcrumbs?: BreadcrumbItem[];
}

const props = withDefaults(defineProps<Props>(), {
    breadcrumbs: () => [],
});

const page = usePage();
const auth = computed(() => page.props.auth);

const isCurrentRoute = (url: string) => {
    return page.url === url;
};

const activeItemStyles = computed(() => (url: string) =>
    isCurrentRoute(url)
        ? 'border-cyan-500/40 bg-cyan-500/10 text-cyan-100'
        : 'text-slate-300 hover:border-slate-600 hover:bg-slate-800/60 hover:text-white',
);

const mainNavItems: NavItem[] = [
    {
        title: 'Dashboard',
        href: '/dashboard',
        icon: LayoutGrid,
    },
    {
        title: 'Sessions',
        href: '/sessions',
        icon: WalletCards,
    },
    {
        title: 'Team',
        href: '/team',
        icon: Users,
    },
    {
        title: 'Review',
        href: '/review',
        icon: ShieldCheck,
    },
];
</script>

<template>
    <div class="sticky top-0 z-30 border-b border-slate-800/90 bg-[#0b1022]/95 backdrop-blur">
        <div class="mx-auto flex h-20 items-center px-4 md:max-w-7xl">
                <!-- Mobile Menu -->
                <div class="lg:hidden">
                    <Sheet>
                        <SheetTrigger :as-child="true">
                            <Button variant="ghost" size="icon" class="mr-2 h-10 w-10 rounded-full border border-slate-700 text-slate-200">
                                <Menu class="h-5 w-5" />
                            </Button>
                        </SheetTrigger>
                        <SheetContent side="left" class="w-[300px] border-slate-800 bg-[#0b1022] p-6 text-white">
                            <SheetTitle class="sr-only">Navigation Menu</SheetTitle>
                            <SheetHeader class="flex justify-start text-left">
                                <AppLogoIcon class="size-6 fill-current text-white" />
                            </SheetHeader>
                            <div class="flex h-full flex-1 flex-col justify-between space-y-4 py-6">
                                <nav class="-mx-3 space-y-1">
                                    <Link
                                        v-for="item in mainNavItems"
                                        :key="item.title"
                                        :href="item.href"
                                        class="flex items-center gap-x-3 rounded-2xl border border-transparent px-3 py-3 text-sm font-medium transition"
                                        :class="activeItemStyles(item.href)"
                                    >
                                        <component v-if="item.icon" :is="item.icon" class="h-5 w-5" />
                                        {{ item.title }}
                                    </Link>
                                </nav>
                            </div>
                        </SheetContent>
                    </Sheet>
                </div>

                <Link :href="route('dashboard')" class="flex items-center gap-x-3">
                    <div class="flex h-11 w-11 items-center justify-center rounded-2xl border border-cyan-500/20 bg-cyan-500/10">
                        <AppLogoIcon class="size-6 fill-current text-cyan-200" />
                    </div>
                    <div class="hidden sm:block">
                        <div class="text-sm font-semibold text-white">MoonKYC Tenant</div>
                        <div class="text-xs text-slate-400">Portal</div>
                    </div>
                    <AppLogo class="hidden h-6 xl:block" />
                </Link>

                <!-- Desktop Menu -->
                <div class="hidden lg:flex lg:flex-1">
                    <nav class="ml-10 flex items-center gap-3">
                        <Link
                            v-for="item in mainNavItems"
                            :key="item.title"
                            :href="item.href"
                            class="inline-flex items-center gap-2 rounded-full border px-4 py-2.5 text-sm font-medium transition"
                            :class="activeItemStyles(item.href)"
                        >
                            <component v-if="item.icon" :is="item.icon" class="h-4 w-4" />
                            {{ item.title }}
                        </Link>
                    </nav>
                </div>

                <div class="ml-auto flex items-center space-x-3">
                    <DropdownMenu>
                        <DropdownMenuTrigger :as-child="true">
                            <Button
                                variant="ghost"
                                size="icon"
                                class="relative h-12 w-auto rounded-full border border-slate-700 bg-slate-900/70 px-2.5 focus-within:ring-2 focus-within:ring-cyan-400"
                            >
                                <Avatar class="size-8 overflow-hidden rounded-full">
                                    <AvatarImage :src="auth.user.avatar" :alt="auth.user.name" />
                                    <AvatarFallback class="rounded-lg bg-slate-700 font-semibold text-white">
                                        {{ getInitials(auth.user?.name) }}
                                    </AvatarFallback>
                                </Avatar>
                                <span class="hidden max-w-[8rem] truncate pl-2 text-sm font-medium text-slate-200 sm:block">
                                    {{ auth.user?.name }}
                                </span>
                            </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end" class="w-56 border-slate-800 bg-[#0b1022] text-white">
                            <UserMenuContent :user="auth.user" />
                        </DropdownMenuContent>
                    </DropdownMenu>
                </div>
            </div>
        <div v-if="props.breadcrumbs.length > 1" class="flex w-full border-t border-slate-800/80 bg-[#0b1022]/95">
            <div class="mx-auto flex h-12 w-full items-center justify-start px-4 text-slate-500 md:max-w-7xl">
                <Breadcrumbs :breadcrumbs="breadcrumbs" />
            </div>
        </div>
    </div>
</template>
