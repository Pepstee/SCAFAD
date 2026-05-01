import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        // SCAFAD severity palette (CSS vars in tokens.css mirror these)
        sev: {
          observe: "#5b8cff",
          review: "#f5a524",
          escalate: "#ff4d4d",
          info: "#6b7280",
        },
        surface: {
          base: "#0b1020",
          panel: "#111934",
          border: "#1f2a4d",
          subtle: "#16213f",
          muted: "#94a3b8",
        },
        ink: {
          DEFAULT: "#e6ecff",
          dim: "#9aa3bd",
          accent: "#7aa2ff",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "Segoe UI", "Helvetica", "Arial", "sans-serif"],
        mono: ["JetBrains Mono", "Menlo", "Consolas", "monospace"],
      },
      boxShadow: {
        panel: "0 1px 0 0 rgba(255,255,255,0.04), 0 8px 24px -12px rgba(0,0,0,0.5)",
      },
      animation: {
        "glow-pulse-observe": "glow-pulse-observe 2s ease-in-out infinite",
        "glow-pulse-review": "glow-pulse-review 2s ease-in-out infinite",
        "glow-pulse-escalate": "glow-pulse-escalate 2s ease-in-out infinite",
        "fade-up": "fade-up 300ms ease-out",
        "slide-right": "slide-in-right 300ms ease-out",
        "pulse-glow": "pulse-glow 2s ease-in-out infinite",
        "count-tick": "count-tick 300ms ease-out",
      },
      keyframes: {
        "glow-pulse-observe": {
          "0%, 100%": {
            boxShadow: "0 0 12px rgba(91, 140, 255, 0.6), 0 0 24px rgba(91, 140, 255, 0.3)",
          },
          "50%": {
            boxShadow: "0 0 20px rgba(91, 140, 255, 0.8), 0 0 32px rgba(91, 140, 255, 0.4)",
          },
        },
        "glow-pulse-review": {
          "0%, 100%": {
            boxShadow: "0 0 12px rgba(245, 165, 36, 0.6), 0 0 24px rgba(245, 165, 36, 0.3)",
          },
          "50%": {
            boxShadow: "0 0 20px rgba(245, 165, 36, 0.8), 0 0 32px rgba(245, 165, 36, 0.4)",
          },
        },
        "glow-pulse-escalate": {
          "0%, 100%": {
            boxShadow: "0 0 12px rgba(255, 77, 77, 0.6), 0 0 24px rgba(255, 77, 77, 0.3)",
          },
          "50%": {
            boxShadow: "0 0 20px rgba(255, 77, 77, 0.8), 0 0 32px rgba(255, 77, 77, 0.4)",
          },
        },
        "fade-up": {
          from: {
            opacity: "0",
            transform: "translateY(8px)",
          },
          to: {
            opacity: "1",
            transform: "translateY(0)",
          },
        },
        "slide-in-right": {
          from: {
            opacity: "0",
            transform: "translateX(100%)",
          },
          to: {
            opacity: "1",
            transform: "translateX(0)",
          },
        },
        "pulse-glow": {
          "0%, 100%": {
            opacity: "1",
          },
          "50%": {
            opacity: "0.7",
          },
        },
        "count-tick": {
          from: {
            opacity: "0",
            transform: "translateY(-4px)",
          },
          to: {
            opacity: "1",
            transform: "translateY(0)",
          },
        },
      },
    },
  },
  plugins: [],
};

export default config;
