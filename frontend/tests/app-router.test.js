import assert from "node:assert/strict";
import test from "node:test";

import { appRoutes } from "../src/app/router/routes.ts";
import {
  getRouteDocumentTitle,
  normalizeRoute,
  routeTitles,
  splitRouteAndSearch,
} from "../src/app/router/useAppRouter.ts";

test("all 15 declared appRoutes have a defined non-empty title without undefined", () => {
  const allRoutes = Object.values(appRoutes);
  assert.equal(allRoutes.length, 15);
  for (const route of allRoutes) {
    assert.ok(routeTitles[route], `Missing route title for ${route}`);
    const fullTitle = getRouteDocumentTitle(route);
    assert.doesNotMatch(fullTitle, /undefined/i);
    assert.match(fullTitle, /KronDocs$/);
  }
});

test("normalizeRoute and splitRouteAndSearch preserve query parameters on known routes", () => {
  assert.equal(normalizeRoute("/studio?artifact=art_001"), appRoutes.studio);
  assert.equal(
    normalizeRoute("/documents?q=contrato"),
    appRoutes.documents,
  );
  assert.equal(normalizeRoute("/unknown-route?foo=1"), appRoutes.chat);

  const parsed = splitRouteAndSearch("/studio?artifact=art_001");
  assert.equal(parsed.route, appRoutes.studio);
  assert.equal(parsed.search, "?artifact=art_001");
});
