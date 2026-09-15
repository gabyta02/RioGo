import { appColors, fontFamily } from "./src/core/theme.js";

/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        app: appColors,
      },
      fontFamily: {
        sans: [fontFamily],
      },
    },
  },
  plugins: [],
};
