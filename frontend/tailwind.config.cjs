/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{html,svelte,ts}'],
  theme: {
    extend: {
      colors: {
        ink:    { 900: '#0F1413', 800: '#1E2625', 700: '#2E3837', 500: '#5E6968' },
        canvas: { 50:  '#FAFAF6', 100: '#F2F0E8' },
        accent: { 500: '#0F8C5A', 600: '#0B6F47' },
      },
      fontFamily: {
        sans:    ['"Be Vietnam Pro"', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        display: ['Lora', 'ui-serif', 'serif'],
        mono:    ['"JetBrains Mono"', 'ui-monospace', 'monospace'],
      },
      borderRadius: { glass: '20px', chip: '999px' },
      boxShadow: {
        glass:    '0 1px 0 rgba(255,255,255,0.4) inset, 0 8px 30px rgba(15,20,19,0.08)',
        glassLg:  '0 1px 0 rgba(255,255,255,0.5) inset, 0 16px 50px rgba(15,20,19,0.12)',
      },
      backdropBlur: { glass: '20px' },
    },
  },
  plugins: [],
};
