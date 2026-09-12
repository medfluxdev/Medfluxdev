/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  webpack(config) {
    // pdfjs-dist's build statically imports a Node-only display module whose
    // NodeCanvasFactory does `require("canvas")`. The browser PDF viewer uses
    // the DOM canvas (never the Node one), so webpack only needs to resolve
    // `canvas` to an empty module to compile — it must NOT install the native
    // node-canvas package. This mirrors pdfjs-dist's own package.json
    // `browser` field (canvas: false) for Next's universal/SSR compilation.
    config.resolve.alias = {
      ...config.resolve.alias,
      canvas: false,
    };
    return config;
  },
  async headers() {
    const csp = [
      "default-src 'self'",
      // Next.js currently emits inline bootstrap/style fragments; unsafe-inline
      // remains explicit rather than falling back to an unrestricted default-src.
      "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data: blob:",
      "font-src 'self' data:",
      "connect-src 'self' http://localhost:8000 http://127.0.0.1:8000",
      "worker-src 'self' blob:",
      "object-src 'none'",
      "base-uri 'self'",
      "form-action 'self'",
      "frame-ancestors 'none'",
    ].join('; ');

    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "no-referrer" },
          { key: "X-Frame-Options", value: "DENY" },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
          },
          { key: "Content-Security-Policy", value: csp },
        ],
      },
    ];
  },
};

module.exports = nextConfig;
