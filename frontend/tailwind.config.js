/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ll: {
          bg: "rgb(var(--ll-bg) / <alpha-value>)",
          surface: "rgb(var(--ll-surface) / <alpha-value>)",
          text: "rgb(var(--ll-text) / <alpha-value>)",
          muted: "rgb(var(--ll-muted) / <alpha-value>)",
          accent: "rgb(var(--ll-accent) / <alpha-value>)",
          danger: "rgb(var(--ll-danger) / <alpha-value>)",
          warn: "rgb(var(--ll-warn) / <alpha-value>)",
          border: "rgb(var(--ll-border) / <alpha-value>)",
          card: "rgb(var(--ll-card) / <alpha-value>)",
          input: "rgb(var(--ll-input) / <alpha-value>)",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};
