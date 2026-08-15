"use strict";

// pa11y-ci configuration for the *deployed* playground, as opposed to
// scripts/pa11y-ci.cjs, which audits the repository's copy of web/index.html
// from a temp directory. Both matter and they are not the same artifact: the
// blocking CI gate proves the source is accessible, this one proves the page
// people actually open is. Run by .github/workflows/playground-deployment.yml.
//
// The a11y-static parameter is passed for the same reason the local config
// passes it -- it skips the Pyodide download and renders the page's static
// state. A deployed page that predates that branch simply ignores an unknown
// query parameter and is audited as it loads.

const liveUrl =
  process.env.A11Y_LIVE_URL || "https://chelseakr.github.io/tods-validate/index.html";

module.exports = {
  defaults: {
    runners: ["axe", "htmlcs"],
    standard: "WCAG2AA",
    timeout: 120000,
    viewport: {
      width: 1280,
      height: 1024
    }
  },
  urls: [
    {
      url: `${liveUrl}?a11y-static=1`,
      // Same reasoning as the local config: the report frame keeps its
      // production sandbox, and its rendered contents are audited directly
      // by the local gate's report.html run.
      hideElements: "#report"
    }
  ]
};
