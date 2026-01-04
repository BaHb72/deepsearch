import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";
import js from "@eslint/js";

const require = createRequire(import.meta.url);
const { FlatCompat } = require("@eslint/eslintrc");

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const compat = new FlatCompat({
  baseDirectory: __dirname,
  resolvePluginsRelativeTo: __dirname,
  recommendedConfig: js.configs.recommended,
  allConfig: js.configs.all,
});

const eslintrcPath = path.join(__dirname, ".eslintrc.json");
const eslintrcConfig = JSON.parse(fs.readFileSync(eslintrcPath, "utf8"));

export default [
  ...compat.config(eslintrcConfig),
];
