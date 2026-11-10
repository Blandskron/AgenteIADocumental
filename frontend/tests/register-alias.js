import { registerHooks } from "node:module";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
registerHooks({
  resolve(specifier, context, nextResolve) {
    let target = specifier.startsWith("@/")
      ? new URL(`../src/${specifier.slice(2)}`, import.meta.url).href
      : specifier;
    if (
      (target.startsWith("file:") || target.startsWith(".")) &&
      !/\.[a-z]+$/i.test(target)
    ) {
      const url = new URL(target, context.parentURL);
      for (const extension of [".ts", ".tsx"])
        if (existsSync(fileURLToPath(url) + extension)) {
          target = url.href + extension;
          break;
        }
    }
    if (target !== specifier) return nextResolve(target, context);
    return nextResolve(specifier, context);
  },
});
