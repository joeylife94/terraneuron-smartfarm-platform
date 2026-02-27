/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  async rewrites() {
    return [
      // terra-cortex API proxy
      { source: '/api/cortex/:path*', destination: 'http://terra-cortex:8082/:path*' },
      // terra-ops API proxy
      { source: '/api/ops/:path*', destination: 'http://terra-ops:8080/api/:path*' },
      // terra-sense API proxy
      { source: '/api/sense/:path*', destination: 'http://terra-sense:8081/api/v1/:path*' },
    ];
  },
};

module.exports = nextConfig;
