/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  async rewrites() {
    return [
      // Public terra-cortex API proxy
      { source: '/api/cortex/:path*', destination: 'http://terra-cortex:8082/:path*' },
      // Protected Terra-Ops traffic must use /api/dashboard/ops route handlers.
      // No /api/ops rewrite is exposed because it would bypass the HttpOnly BFF.
      // Public terra-sense API proxy
      { source: '/api/sense/:path*', destination: 'http://terra-sense:8081/api/v1/:path*' },
    ];
  },
};

module.exports = nextConfig;
