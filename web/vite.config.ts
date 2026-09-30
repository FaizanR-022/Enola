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
      // Vite 8 rejects unfamiliar Host headers. Naming the local aliases here lets
      // http://enola.localhost:5173 and http://enola.test:5173 work; IP literals and
      // plain localhost are permitted by Vite regardless, so LAN access is unaffected.
      // Use .localhost (resolves to loopback with no setup) or .test (needs a hosts
      // entry). Never .local — that is mDNS and makes Windows DNS crawl — and never
      // .dev, which browsers force to HTTPS.
      allowedHosts: ["enola.localhost", "enola.test", ...(env["VITE_ALLOWED_HOSTS"] || "").split(",").filter(Boolean)],
      proxy: {
        "/api": { target: apiTarget, changeOrigin: false },
        "/health": { target: apiTarget, changeOrigin: false },
      },
    },
  };
});
