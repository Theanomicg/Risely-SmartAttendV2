/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        navy: {
          950: '#060B18',
          900: '#0A0E1A',
          800: '#0D1526',
          700: '#131929',
          600: '#1A2138',
          500: '#1E2A45',
          400: '#243154',
        },
        brand: {
          blue:  '#4A90D9',
          cyan:  '#38BDF8',
          purple:'#7C5CFC',
        },
      },
      fontFamily: {
        display: ['"DM Sans"', 'sans-serif'],
        body:    ['"Inter"', 'sans-serif'],
        mono:    ['"JetBrains Mono"', 'monospace'],
      },
    },
  },
  plugins: [],
}
