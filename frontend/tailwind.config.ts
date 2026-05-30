import type { Config } from 'tailwindcss';

const withOpacity = (name: string) => `rgb(var(${name}) / <alpha-value>)`;

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: withOpacity('--color-ink'),
        canvas: withOpacity('--color-canvas'),
        panel: withOpacity('--color-panel'),
        panelStrong: withOpacity('--color-panel-strong'),
        line: withOpacity('--color-line'),
        muted: withOpacity('--color-muted'),
        cream: withOpacity('--color-cream'),
        brass: withOpacity('--color-brass'),
        ember: withOpacity('--color-ember'),
        signal: withOpacity('--color-signal'),
        success: withOpacity('--color-success'),
        warning: withOpacity('--color-warning'),
        danger: withOpacity('--color-danger'),
      },
      fontFamily: {
        display: ['"Fraunces"', 'Georgia', 'serif'],
        sans: ['"IBM Plex Sans"', 'Verdana', 'sans-serif'],
      },
      boxShadow: {
        panel: 'var(--shadow-panel)',
        glow: 'var(--shadow-glow)',
      },
      borderRadius: {
        card: 'var(--radius-card)',
        pill: 'var(--radius-pill)',
      },
      backgroundImage: {
        'cockpit-grid': 'var(--image-cockpit-grid)',
        'radar-glow': 'var(--image-radar-glow)',
        'grain': 'var(--image-grain)',
      },
      keyframes: {
        reveal: {
          '0%': { opacity: '0', transform: 'translateY(16px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        pulseLine: {
          '0%, 100%': { opacity: '0.35' },
          '50%': { opacity: '0.85' },
        },
      },
      animation: {
        reveal: 'reveal 700ms ease both',
        'pulse-line': 'pulseLine 2200ms ease-in-out infinite',
      },
    },
  },
  plugins: [],
} satisfies Config;
