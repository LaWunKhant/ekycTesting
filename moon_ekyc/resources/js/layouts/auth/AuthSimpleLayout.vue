<script setup lang="ts">
defineProps<{
    title?: string;
    description?: string;
}>();
</script>

<template>
    <div class="relative flex min-h-svh items-center justify-center overflow-hidden bg-[radial-gradient(circle_at_top,_rgba(30,41,59,0.55),_transparent_28%),linear-gradient(180deg,_#020617_0%,_#030617_38%,_#02030f_100%)] px-4 py-10 sm:px-6">
        <div class="absolute inset-0 bg-[linear-gradient(180deg,rgba(15,23,42,0)_0%,rgba(2,6,23,0.35)_100%)]" />
        <div class="relative w-full max-w-md rounded-[24px] border border-slate-800 bg-slate-950/70 p-7 shadow-[0_30px_80px_rgba(2,6,23,0.6)] backdrop-blur">
            <div class="space-y-2 text-center">
                <h1 class="text-[2rem] font-semibold tracking-tight text-white">{{ title }}</h1>
                <p class="text-sm text-slate-400">{{ description }}</p>
            </div>
            <div class="mt-8">
                <slot />
            </div>
        </div>
    </div>
</template>
