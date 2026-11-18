import { defineConfig } from "vite";

export default defineConfig({
  publicDir: false,
  build: {
    rolldownOptions: {
      output: {
        entryFileNames: "assets/studio.js",
        assetFileNames: "assets/[name][extname]",
      },
    },
  },
});
