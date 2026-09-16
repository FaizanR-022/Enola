import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";

// No hardcoded hosts: the API base URL is read by the app from VITE_API_BASE_URL.
export default defineConfig({
  plugins: [react()],
  envDir: "..",
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  server: { host: true },
});
