import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  transpilePackages: ["@tirekick/shared"],
  typescript: {
    // Never silently ship type errors; `pnpm typecheck` is a CI gate.
    ignoreBuildErrors: false,
  },
};

export default nextConfig;
