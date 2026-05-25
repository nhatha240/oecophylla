/* Tailwind config + theme extension for Oecophylla glass.
   This sets up tailwind.config BEFORE the Play CDN script runs. */

window.tailwind = window.tailwind || {};
window.tailwind.config = {
  darkMode: ['class', '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        ink:    { DEFAULT: '#0B1212', 2: '#2D3633' },
        muted:  { DEFAULT: '#5C6660', 2: '#8C948F' },
        emerald: {
          50:  '#E3F7EC',
          100: '#BDEBD0',
          200: '#90DBB1',
          300: '#5FC68D',
          400: '#2EB270',
          500: '#00A66B',
          600: '#008A57',
          700: '#007048',
          800: '#005635',
          900: '#003D24',
        },
        glass: {
          base:    'rgba(255, 255, 255, 0.55)',
          strong:  'rgba(255, 255, 255, 0.78)',
          soft:    'rgba(255, 255, 255, 0.35)',
          'dark-base': 'rgba(28, 36, 32, 0.55)',
        },
      },
      fontFamily: {
        sans: ['"SF Pro Display"', '-apple-system', 'BlinkMacSystemFont', '"Be Vietnam Pro"', 'system-ui', 'sans-serif'],
        serif: ['Lora', 'Georgia', 'serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'monospace'],
      },
      borderRadius: {
        '4xl': '28px',
        '5xl': '36px',
      },
      boxShadow: {
        'glass':    '0 12px 32px -10px rgba(15, 50, 35, 0.18), 0 4px 12px -4px rgba(15, 50, 35, 0.10)',
        'glass-lg': '0 32px 64px -20px rgba(15, 50, 35, 0.30), 0 10px 24px -10px rgba(15, 50, 35, 0.18)',
        'glass-inner': 'inset 0 1px 0 0 rgba(255, 255, 255, 0.9), inset 0 0 0 1px rgba(255, 255, 255, 0.55)',
        'glow-emerald': '0 8px 24px -6px rgba(0, 170, 100, 0.5), inset 0 1px 0 rgba(255,255,255,0.4)',
        'glass-pill': 'inset 0 1px 0 rgba(255,255,255,0.9), 0 4px 12px -4px rgba(0, 60, 40, 0.20)',
      },
      backgroundImage: {
        'emerald-grad': 'linear-gradient(160deg, #00C480 0%, #008A57 100%)',
        'ink-grad':     'linear-gradient(160deg, #1F2624 0%, #0B1212 100%)',
        'glass-grad':   'linear-gradient(160deg, rgba(255,255,255,0.95) 0%, rgba(255,255,255,0.75) 100%)',
        'glass-grad-dark': 'linear-gradient(160deg, rgba(255,255,255,0.18) 0%, rgba(255,255,255,0.06) 100%)',
      },
      keyframes: {
        toastIn: { from: { opacity: 0, transform: 'translate(-50%, 10px)' }, to: { opacity: 1, transform: 'translate(-50%, 0)' } },
      },
      animation: {
        'toast-in': 'toastIn .25s ease',
      },
    },
  },
};
