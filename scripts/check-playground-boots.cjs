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
//   4. A synthetic broken fixture uploads, Validate runs the real wheel in
//      the browser, and the report frame renders the finding the fixture is
//      built to trigger. A wheel that installs but whose API the page calls
//      no longer matches fails here rather than in a user's browser.
//   5. The valid fixture uploads into the same page and reports nothing. A
//      page that answers every feed with findings satisfies step 4 exactly as
//      well as a working one does, so step 4 alone cannot tell "it validates"
//      from "it complains". #146 asks for both halves for that reason. Running
//      it second, in the session step 4 just dirtied, also exercises the
//      cleanup path in web/index.html that unlinks the previous run's files
//      from /feed: a leak there shows up here as findings from the run before.
//
// Usage:
//   node scripts/check-playground-boots.cjs
//
// Environment:
//   PLAYGROUND_URL              page to drive (default: the project's Pages URL)
//   PLAYGROUND_EXPECTED_PIN     require the page to declare this wheel version
//   PLAYGROUND_FIXTURE          broken feed file (default: the TODS-E201 fixture)
//   PLAYGROUND_EXPECTED_RULE    rule id the report must contain (default: TODS-E201)
//   PLAYGROUND_VALID_FIXTURE    directory of a feed that must validate clean
//                               (default: tests/fixtures/valid/tods)
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
const validFixtureDir =
  process.env.PLAYGROUND_VALID_FIXTURE ||
  path.join(REPO_ROOT, "tests", "fixtures", "valid", "tods");
const bootTimeoutMs = Number(process.env.PLAYGROUND_BOOT_TIMEOUT_MS || 300000);
const runTimeoutMs = Number(process.env.PLAYGROUND_RUN_TIMEOUT_MS || 180000);

// The page writes uploads into a flat /feed directory keyed by File.name, which
// is the shape a TODS package already has, so the valid fixture's files go up
// as a flat list. Sorted, so a failure message names them in a stable order.
function feedFilesIn(dir) {
  return fs
    .readdirSync(dir)
    .filter((name) => name.endsWith(".txt"))
    .sort()
    .map((name) => path.join(dir, name));
}

// Any rule id the report may have rendered. The clean run asserts on this
// rather than on the "No problems found." wording alone: the wording is a
// string in report.py that could change, while a rendered rule id means the
// page found something in a feed that has nothing to find.
const RULE_ID = /TODS-[EWI]\d{3}/g;

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

// Upload `files`, click Validate, and return the text the report frame
// actually rendered. Shared by both runs so the clean feed is put through the
// identical path the broken one is, rather than a second, subtly different one.
async function validateThrough(page, files) {
  const shown = files.map((f) => path.relative(REPO_ROOT, f));
  console.log(`uploading ${shown.length === 1 ? shown[0] : `${shown.length} files`} and running Validate`);

  // Clear the input first. Selecting a file list identical to the one already
  // there is not a change, so the page's `change` handler never runs and the
  // status line keeps whatever the previous run left on it. That is only
  // reachable when two runs upload the same files, which the default pair does
  // not do, so without this the script passes for the wrong reason on the pair
  // it ships with and hangs for anyone who points both runs at one fixture.
  const input = await page.$("#files");
  await input.evaluate((el) => {
    el.value = "";
  });
  await input.uploadFile(...files);
  // The change handler reads each file asynchronously; clicking before it
  // finishes just gets "Select your feed files first." Match the count too:
  // "includes" would accept a stale line from the run before.
  await waitForStatus(page, {
    what: "reading the selected file(s)",
    done: (text) => text === `${files.length} file(s) selected.`,
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
  return frame.evaluate(() => document.body.innerText);
}

async function main() {
  if (!fs.existsSync(fixture)) {
    fail(`fixture not found: ${fixture}`);
    return;
  }
  if (!fs.existsSync(validFixtureDir)) {
    fail(`valid fixture directory not found: ${validFixtureDir}`);
    return;
  }
  const validFiles = feedFilesIn(validFixtureDir);
  if (validFiles.length === 0) {
    fail(`no .txt feed files in ${validFixtureDir}`);
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

    // 4. The broken fixture must produce the finding it is built to produce.
    const brokenReport = await validateThrough(page, [fixture]);
    if (!brokenReport.includes(expectedRule)) {
      throw new Error(
        `the report rendered, but does not mention ${expectedRule}, which ` +
          `${path.relative(REPO_ROOT, fixture)} is built to trigger. Rendered report began: ` +
          JSON.stringify(brokenReport.slice(0, 400))
      );
    }
    console.log(`  reported ${expectedRule}, as the fixture is built to`);

    // 5. The valid fixture must produce nothing, in the same session. Step 4
    // proves the page can find a problem; only this proves it does not invent
    // one, and that the previous run left nothing behind in /feed.
    const cleanReport = await validateThrough(page, validFiles);
    const rendered = [...new Set(cleanReport.match(RULE_ID) || [])].sort();
    if (rendered.length > 0) {
      throw new Error(
        `the deployed page reported ${rendered.join(", ")} for ` +
          `${path.relative(REPO_ROOT, validFixtureDir)}, which validates clean. ` +
          `Rendered report began: ${JSON.stringify(cleanReport.slice(0, 400))}`
      );
    }
    console.log(`  reported nothing for the ${validFiles.length}-file valid feed`);

    console.log(
      `the deployed playground booted on tods-validate ${livePin}, reported ` +
        `${expectedRule} for the broken fixture, and reported nothing for the valid one`
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
