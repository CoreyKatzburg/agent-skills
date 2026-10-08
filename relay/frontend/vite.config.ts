import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// In development, Vite serves the React app and forwards API calls (and the live-update
// WebSocket) to the FastAPI backend, so the browser only ever talks to one address.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/v1": { target: "http://localhost:8000", ws: true },
    },
  },
});
