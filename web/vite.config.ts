import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // Override when something else already owns port 8000:
      //   FOREMAN_API_URL=http://localhost:8001 npm run dev
      "/api": { target: process.env.FOREMAN_API_URL ?? "http://localhost:8000", changeOrigin: true },
    },
  },
});
