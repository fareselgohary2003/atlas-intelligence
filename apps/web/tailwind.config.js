module.exports = {
  darkMode: "class",
  content: ["./app/**/*.tsx", "./components/**/*.tsx"],
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)",
        card: "var(--card)",
        bd: "var(--bd)",
        tx: "var(--tx)",
        mut: "var(--mut)",
        acc: "var(--acc)",
        "acc-light": "var(--acc-light)",
        "acc-dark": "var(--acc-dark)",
        success: "var(--success)",
        warning: "var(--warning)",
        danger: "var(--danger)",
        side: "var(--side)",
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "-apple-system", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      borderRadius: {
        DEFAULT: "var(--radius)",
        sm: "var(--radius-sm)",
        lg: "var(--radius-lg)",
      },
      boxShadow: {
        sm: "var(--shadow-sm)",
        md: "var(--shadow-md)",
        lg: "var(--shadow-lg)",
      },
    },
  },
};
