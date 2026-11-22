import js from "@eslint/js";
import tseslint from "typescript-eslint";
import hooks from "eslint-plugin-react-hooks";

const PHANTOM_TOKEN_REGEX =
  "--(border-subtle|surface-card|text-muted|surface-elevated|surface-muted|surface-primary|accent-primary)";

export default tseslint.config(
  { ignores: ["dist/**", "test-results/**", "playwright-report/**"] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ["src/**/*.{ts,tsx}"],
    plugins: { "react-hooks": hooks },
    rules: {
      "react-hooks/rules-of-hooks": "error",
      "react-hooks/exhaustive-deps": "error",
      "@typescript-eslint/consistent-type-imports": "error",
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              group: ["../../*"],
              message: "Usa el alias @/ para importar entre capas.",
            },
          ],
        },
      ],
      "no-restricted-syntax": [
        "error",
        {
          selector: `Literal[value=/${PHANTOM_TOKEN_REGEX}/]`,
          message:
            "Usa exclusivamente variables definidas en src/shared/styles/tokens.css.",
        },
      ],
    },
  },
  {
    files: ["src/shared/**/*.{ts,tsx}"],
    rules: {
      "@typescript-eslint/no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              group: [
                "../../*",
                "@/entities/*",
                "@/features/*",
                "@/widgets/*",
                "@/pages/*",
                "@/app/*",
              ],
              allowTypeImports: true,
              message:
                "La capa shared/ no debe importar código de ejecución desde capas superiores.",
            },
          ],
        },
      ],
    },
  },
  {
    files: ["src/entities/**/*.{ts,tsx}"],
    rules: {
      "@typescript-eslint/no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              group: [
                "../../*",
                "@/features/*",
                "@/widgets/*",
                "@/pages/*",
                "@/app/*",
              ],
              allowTypeImports: false,
              message:
                "La capa entities/ no debe importar desde features/, widgets/, pages/ o app/.",
            },
          ],
        },
      ],
    },
  },
);
