import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

export default defineConfig({
  // The components are rendered with renderToStaticMarkup rather than mounted in
  // a DOM, so no jsdom is needed. esbuild has to be told to transform JSX because
  // the Next tsconfig sets "jsx": "preserve" for the Next compiler's benefit.
  esbuild: { jsx: "automatic" },
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  test: {
    environment: "node",
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
