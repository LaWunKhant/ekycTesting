import { onMounted, ref } from 'vue';

export type Appearance = 'light' | 'dark' | 'system';

const appearance = ref<Appearance>('system');

const applyAppearanceClass = (value: Appearance) => {
    document.documentElement.classList.remove('appearance-light', 'appearance-dark', 'appearance-system');
    document.documentElement.classList.add(`appearance-${value}`);
    document.documentElement.dataset.appearance = value;
};

export function updateTheme(value: Appearance) {
    appearance.value = value;
    document.documentElement.classList.toggle('dark', value !== 'light');
    applyAppearanceClass(value);
}

const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');

const handleSystemThemeChange = () => {
    const currentAppearance = localStorage.getItem('appearance') as Appearance | null;
    updateTheme(currentAppearance || 'system');
};

export function initializeTheme() {
    const savedAppearance = localStorage.getItem('appearance') as Appearance | null;
    updateTheme(savedAppearance || 'system');
    mediaQuery.addEventListener('change', handleSystemThemeChange);
}

export function useAppearance() {
    onMounted(() => {
        initializeTheme();

        const savedAppearance = localStorage.getItem('appearance') as Appearance | null;

        if (savedAppearance) {
            appearance.value = savedAppearance;
        }
    });

    function updateAppearance(value: Appearance) {
        appearance.value = value;
        localStorage.setItem('appearance', value);
        updateTheme(value);
    }

    return {
        appearance,
        updateAppearance,
    };
}
