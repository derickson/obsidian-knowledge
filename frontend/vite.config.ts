import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const apiPrefix = process.env.API_PREFIX || "/obsidian-knowledge";

export default defineConfig({
  plugins: [react()],
  define: {
    __API_PREFIX__: JSON.stringify(apiPrefix),
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      [apiPrefix]: "http://backend:8000",
    },
  },
});
