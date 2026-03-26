<script setup lang="ts">
import InputError from '@/components/InputError.vue';
import TextLink from '@/components/TextLink.vue';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import AuthBase from '@/layouts/AuthLayout.vue';
import { Head, useForm } from '@inertiajs/vue3';
import { LoaderCircle } from 'lucide-vue-next';

defineProps<{
    status?: string;
    canResetPassword: boolean;
    tenantName?: string | null;
    tenantSlug?: string | null;
}>();

const form = useForm({
    email: '',
    password: '',
    remember: false,
});

const submit = () => {
    form.post(route('login'), {
        onFinish: () => form.reset('password'),
    });
};
</script>

<template>
    <AuthBase
        :title="tenantName ? `${tenantName} Workspace` : 'MoonKYC Business'"
        :description="tenantName ? `Sign in to the ${tenantName} tenant workspace` : 'Sign in to your workspace'"
    >
        <Head title="Log in" />

        <div v-if="tenantSlug" class="mb-4 rounded-2xl border border-cyan-500/20 bg-cyan-500/10 px-4 py-3 text-center text-sm font-medium text-cyan-300">
            Workspace verified: {{ tenantSlug }}
        </div>

        <div v-if="status" class="mb-4 rounded-2xl border border-emerald-500/20 bg-emerald-500/10 px-4 py-3 text-center text-sm font-medium text-emerald-300">
            {{ status }}
        </div>

        <form @submit.prevent="submit" class="flex flex-col gap-5">
            <div class="grid gap-5">
                <div class="grid gap-2.5">
                    <Label for="email" class="text-sm font-medium text-slate-200">Email</Label>
                    <Input
                        id="email"
                        type="email"
                        required
                        autofocus
                        tabindex="1"
                        autocomplete="email"
                        v-model="form.email"
                        placeholder=""
                        class="h-12 rounded-xl border-slate-700 bg-slate-950 text-white placeholder:text-slate-500 focus-visible:border-cyan-400 focus-visible:ring-cyan-400/30"
                    />
                    <InputError :message="form.errors.email" />
                </div>

                <div class="grid gap-2.5">
                    <div class="flex items-center justify-between gap-3">
                        <Label for="password" class="text-sm font-medium text-slate-200">Password</Label>
                        <TextLink
                            v-if="canResetPassword"
                            :href="route('password.request')"
                            class="text-sm font-medium text-cyan-200 underline decoration-cyan-300 underline-offset-4 hover:text-cyan-100"
                            tabindex="5"
                        >
                            Forgot password?
                        </TextLink>
                    </div>
                    <Input
                        id="password"
                        type="password"
                        required
                        tabindex="2"
                        autocomplete="current-password"
                        v-model="form.password"
                        placeholder=""
                        class="h-12 rounded-xl border-slate-700 bg-slate-950 text-white placeholder:text-slate-500 focus-visible:border-cyan-400 focus-visible:ring-cyan-400/30"
                    />
                    <InputError :message="form.errors.password" />
                </div>

                <div class="flex items-center justify-between pt-1" tabindex="3">
                    <Label for="remember" class="flex items-center space-x-3 text-sm text-slate-300">
                        <Checkbox id="remember" v-model:checked="form.remember" tabindex="4" />
                        <span>Remember me</span>
                    </Label>
                </div>

                <Button
                    type="submit"
                    class="mt-2 h-12 w-full rounded-xl bg-cyan-400 text-base font-semibold text-slate-950 shadow-none hover:bg-cyan-300"
                    tabindex="4"
                    :disabled="form.processing"
                >
                    <LoaderCircle v-if="form.processing" class="h-4 w-4 animate-spin" />
                    Sign in
                </Button>
            </div>
        </form>
    </AuthBase>
</template>
