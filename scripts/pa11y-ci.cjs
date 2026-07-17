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
    `${baseUrl}/report.html`
  ]
};
