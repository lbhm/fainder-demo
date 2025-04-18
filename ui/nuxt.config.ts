import vuetify, { transformAssetUrls } from "vite-plugin-vuetify";
// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  ssr: false,
  compatibilityDate: "2024-11-01",
  devtools: { enabled: true },
  build: {
    transpile: ["vuetify"],
  },
  alias: {
    "#app-manifest": "node_modules/nuxt/dist/app/composables/manifest.js",
  },
  modules: [
    (_options, nuxt) => {
      nuxt.hooks.hook("vite:extendConfig", (config) => {
        // @ts-expect-error - This is a private API
        config.plugins.push(vuetify({ autoImport: true }));
      });
    },
    "@nuxtjs/mdc",
    "@nuxtjs/color-mode",
    ...(process.env.NODE_ENV === "production"
      ? []
      : ["@nuxt/test-utils/module"]),
  ],
  runtimeConfig: {
    public: {
      apiBase: process.env.NUXT_API_BASE || "http://localhost:8000",
    },
  },
  vite: {
    vue: {
      template: {
        transformAssetUrls,
      },
    },
  },
  mdc: {
    // TODO: Document why we use this
    headings: {
      anchorLinks: {
        h3: false,
      },
    },
  },
  app: {
    head: {
      script: [
        {
          src: "https://cdn.jsdelivr.net/gh/WebCoder49/code-input@2.3/code-input.min.js",
          body: true,
        },
      ],
      link: [
        {
          rel: "stylesheet",
          href: "https://cdn.jsdelivr.net/gh/WebCoder49/code-input@2.3/code-input.min.css",
        },
      ],
    },
  },
});
