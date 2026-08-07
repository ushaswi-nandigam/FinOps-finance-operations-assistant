/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        tier0: "#16a34a",
        tier1: "#65a30d",
        tier2: "#d97706",
        tier3: "#dc2626",
      },
    },
  },
  plugins: [],
};
