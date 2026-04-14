import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx}",
    "./components/**/*.{js,ts,jsx,tsx}",
    "./lib/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        ims: {
          bg: "#0A0E1A",
          "bg-panel": "#0F1420",
          "bg-card": "#141926",
          teal: "#00D4FF",
          bullish: "#00FF88",
          bearish: "#FF3B5C",
          warning: "#FFB800",
          "text-primary": "#E2E8F0",
          "text-secondary": "#64748B",
          border: "#1E2A3A",
          "border-light": "#2A3A4E",
        },
      },
      fontFamily: {
        mono: ["JetBrains Mono", "Fira Code", "monospace"],
        sans: ["IBM Plex Sans", "system-ui", "sans-serif"],
      },
      keyframes: {
        pulse: {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.7" },
        },
        "slide-in": {
          "0%": { transform: "translateY(-4px)", opacity: "0" },
          "100%": { transform: "translateY(0)", opacity: "1" },
        },
      },
      animation: {
        "data-pulse": "pulse 2s ease-in-out infinite",
        "slide-in": "slide-in 0.3s ease-out",
      },
    },
  },
  plugins: [],
};

export default config;
