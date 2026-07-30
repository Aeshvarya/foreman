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
        // Channel form so opacity modifiers actually work: bg-amber/10 has to
        // produce a 10% amber wash, not nothing. A bare var(--amber) silently
        // drops the alpha, which left every tint in the UI transparent.
        amber: "rgb(var(--amber-rgb) / <alpha-value>)",
        "amber-bright": "rgb(var(--amber-bright-rgb) / <alpha-value>)",
        red: "rgb(var(--red-rgb) / <alpha-value>)",
        green: "rgb(var(--green-rgb) / <alpha-value>)",
        steel: "rgb(var(--steel-rgb) / <alpha-value>)",
        "steel-bright": "rgb(var(--steel-bright-rgb) / <alpha-value>)",
      },
      fontFamily: {
        display: ['"Bricolage Grotesque Variable"', "sans-serif"],
        sans: ['"Hanken Grotesk Variable"', "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono Variable"', "ui-monospace", "monospace"],
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
