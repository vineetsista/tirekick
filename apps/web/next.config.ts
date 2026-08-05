import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  transpilePackages: ["@tirekick/shared"],
  typescript: {
    // Never silently ship type errors; `pnpm typecheck` is a CI gate.
    ignoreBuildErrors: false,
  },
  experimental: {
    serverActions: {
      // The upload action receives inspection media. Its own per-file and
      // total caps live in app/new/actions.ts; this is the transport ceiling
      // above them, not the policy.
      bodySizeLimit: "220mb",
    },
  },
};

export default nextConfig;
