/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#ebf8ff',
          100: '#d6eef8',
          200: '#addcf0',
          300: '#84cbe8',
          400: '#5bbae0',
          500: '#32a9d8',
          600: '#0e7490', // Base cyan-700
          700: '#0c6478',
          800: '#0a5260',
          900: '#083e48',
        },
      },
    },
  },
  plugins: [],
} 