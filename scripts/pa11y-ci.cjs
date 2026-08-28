"use strict";

const baseUrl = process.env.A11Y_BASE_URL || "http://127.0.0.1:8765";

module.exports = {
  defaults: {
    runners: ["axe", "htmlcs"],
    standard: "WCAG2AA",
    timeout: 60000,
    viewport: {
      width: 1280,
      height: 1024
    }
  },
  urls: [
    {
      url: `${baseUrl}/index.html?a11y-static=1`,
      // The report frame keeps its production sandbox. Its rendered contents
      // are audited directly at report.html below, so axe does not need to
      // bypass that security boundary from the parent page.
      hideElements: "#report"
    },
    `${baseUrl}/report.html`,
    // The rule catalog, published by pages.yml alongside index.html. All 44
    // rule pages come from one template in scripts/generate_rules_doc.py, and
    // `--check` (a CI gate) fails if any committed page differs from what that
    // template produces, so auditing the index plus one page audits the shape
    // of all of them. tests/test_generate_rules_doc.py pins that reasoning.
    `${baseUrl}/rules/index.html`,
    `${baseUrl}/rules/TODS-E307.html`
  ]
};
