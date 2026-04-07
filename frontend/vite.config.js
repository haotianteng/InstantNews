import { defineConfig } from "vite";
import { resolve } from "path";

export default defineConfig({
  root: ".",
  publicDir: "public",

  build: {
    outDir: resolve(__dirname, "..", "static"),
    emptyOutDir: true,
    rollupOptions: {
      input: {
        landing: resolve(__dirname, "index.html"),
        terminal: resolve(__dirname, "terminal.html"),
        account: resolve(__dirname, "account.html"),
        pricing: resolve(__dirname, "pricing.html"),
        docs: resolve(__dirname, "docs.html"),
        privacy: resolve(__dirname, "privacy.html"),
        terms: resolve(__dirname, "terms.html"),
        admin: resolve(__dirname, "admin.html"),
      },
    },
  },

  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/admin/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },

  plugins: [
    // Rewrite clean URLs to .html files for dev server
    {
      name: "html-rewrite",
      configureServer(server) {
        server.middlewares.use((req, res, next) => {
          const cleanRoutes = [
            "/terminal",
            "/account",
            "/pricing",
            "/docs",
            "/privacy",
            "/terms",
            "/admin",
          ];
          const pathname = req.url.split("?")[0];
          if (cleanRoutes.includes(pathname)) {
            const query = req.url.includes("?")
              ? "?" + req.url.split("?")[1]
              : "";
            req.url = pathname + ".html" + query;
          }
          // /docs/* sub-routes → docs.html
          if (pathname.startsWith("/docs/")) {
            req.url = "/docs.html";
          }
          next();
        });
      },
    },
  ],
});
