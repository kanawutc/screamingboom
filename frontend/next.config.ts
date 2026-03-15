import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    return [
      { source: "/api/:path*", destination: "http://backend:8000/api/:path*" },
      { source: "/ws/:path*", destination: "http://backend:8000/ws/:path*" },
    ];
  },
};

export default nextConfig;
