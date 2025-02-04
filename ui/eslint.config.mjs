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
  // rules: {
  //   // override/add rules settings here, such as:
  //   // 'vue/no-unused-vars': 'error',
  // },
});
