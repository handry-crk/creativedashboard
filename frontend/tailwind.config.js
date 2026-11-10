/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        brand: { DEFAULT: "#D7191F", deep: "#B32E26", tint: "#F7D4D5", line: "#EBD9DA", cream: "#FFF4E0", yellow: "#F5B800", ink: "#1F1A1A" },
      },
      fontFamily: { sans: ['"Plus Jakarta Sans"', "system-ui", "sans-serif"] },
    },
  },
  plugins: [],
};
