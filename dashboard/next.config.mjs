/** @type {import('next').NextConfig} */
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    // Proxy API calls to the FastAPI backend (avoids CORS in dev).
    return [{ source: "/api/v1/:path*", destination: `${API_BASE}/api/v1/:path*` }];
  },
};
export default nextConfig;
