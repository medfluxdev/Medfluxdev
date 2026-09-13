/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  webpack(config) {
    // pdfjs-dist's build statically imports a Node-only display module whose
    // NodeCanvasFactory does `require("canvas")`. The browser PDF viewer uses
    // the DOM canvas (never the Node one), so webpack only needs to resolve
    // `canvas` to an empty module to compile — it must NOT install the native
    // node-canvas package. This mirrors pdfjs-dist's own package.json
    // `browser` field (canvas: false) for Next's universal/SSR compilation,
    // which otherwise ignores the browser field and fails to resolve canvas.
    config.resolve.alias = {
      ...config.resolve.alias,
      canvas: false,
    };
    return config;
  },
  async headers() {
    return [
      {
        // Sicherheits-Header für alle Routen.
        // Bewusst KEIN restriktives default-src-CSP: die aktuelle App nutzt
        // Inline-Styles und lädt das Dashboard clientseitig vom lokalen Backend
        // (Cross-Origin). Ein zu striktes CSP würde diese Seitenseite brechen.
        // Ein vollumfängliches CSP folgt zusammen mit Authentifizierung in STEP 16.
        source: "/(.*)",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "X-Frame-Options", value: "DENY" },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=(), payment=()",
          },
          {
            key: "Content-Security-Policy",
            value: "frame-ancestors 'none'",
          },
        ],
      },
    ];
  },
};

module.exports = nextConfig;
