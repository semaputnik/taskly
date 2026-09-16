import { defineConfig } from "@hey-api/openapi-ts"

export default defineConfig({
  input: "./openapi.json",
  output: "./src/client",

  plugins: [
    { name: "@hey-api/client-axios", throwOnError: true },
    { name: "@hey-api/typescript", case: "preserve" },
    // The API's own constraints, so a form reads a limit rather than
    // restating it.
    { name: "@hey-api/schemas", type: "json" },
    {
      name: "@hey-api/sdk",
      operations: {
        // NOTE: this doesn't allow tree-shaking
        strategy: "byTags",
        methods: "static",
        containerName: "{{name}}Service",
        methodName: (name: string): string => name.replace(/^[^-]*-/, ""),
      },
    },
  ],
})
