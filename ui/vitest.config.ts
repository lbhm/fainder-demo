import { defineVitestConfig } from "@nuxt/test-utils/config";

export default defineVitestConfig({
  // any custom Vitest config you require
  test: {
    // Define projects instead of environmentMatchGlobs for Vitest 3+ compatibility
    projects: [
      {
        test: {
          environment: "node",
        },
      },
    ],
  },
});
