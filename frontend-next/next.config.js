/** @type {import('next').NextConfig} */
const nextConfig = {
  // Set NEXT_STATIC_EXPORT=1 when building for nginx static serving.
  // Leave unset for `next dev` and `next start`.
  ...(process.env.NEXT_STATIC_EXPORT === '1' ? { output: 'export', trailingSlash: true } : {}),
  images: { unoptimized: true },
  env: {
    NEXT_PUBLIC_API_BASE: process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000',
  },
};

module.exports = nextConfig;
