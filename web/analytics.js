/*
 * Google Analytics 4 on the public tods-validate pages (ADR 0010).
 *
 * GA4_ID below is the one place the measurement ID goes. It is public: every
 * page that loads GA sends it to the browser. Set it to "" and this file loads
 * nothing from Google on any page.
 *
 * When an ID is set, the script returns before creating `dataLayer` or asking
 * Google for anything unless every one of these holds:
 *
 * - the page is served over HTTPS from chelseakr.github.io under
 *   /tods-validate/, so local previews, the pa11y and boot-check servers on
 *   127.0.0.1 and CI never send a hit to the real property;
 * - the browser does not send Global Privacy Control
 *   (`navigator.globalPrivacyControl === true`);
 * - Do Not Track is off (`navigator.doNotTrack`, `window.doNotTrack` or
 *   `navigator.msDoNotTrack` is not "1" or "yes"); and
 * - the visitor has not used the footer's "Opt out of analytics" control, which
 *   is remembered in localStorage under OPT_OUT_KEY.
 *
 * Then it sets Consent Mode v2 defaults (the three advertising signals denied
 * everywhere; analytics storage denied in the EEA, the UK and Switzerland, so
 * Google receives cookieless pings there, and granted elsewhere) and configures
 * GA with Google signals and ad personalization off. `page_location` is the
 * page's origin and path only: no query string and no fragment ever reaches
 * Google. `page_referrer` is the linking site's origin only.
 *
 * The feed files chosen in the playground, the validation report and anything
 * else on a page are never read by this file and are never sent to Google.
 */
(function () {
  "use strict";

  // The one place the measurement ID goes. "" = no Google Analytics anywhere.
  // G-TM683Q87RD is the web stream of GA4 property 554837399 (provisioned
  // 2026-09-17 with 14-month retention and Google signals disabled).
  var GA4_ID = "G-TM683Q87RD";
  var PRODUCTION_HOST = "chelseakr.github.io";
  var PRODUCTION_PATH = "/tods-validate/";
  // Renaming this key would silently opt every opted-out visitor back in.
  var OPT_OUT_KEY = "tods-validate:analytics-opt-out";
  var LOADER = "https://www.googletagmanager.com/gtag/js?id=";
  // analytics_storage stays denied for these ISO 3166-1 regions: the 27 EU
  // member states, Iceland, Liechtenstein and Norway (the EEA), the United
  // Kingdom and Switzerland.
  var CONSENT_REQUIRED = [
    "AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "ES", "FI", "FR", "GR", "HR", "HU",
    "IE", "IT", "LT", "LU", "LV", "MT", "NL", "PL", "PT", "RO", "SE", "SI", "SK",
    "IS", "LI", "NO",
    "GB",
    "CH",
  ];
  var MESSAGES = {
    optedOut: "Opted out. From the next page you open, this site will not load "
      + "Google Analytics in this browser.",
    isOut: "You have opted out. This site does not load Google Analytics in this browser.",
    backIn: "Opted back in. Analytics resumes from the next page you open.",
    signal: "Analytics is off because your browser sends Global Privacy Control "
      + "or Do Not Track.",
    noStorage: "This browser is blocking site storage, so an opt-out cannot be "
      + "remembered here. Global Privacy Control or Do Not Track keeps analytics off.",
  };

  var w = window;
  var n = w.navigator || {};
  var d = document;
  var hasId = /^G-[A-Z0-9]{4,20}$/.test(GA4_ID);

  var store = null;
  try {
    store = w.localStorage;
    store.getItem(OPT_OUT_KEY);
  } catch (e) {
    store = null;
  }
  function optedOut() {
    try {
      return !!store && store.getItem(OPT_OUT_KEY) === "1";
    } catch (e) {
      return false;
    }
  }
  var dnt = n.doNotTrack || w.doNotTrack || n.msDoNotTrack;
  var signal = n.globalPrivacyControl === true || dnt === "1" || dnt === "yes";

  // The footer control. It is wired on every host, so the local pa11y runs
  // check the real, visible button, but it only ever changes the flag.
  function wireChoice() {
    var box = d.querySelector("[data-analytics-choice]");
    if (!box) return;
    var button = box.querySelector("button");
    var status = box.querySelector("[role=status]");
    if (!button || !status) return;
    var gaDisable = "ga-disable-" + GA4_ID;
    function render(message) {
      button.textContent = optedOut() ? "Opt back in" : "Opt out of analytics";
      button.hidden = signal || !store;
      status.textContent = message;
      box.hidden = false;
    }
    button.addEventListener("click", function () {
      try {
        if (optedOut()) {
          store.removeItem(OPT_OUT_KEY);
          w[gaDisable] = false;
          render(MESSAGES.backIn);
        } else {
          store.setItem(OPT_OUT_KEY, "1");
          w[gaDisable] = true;
          render(MESSAGES.optedOut);
        }
      } catch (e) {
        store = null;
        render(MESSAGES.noStorage);
      }
    });
    render(signal ? MESSAGES.signal
      : !store ? MESSAGES.noStorage
        : optedOut() ? MESSAGES.isOut : "");
  }
  if (hasId) {
    if (d.readyState === "loading") {
      d.addEventListener("DOMContentLoaded", wireChoice);
    } else {
      wireChoice();
    }
  }

  if (!hasId) return;
  var loc = w.location;
  if (loc.protocol !== "https:" || loc.hostname !== PRODUCTION_HOST) return;
  if (loc.pathname.indexOf(PRODUCTION_PATH) !== 0) return;
  if (signal) return;
  if (optedOut()) return;

  function referrerOrigin() {
    var ref = d.referrer;
    if (!ref) return "";
    try {
      return new URL(ref).origin + "/";
    } catch (e) {
      return "";
    }
  }

  w.dataLayer = w.dataLayer || [];
  // gtag reads the arguments object itself, not an array made from it.
  function gtag() {
    w.dataLayer.push(arguments);
  }
  gtag("consent", "default", {
    ad_storage: "denied",
    ad_user_data: "denied",
    ad_personalization: "denied",
    analytics_storage: "denied",
    region: CONSENT_REQUIRED,
  });
  gtag("consent", "default", {
    ad_storage: "denied",
    ad_user_data: "denied",
    ad_personalization: "denied",
    analytics_storage: "granted",
  });
  gtag("js", new Date());
  gtag("config", GA4_ID, {
    allow_google_signals: false,
    allow_ad_personalization_signals: false,
    page_location: loc.origin + loc.pathname,
    page_referrer: referrerOrigin(),
  });

  var script = d.createElement("script");
  script.async = true;
  script.src = LOADER + encodeURIComponent(GA4_ID);
  (d.head || d.documentElement).appendChild(script);
})();
