/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        playto: {
          blue: '#2563EB',
          dark: '#1E293B',
        },
      },
    },
  },
  plugins: [],
};
