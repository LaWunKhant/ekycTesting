import { onMounted, ref } from 'vue';

export type Appearance = 'light' | 'dark' | 'system';

const DEFAULT_APPEARANCE: Appearance = 'dark';
const appearance = ref<Appearance>(DEFAULT_APPEARANCE);

const prefersDarkMode = () => window.matchMedia('(prefers-color-scheme: dark)').matches;

const applyAppearanceClass = (value: Appearance) => {
    document.documentElement.classList.remove('appearance-light', 'appearance-dark', 'appearance-system');
    document.documentElement.classList.add(`appearance-${value}`);
    document.documentElement.dataset.appearance = value;
};

export function updateTheme(value: Appearance) {
    appearance.value = value;

    const shouldUseDarkPalette = value === 'dark' || (value === 'system' && prefersDarkMode());
    document.documentElement.classList.toggle('dark', shouldUseDarkPalette);
    applyAppearanceClass(value);
}

const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');

const handleSystemThemeChange = () => {
    const currentAppearance = localStorage.getItem('appearance') as Appearance | null;
    updateTheme(currentAppearance || DEFAULT_APPEARANCE);
};

export function initializeTheme() {
    const savedAppearance = localStorage.getItem('appearance') as Appearance | null;
    updateTheme(savedAppearance || DEFAULT_APPEARANCE);
    mediaQuery.addEventListener('change', handleSystemThemeChange);
}

export function useAppearance() {
    onMounted(() => {
        initializeTheme();

        const savedAppearance = localStorage.getItem('appearance') as Appearance | null;

        if (savedAppearance) {
            appearance.value = savedAppearance;
        } else {
            appearance.value = DEFAULT_APPEARANCE;
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
