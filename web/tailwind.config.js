/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)",
        elev: "var(--bg-elev)",
        surface: "var(--surface)",
        "surface-2": "var(--surface-2)",
        line: "var(--border)",
        "line-strong": "var(--border-strong)",
        text: "var(--text)",
        muted: "var(--muted)",
        faint: "var(--faint)",
        amber: "var(--amber)",
        "amber-bright": "var(--amber-bright)",
        red: "var(--red)",
        green: "var(--green)",
        steel: "var(--steel)",
        "steel-bright": "var(--steel-bright)",
      },
      fontFamily: {
        display: ['"Space Grotesk"', "sans-serif"],
        sans: ['"Geist Variable"', "system-ui", "sans-serif"],
        mono: ['"Geist Mono Variable"', "ui-monospace", "monospace"],
      },
      letterSpacing: { micro: "0.18em" },
      boxShadow: {
        glow: "0 0 0 1px rgba(245,166,35,0.2), 0 8px 40px -8px rgba(245,166,35,0.25)",
        panel: "0 2px 20px -4px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.04)",
      },
      keyframes: {
        "fade-up": {
          from: { opacity: 0, transform: "translateY(16px)" },
          to: { opacity: 1, transform: "translateY(0)" },
        },
        "pulse-node": {
          "0%,100%": { filter: "drop-shadow(0 0 3px rgba(245,166,35,0.4))" },
          "50%": { filter: "drop-shadow(0 0 12px rgba(245,166,35,0.8))" },
        },
        marquee: { from: { transform: "translateX(0)" }, to: { transform: "translateX(-50%)" } },
      },
      animation: {
        "fade-up": "fade-up 0.6s cubic-bezier(0.16,1,0.3,1) both",
        "pulse-node": "pulse-node 2s ease-in-out infinite",
        marquee: "marquee 30s linear infinite",
      },
    },
  },
  plugins: [],
};
