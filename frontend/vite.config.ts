import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const apiPrefix = process.env.API_PREFIX || "/obsidian-knowledge";
const backendUrl = process.env.BACKEND_URL || "http://localhost:3105";

export default defineConfig({
  plugins: [react()],
  base: `${apiPrefix}/`,
  define: {
    __API_PREFIX__: JSON.stringify(apiPrefix),
  },
  server: {
    host: "0.0.0.0",
    allowedHosts: true,
    port: parseInt(process.env.PORT || "8104"),
    proxy: {
      [`${apiPrefix}/api/`]: backendUrl,
      [`${apiPrefix}/mcp/`]: backendUrl,
    },
  },
});
