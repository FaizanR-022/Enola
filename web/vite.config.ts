import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";

// The API location comes from the repo-root .env, never from a literal here.
// In dev the app is same-origin: /api and /health are proxied to the API so the
// session cookie works whether you open localhost or 127.0.0.1.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, fileURLToPath(new URL("..", import.meta.url)), "");
  const apiTarget = env["VITE_API_PROXY_TARGET"] || `http://${env["ENOLA_API_HOST"] || "127.0.0.1"}:${env["ENOLA_API_PORT"] || "8000"}`;
  return {
    plugins: [react()],
    envDir: "..",
    resolve: {
      alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
    },
    server: {
      host: true,
      proxy: {
        "/api": { target: apiTarget, changeOrigin: false },
        "/health": { target: apiTarget, changeOrigin: false },
      },
    },
  };
});
