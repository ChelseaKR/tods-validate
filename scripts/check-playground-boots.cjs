"use strict";

// Drive the deployed playground in a real browser and fail if it does not
// actually validate a feed.
//
// Why this exists. Until this script, every playground gate checked the page
// without ever running it:
//
//   * scripts/check-deployed-playground.sh compares the served bytes with
//     web/index.html. Byte-identical to the source and completely broken for
//     every visitor are not mutually exclusive.
//   * scripts/pa11y-ci-live.cjs loads the live URL with ?a11y-static=1, and
//     that parameter is exactly the branch in web/index.html that *skips*
//     boot(). Pyodide never loads, micropip never installs, no validation is
//     ever attempted.
//   * pages.yml checks PyPI serves the pinned wheel, but it checks the pin in
//     its own checkout at deploy time, not the pin in the page being served.
//
// So the whole deployment check was satisfiable by a page that shows "Failed
// to load Python" to everyone who opens it, and this project has shipped
// exactly that: #136 repinned the page to "0.9.0, the version PyPI actually
// has", meaning the live playground had been pinned to a wheel PyPI never
// served and micropip.install rejected it for every visitor, with every gate
// green throughout. Issue #146 asks for this end-to-end confirmation because
// it has never once been done.
//
// What this proves, in order, each step able to fail on its own:
//
//   1. The page loads and its boot() path runs (no ?a11y-static=1 here).
//   2. Pyodide loads from the CDN and micropip installs
//      tods-validate==<the pin in the served page> from PyPI. Reaching the
//      "Ready" status is only reachable after that install resolves, so this
//      is the check #136's bug would have failed.
//   3. The declared pin matches PLAYGROUND_EXPECTED_PIN when the caller sets
//      it, so a live page installing a different release than the one the
//      repository publishes is caught even though it "works".
//   4. A synthetic fixture uploads, Validate runs the real wheel in the
//      browser, and the report frame renders the finding the fixture is
//      built to trigger. A wheel that installs but whose API the page calls
//      no longer matches fails here rather than in a user's browser.
//
// Usage:
//   node scripts/check-playground-boots.cjs
//
// Environment:
//   PLAYGROUND_URL              page to drive (default: the project's Pages URL)
//   PLAYGROUND_EXPECTED_PIN     require the page to declare this wheel version
//   PLAYGROUND_FIXTURE          feed file to upload (default: the TODS-E201 fixture)
//   PLAYGROUND_EXPECTED_RULE    rule id the report must contain (default: TODS-E201)
//   PLAYGROUND_BOOT_TIMEOUT_MS  wait for Pyodide + micropip (default 300000)
//   PLAYGROUND_RUN_TIMEOUT_MS   wait for a validation run (default 180000)
//   PUPPETEER_EXECUTABLE_PATH   Chrome binary (CI passes the hosted one)

const path = require("node:path");
const fs = require("node:fs");

// puppeteer arrives through pa11y-ci -> pa11y, and package-lock.json pins it
// at the top of node_modules, so `npm ci` resolves this deterministically. It
// is deliberately not a direct devDependency: WVR-001 waives a transitive
// extract-zip advisory on the grounds that puppeteer reaches this repository
// only under the accessibility toolchain, and promoting it would make that
// waiver's stated reasoning untrue. Declaring it is the right move if pa11y
// ever drops puppeteer -- but then the waiver text has to be rewritten in the
// same change, so fail here saying so rather than letting a bare
// MODULE_NOT_FOUND look like an infrastructure blip.
let puppeteer;
try {
  puppeteer = require("puppeteer");
} catch (err) {
  console.error(
    "::error::puppeteer is not installed. It comes in transitively under " +
      "pa11y-ci; run `npm ci`. If pa11y-ci no longer depends on it, add " +
      "puppeteer to package.json's devDependencies and update WVR-001 in " +
      "waivers.yml, which describes it as reachable only through pa11y-ci."
  );
  process.exit(1);
}

const REPO_ROOT = path.join(__dirname, "..");

const url = process.env.PLAYGROUND_URL || "https://chelseakr.github.io/tods-validate/index.html";
const expectedPin = process.env.PLAYGROUND_EXPECTED_PIN || "";
const expectedRule = process.env.PLAYGROUND_EXPECTED_RULE || "TODS-E201";
const fixture =
  process.env.PLAYGROUND_FIXTURE ||
  path.join(REPO_ROOT, "tests", "fixtures", "invalid", "TODS-E201", "run_events.txt");
const bootTimeoutMs = Number(process.env.PLAYGROUND_BOOT_TIMEOUT_MS || 300000);
const runTimeoutMs = Number(process.env.PLAYGROUND_RUN_TIMEOUT_MS || 180000);

function fail(message) {
  // ::error:: so the failure lands as a GitHub Actions annotation, the same
  // way check-deployed-playground.sh reports.
  console.error(`::error::${message}`);
  process.exitCode = 1;
}

const status = (page) =>
  page.evaluate(() => document.getElementById("status").textContent.trim());

// Poll #status until `done` accepts it. `abortOn` is checked first and throws
// immediately: the page reports both of its own failure modes into this same
// element ("Failed to load Python: ...", "Validation error: ..."), and waiting
// out a five-minute timeout to report a message the page already printed helps
// nobody.
async function waitForStatus(page, { what, done, abortOn, timeoutMs }) {
  const deadline = Date.now() + timeoutMs;
  let last = "";
  for (;;) {
    last = await status(page);
    for (const bad of abortOn) {
      if (last.startsWith(bad)) {
        throw new Error(`the playground reported a failure while ${what}: ${last}`);
      }
    }
    if (done(last)) {
      return last;
    }
    if (Date.now() > deadline) {
      throw new Error(
        `timed out after ${Math.round(timeoutMs / 1000)}s while ${what}; ` +
          `the page's last status was ${JSON.stringify(last)}`
      );
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
}

async function main() {
  if (!fs.existsSync(fixture)) {
    fail(`fixture not found: ${fixture}`);
    return;
  }

  const browser = await puppeteer.launch({
    executablePath: process.env.PUPPETEER_EXECUTABLE_PATH || undefined,
    // The hosted runners' Chrome cannot use its sandbox inside the Actions
    // container; pa11y runs the same way here.
    args: ["--no-sandbox", "--disable-dev-shm-usage"],
  });

  try {
    const page = await browser.newPage();

    // Surface the page's own diagnostics. A CSP violation or a failed CDN
    // fetch shows up here and is the first thing worth reading when the
    // status line just says the load failed.
    const pageErrors = [];
    page.on("pageerror", (err) => pageErrors.push(String(err)));
    page.on("requestfailed", (req) =>
      pageErrors.push(`request failed: ${req.url()} (${req.failure()?.errorText})`)
    );

    console.log(`driving ${url}`);
    const response = await page.goto(url, { waitUntil: "domcontentloaded", timeout: 60000 });
    if (!response || !response.ok()) {
      throw new Error(`${url} returned HTTP ${response ? response.status() : "no response"}`);
    }

    // 1 + 2. boot() must reach Ready, which happens only after Pyodide loads
    // and micropip.install(`tods-validate==<pin>`) resolves against PyPI.
    console.log("waiting for Pyodide and micropip to install the pinned wheel");
    const readyStatus = await waitForStatus(page, {
      what: "loading Python and installing the pinned wheel",
      done: (text) => text.startsWith("Ready"),
      abortOn: ["Failed to load Python:"],
      timeoutMs: bootTimeoutMs,
    });
    console.log(`ready: ${readyStatus}`);

    const runDisabled = await page.evaluate(() => document.getElementById("run").disabled);
    if (runDisabled) {
      throw new Error("the page reported Ready but left the Validate button disabled");
    }

    // 3. The version the served page declares, read from the DOM it renders.
    const footer = await page.evaluate(
      () => document.getElementById("footer-version").textContent
    );
    const pinMatch = /tods-validate\s+([^\s]+)/.exec(footer);
    if (!pinMatch) {
      throw new Error(`could not read the wheel version from the footer: ${JSON.stringify(footer)}`);
    }
    const livePin = pinMatch[1];
    console.log(`the deployed page installed tods-validate ${livePin}`);
    if (expectedPin && livePin !== expectedPin) {
      throw new Error(
        `the deployed page boots on tods-validate ${livePin}, but this repository publishes ${expectedPin}`
      );
    }

    // 4. Upload the fixture, run it, and read the rendered report.
    console.log(`uploading ${path.relative(REPO_ROOT, fixture)} and running Validate`);
    const input = await page.$("#files");
    await input.uploadFile(fixture);
    // The change handler reads each file asynchronously; clicking before it
    // finishes just gets "Select your feed files first."
    await waitForStatus(page, {
      what: "reading the selected file",
      done: (text) => text.includes("file(s) selected"),
      abortOn: [],
      timeoutMs: 60000,
    });

    await page.click("#run");
    await waitForStatus(page, {
      what: "validating the fixture",
      done: (text) => text === "Done.",
      abortOn: ["Validation error:"],
      timeoutMs: runTimeoutMs,
    });

    // The report iframe is srcdoc with sandbox="allow-same-origin", so it
    // keeps the parent origin and its rendered DOM is readable here. Assert on
    // what the frame actually rendered rather than the srcdoc attribute: that
    // is the report a person sees.
    const frameHandle = await page.$("#report");
    const frame = await frameHandle.contentFrame();
    if (!frame) {
      throw new Error("the report frame is not accessible");
    }
    const reportText = await frame.evaluate(() => document.body.innerText);
    if (!reportText.includes(expectedRule)) {
      throw new Error(
        `the report rendered, but does not mention ${expectedRule}, which ` +
          `${path.relative(REPO_ROOT, fixture)} is built to trigger. Rendered report began: ` +
          JSON.stringify(reportText.slice(0, 400))
      );
    }

    console.log(
      `the deployed playground booted on tods-validate ${livePin} and reported ${expectedRule} for the fixture`
    );
    if (pageErrors.length > 0) {
      // Not fatal: the run demonstrably worked. Still worth printing, because
      // a failed request that did not break this fixture may break another.
      console.log("page diagnostics during the run:");
      for (const line of pageErrors) {
        console.log(`  ${line}`);
      }
    }
  } catch (err) {
    fail(err.message);
  } finally {
    await browser.close();
  }
}

main().catch((err) => {
  fail(err && err.stack ? err.stack : String(err));
});
