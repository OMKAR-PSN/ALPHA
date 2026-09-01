/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        navy: {
          50: '#e8edf5',
          100: '#c5d0e3',
          200: '#9fb0d0',
          300: '#7890bc',
          400: '#5a77ae',
          500: '#3c5d9f',
          600: '#2c4b8f',
          700: '#1e3878',
          800: '#152c65',
          900: '#0F2A4A',
          950: '#091a32',
        },
        teal: {
          50: '#e6f4f4',
          100: '#c0e3e3',
          200: '#97d0d0',
          300: '#6ebdbd',
          400: '#4aafaf',
          500: '#26a0a0',
          600: '#1A8080',
          700: '#166868',
          800: '#115050',
          900: '#0a3838',
        },
        rs: {
          navy: '#0F2A4A',
          teal: '#1A6B6B',
          orange: '#E07B39',
          amber: '#D97706',
          green: '#2E7D52',
          bg: '#F5F7FA',
          panel: '#FFFFFF',
          border: '#E2E8F0',
          'text-primary': '#0F172A',
          'text-secondary': '#475569',
          'text-muted': '#94A3B8',
        }
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      animation: {
        'fade-in': 'fadeIn 0.4s ease-out',
        'slide-up': 'slideUp 0.4s ease-out',
        'pulse-slow': 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'spin-slow': 'spin 3s linear infinite',
        'trace-appear': 'traceAppear 0.5s ease-out forwards',
        'progress': 'progress 1.5s ease-in-out infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: 0 },
          '100%': { opacity: 1 },
        },
        slideUp: {
          '0%': { opacity: 0, transform: 'translateY(12px)' },
          '100%': { opacity: 1, transform: 'translateY(0)' },
        },
        traceAppear: {
          '0%': { opacity: 0, transform: 'translateX(-10px)' },
          '100%': { opacity: 1, transform: 'translateX(0)' },
        },
        progress: {
          '0%': { width: '0%' },
          '50%': { width: '75%' },
          '100%': { width: '100%' },
        },
      },
      boxShadow: {
        'panel': '0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.06)',
        'panel-md': '0 4px 12px rgba(0,0,0,0.1), 0 2px 4px rgba(0,0,0,0.06)',
        'panel-lg': '0 10px 30px rgba(0,0,0,0.12), 0 4px 8px rgba(0,0,0,0.08)',
        'navy': '0 4px 14px rgba(15,42,74,0.25)',
      },
    },
  },
  plugins: [],
}
