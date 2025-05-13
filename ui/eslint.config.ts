import { createConfigForNuxt } from "@nuxt/eslint-config";

export default createConfigForNuxt({
  // options here
  // lbhm: Not sure if this is needed
  // extends: [
  //   eslint.configs.recommended,
  //   ...typescriptEslint.configs.recommended,
  //   ...eslintPluginVue.configs["flat/recommended"],
  // ],
  // files: ["**/*.{ts,vue}"],
  // languageOptions: {
  //   ecmaVersion: "latest",
  //   sourceType: "module",
  //   globals: globals.browser,
  //   parserOptions: {
  //     parser: typescriptEslint.parser,
  //   },
  // },
}).override("nuxt/vue/rules", {
  rules: {
    // Rule overrides
    "vue/no-v-html": "off",
    "vue/no-v-text-v-html-on-component": "off",
    "vue/html-self-closing": [
      "error",
      {
        html: {
          void: "always",
        },
      },
    ],
  },
});
