import type { NextConfig } from "next";

// Built as a static export and served by the API process, so production is
// one origin and one thing to run. In development the client talks to the API
// on its own port instead, set by NEXT_PUBLIC_API.
const config: NextConfig = {
  output: "export",
  distDir: "out",
  images: { unoptimized: true },
};

export default config;
