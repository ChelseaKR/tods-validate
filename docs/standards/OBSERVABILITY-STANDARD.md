# Observability Standard

This is the canonical definition of how every repo in this portfolio emits, structures, and acts on telemetry. **OpenTelemetry (OTel) is the only instrumentation API** — chosen because it is the 2026 vendor-neutral default with stable Python/JS trace and metric SDKs, so a repo can switch backends (Grafana, Sentry, self-hosted) without re-instrumenting. *Rejected:* per-vendor SDKs (Datadog, raw Sentry tracing) — they lock the instrumentation to a billing relationship; bespoke JSON-lines logging — no correlation IDs, no propagation, no semconv.

The standard is **tiered by deployment shape**, because instrumenting a local-only CLI like a hosted Lambda is waste, and skipping a hosted civic RAG service is negligence. Each repo declares its tier in `docs/ROADMAP.md`. There is no fourth, "aspirational" enforcement category: a control is **AUTO-GATE** (mechanically checkable, merge-blocking in CI) or **REVIEW-GATE** (human judgment, paired with a checklist item and a committed artifact).

> **Reference, don't repeat.** The rigor lives here once. A repo records only its *values*: its `OTEL_SERVICE_NAME`, its SLO targets, its span-coverage artifact, its declared tier. It does not restate the gates.

---

## 0. Tiers — which rules apply

Declare the tier in `docs/ROADMAP.md` under a `## Observability` heading. A repo that skips a tier control must record **N/A-with-reason** in that section; silent omission is a defect caught by the tier-declaration gate (§7).

| Tier | Example shapes | What is in scope |
|------|------------------------|------------------|
| **A — Hosted service / Lambda** | HTTP APIs, background pipeline services, and serverless handlers | Full stack: OTel traces+metrics, structured JSON logs with trace correlation, RED/USE, `/livez`+`/readyz`, SLOs, burn-rate alerts, dashboards-as-code, PII-safe-logging gate |
| **B — Frontend / PWA** | SPAs, public maps, and multilingual web applications | Core Web Vitals RUM (LCP/INP/CLS), browser OTel spans on API calls, `traceparent` propagation to the backend, Lighthouse-CI CWV gate |
| **C — Library / CLI** | local libraries, operator CLIs, and offline privacy-sensitive tools | Opt-in `--log-format json` (structlog); OTel **optional and documented out-of-scope**; no SLO/health requirement |

A repository with both a service and a CLI applies Tier A to the service surface and Tier C to the CLI surface. State both.

**Migration triggers (record project values privately):**

- A service using vendor-specific tracing adds OTLP export and a non-zero,
  documented sampling policy.
- A frontend adds the `web-vitals` to RUM beacon path described in §8.
- A service emitting bespoke JSON-lines or `console.error` migrates to the §3
  structured-log contract.

---

## 1. Traces (Tier A; Tier B for browser spans)

**Tool:** `opentelemetry-distro` zero-code auto-instrumentation (Python) / `@opentelemetry/sdk-web` (TS). *Rejected:* manual span wiring as the baseline — auto-instrumentation covers Flask/FastAPI/httpx/requests/SQLAlchemy/Redis for free; reserve manual spans for business operations the auto-instrumentor can't see (a retrieval step, a judge call).

Run Python services under `opentelemetry-instrument python app.py`. Export via OTLP — gRPC `:4317` or HTTP `:4318` — to an OTel Collector, never directly to a backend. Use `BatchSpanProcessor` in production.

**Required env (in the container manifest, not code):**

```dotenv
OTEL_SERVICE_NAME=example-service             # non-empty, == service.name resource attr
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318
OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
OTEL_PROPAGATORS=tracecontext,baggage     # W3C Trace Context Level 1
OTEL_PYTHON_LOG_CORRELATION=true          # injects trace_id/span_id into logs
```

**Span attribute contract** (OTel Semantic Conventions **v1.42.0** — pin this version; do not invent attribute names outside the semconv namespace):

| Span kind | Required attributes |
|-----------|---------------------|
| HTTP **server** | `http.request.method`, `url.path`, `url.scheme`, `http.route`, `http.response.status_code`, `error.type` (on error) |
| HTTP **client** | `http.request.method`, `server.address`, `server.port`, `url.full`, `http.response.status_code`, `error.type` (on error) |
| **All spans** (resource) | `service.name`, `service.version`, `deployment.environment` |

W3C `traceparent` (`00-<32hex>-<16hex>-<2hex>`) and `tracestate` propagate on every inbound/outbound HTTP call. All-zero trace-id or parent-id is forbidden; generate a fresh trace-id when no incoming header exists. For Tier-B frontends, the `fetch`/`axios` layer **must** inject `traceparent` on API requests so browser traces chain to backend traces.

| Metric | Target | Measured by | Gate |
|--------|--------|-------------|------|
| `OTEL_SERVICE_NAME` set & non-empty [OBS-01] | required | CI asserts env present in container manifest pre-deploy | AUTO-GATE |
| HTTP route span coverage [OBS-02] | every registered route produces ≥1 span with `http.request.method` + `http.response.status_code` | integration test enumerates routes, asserts spans | AUTO-GATE |
| `traceparent` on cross-service calls [OBS-03] | present, valid, non-zero | integration test asserts header on all service-to-service requests | AUTO-GATE |
| Span attribute names [OBS-04] | semconv v1.42.0, no deprecated (`net.peer.ip`→`network.peer.address`) or invented names | semconv linter (OPA/custom) on every PR | AUTO-GATE |
| Span coverage report [OBS-05] | 100% of HTTP routes instrumented | `observability/span-coverage.md`, owner sign-off per release | REVIEW-GATE |

---

## 2. Metrics — RED & USE (Tier A)

**Tool:** OTel metrics SDK + `PeriodicExportingMetricReader` (60 s) → Collector → Prometheus/Mimir. Names follow Prometheus convention: lowercase `snake_case`, base UCUM units (`seconds` not `ms`, `bytes` not `mb`), `_total` on counters.

**RED per public endpoint** — define exactly these:

```text
<service>_http_requests_total            counter   labels: method, route, status_code
<service>_http_request_duration_seconds  histogram labels: method, route
                                         buckets: .005 .01 .025 .05 .1 .25 .5 1 2.5 5 10
<service>_http_request_errors_total      counter   labels: method, route, error_type
```

**USE per resource:** `process_cpu_seconds_total`, `process_resident_memory_bytes`, plus a custom saturation gauge per bounded resource (queue depth, connection-pool in-use). For the RAG/eval repos, add domain saturation where it bounds capacity (e.g. embedding-queue depth, LLM-token-budget remaining) — these are the saturation SLIs that actually predict failure.

**Cardinality rule (hard):** labels never carry user IDs, emails, request IDs, or any unbounded value. This is both a cost control and a privacy control — a user-ID label is PII in the metrics store.

| Metric | Target | Measured by | Gate |
|--------|--------|-------------|------|
| Metric naming [OBS-06] | base units only; `_total` on every monotonic counter; no `_ms`/`_mb`/`_gb` suffix | `promtool lint` + custom linter in CI | AUTO-GATE |
| Label cardinality [OBS-07] | no `user_id`/`email`/`request_id`/unbounded labels | custom linter scans metric definitions | AUTO-GATE |
| RED present per endpoint [OBS-08] | requests_total + duration_seconds + errors_total exist for every public route | metrics-registry test | AUTO-GATE |

---

## 3. Logs — structured JSON with trace correlation & PII redaction (Tier A AUTO-GATE; Tier C opt-in)

The OTel **Logs** Python SDK is still in Development in 2026, so do **not** use the native OTel Logs SDK directly. Use the **Log Bridge pattern**: `structlog` with a JSON renderer → stdout; the OTel Collector `filelog` receiver reads stdout JSON and converts to OTLP LogRecord. *Rejected:* `python-json-logger` as the default — structlog's processor pipeline is richer and is what injects trace context cleanly. *Rejected:* native OTel Logs SDK — not stable; pinning to it now buys churn.

**structlog trace-context processor (the load-bearing snippet):**

```python
import logging, structlog
from opentelemetry import trace

def add_trace_context(_, __, event: dict) -> dict:
    span = trace.get_current_span()
    ctx = span.get_span_context() if span else None
    if ctx and ctx.is_valid:
        event["trace_id"] = format(ctx.trace_id, "032x")  # 32-char hex
        event["span_id"] = format(ctx.span_id, "016x")    # 16-char hex
        event["trace_flags"] = ctx.trace_flags
    return event

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,        # -> severity
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        add_trace_context,
        structlog.processors.EventRenamer("message"),
        structlog.processors.JSONRenderer(),
    ],
)
```

**Every Tier-A log record MUST contain:** `timestamp` (ISO 8601 UTC), `severity` (SeverityText), `service.name`, `trace_id`, `span_id`, `message`, and a structured attributes map. Never use `%s` format strings for structured fields — always pass `extra={}` / structlog kwargs.

**PII / secrets — the explicit hard gate (OWASP Top 10:2025 A09).** NEVER log: passwords, session/access tokens, API keys, encryption keys, DB connection strings, PII/PHI, payment-card data, government IDs, rider identities, trip endpoints, or any field that could deanonymize a person. De-identify (delete/pseudonymize) before logging; encode log data to prevent log injection. This standard owns the redaction *mechanism* below; `DATA-GOVERNANCE-STANDARD.md` §4 owns the **classification** — the canonical sensitive-field inventory this gate is checked against, extended as a repository adds new L3 fields.

| Metric | Target | Measured by | Gate |
|--------|--------|-------------|------|
| Log records are valid JSON [OBS-09] | 100% of stdout lines parse | integration test pipes captured stdout through `jq .`; non-zero exit blocks merge | AUTO-GATE |
| Required field presence [OBS-10] | `timestamp`,`severity`,`service.name`,`trace_id`,`span_id`,`message` on every record | `jq` field-presence assertion in the same test | AUTO-GATE |
| **No secrets/PII in logs** [OBS-11] | zero log calls pass a variable named `password`,`token`,`secret`,`api_key`,`ssn`,`dob`,`email`,`credit_card` (extend with repo-specific identity fields) | `bandit` + custom `semgrep` rules on every PR | **AUTO-GATE** |
| Trace correlation [OBS-12] | `trace_id` in response logs == incoming `traceparent` trace-id | integration test | AUTO-GATE |
| Data-classification audit [OBS-13] | no logged field exceeds the service's permitted PII level, per the `DATA-GOVERNANCE-STANDARD.md` §4 tier table | `compliance/logging-audit-YYYY-QN.md`, quarterly | REVIEW-GATE |

**Tier C (libraries/CLIs):** offer an opt-in `--log-format json` flag backed by `structlog`; default human-readable is fine. The valid-JSON and required-field gates apply **only when `--log-format json` is selected**. OTel tracing is optional and **documented as out-of-scope** in the repo's `## Observability` section (N/A-with-reason). A logging-focused library provides the reference `structlog` JSON-renderer shape.

**The PII-in-logs gate is the one non-tiered control: it is AUTO-GATE in every repo that logs anything, Tier A/B/C alike.** Privacy-first repos do not get to skip it; they are the reason it exists.

---

## 4. SLOs, SLIs & error budgets (Tier A)

Per the Google SRE Workbook. SLIs are ratio metrics `good_events / total_events`; SLOs are a target % over a **rolling 4-week window**; error budget = `(100% − SLO) × total_events`. **Do not target 100%.** Keep internal SLOs stricter than any public SLA.

**Minimum SLIs per Tier-A service:** availability (1 − HTTP-5xx ratio), latency (p99 ≤ threshold), saturation. For LLM/RAG routes, latency uses the portfolio's existing budgets from `QUALITY-AND-METRICS-STANDARD.md §2`: **p95 first-token < 1.5 s, full-response < 6 s**; non-LLM routes **p95 < 500 ms**.

**Default SLO targets by service shape** (a repo overrides values, not structure):

| Service shape | Availability SLO | Latency SLI/SLO | Notes |
|---------------|------------------|-----------------|-------|
| Public civic or benefits service | 99.5% / 4wk | p99 < 500 ms non-LLM; p95 first-token < 1.5 s LLM | error budget spends conservatively |
| Internal or evaluation API | 99.0% / 4wk | p99 < 1 s | not user-facing-critical |
| Static edge handler | 99.9% / 4wk | p99 < 300 ms | small, predictable request surface |

**Committed SLO file** — `slos/*.yaml`, schema-validated:

```yaml
name: example-service-availability
sli_query: 1 - (sum(rate(transit_assistance_http_request_errors_total[5m])) / sum(rate(transit_assistance_http_requests_total[5m])))
target_percentage: 99.5
window_days: 28
error_budget_policy: freeze-features-on-50pct-burn
```

| Metric | Target | Measured by | Gate |
|--------|--------|-------------|------|
| SLO definition exists [OBS-14] | `slos/*.yaml` present, passes JSON-Schema (`name`,`sli_query`,`target_percentage`,`window_days`,`error_budget_policy`) | schema validation in CI; no SLO file = no prod deploy | AUTO-GATE |
| Quarterly SLO review [OBS-15] | error-budget consumption vs target reviewed; SLI-vs-complaint alignment checked | ADR committed within 5 business days | REVIEW-GATE |

---

## 5. Alerting — multi-window multi-burn-rate (Tier A)

Per the SRE Workbook. For each SLO, **both** the long- and short-window conditions must be true to fire (kills flapping). Implement with Prometheus recording rules; validate with `promtool`.

| Tier | Burn rate | Long window | Short window | Budget consumed | Route |
|------|-----------|-------------|--------------|-----------------|-------|
| Page (critical) | > 14.4× | 1h | 5m | 2% / month | PagerDuty |
| Page (high) | > 6× | 6h | 30m | 5% / month | PagerDuty |
| Ticket | > 1× | 3d | 6h | 10% / month | ticketing |

```yaml
# alerts/burn-rate.yml  (promtool check rules MUST pass)
groups:
  - name: example-service-slo-burn
    rules:
      - alert: ErrorBudgetBurnCritical
        expr: |
          (slo:error_rate:ratio_rate1h{service="example-service"} > (14.4 * 0.005))
          and
          (slo:error_rate:ratio_rate5m{service="example-service"} > (14.4 * 0.005))
        labels: { severity: page }
      - alert: ErrorBudgetBurnHigh
        expr: |
          (slo:error_rate:ratio_rate6h{service="example-service"} > (6 * 0.005))
          and
          (slo:error_rate:ratio_rate30m{service="example-service"} > (6 * 0.005))
        labels: { severity: page }
```

| Metric | Target | Measured by | Gate |
|--------|--------|-------------|------|
| Alert rules valid [OBS-16] | zero errors | `promtool check rules alerts/*.yml` in CI | AUTO-GATE |
| Burn-rate tiers complete [OBS-17] | critical (14.4×, 1h+5m) **and** high (6×, 6h+30m) defined per SLO | rule-presence linter | AUTO-GATE |

**A `page`-severity alert that confirms real user impact opens an `incident` issue.** This standard owns detection and routing; what happens once a page is confirmed real (severity assignment, labelling, the postmortem clock) is owned by `INCIDENT-RESPONSE-STANDARD.md` §1–3 — a fired alert is not itself an incident record.

---

## 6. Health & readiness endpoints (Tier A)

Distinct endpoints, distinct semantics (Kubernetes probe contract):

- `GET /livez` — process alive, not deadlocked. **No external calls.** Returns `200 {"status":"ok"}` in **< 200 ms**.
- `GET /readyz` — ready for traffic, **including** dependency checks. `200 {"status":"ok","checks":{"db":"ok","cache":"ok"}}` or `503` with failing component detail.
- Both **unauthenticated** and **excluded from access logs** (no auth middleware, no log noise).

A Lambda/serverless Tier-A repo without a long-lived process declares `/livez`+`/readyz` **N/A-with-reason** (cold-start health is the platform's; readiness is the dependency check it runs on init).

```yaml
# k8s probes (OPA Conftest rejects a Deployment missing either, or pointing both at one path)
livenessProbe:  { httpGet: { path: /livez,  port: 8080 }, periodSeconds: 10, failureThreshold: 3 }
readinessProbe: { httpGet: { path: /readyz, port: 8080 }, periodSeconds: 5 }
```

| Metric | Target | Measured by | Gate |
|--------|--------|-------------|------|
| Both probes present, distinct paths [OBS-18] | `livenessProbe`+`readinessProbe` defined, different paths | `kubeval` + OPA Conftest on manifest changes | AUTO-GATE |
| `/livez` semantics [OBS-19] | < 200 ms, no dependency calls | contract test | AUTO-GATE |
| `/readyz` semantics [OBS-20] | reflects dependency health (503 on failure) | contract test with dependency stubbed down | AUTO-GATE |

---

## 7. Local-dev parity & tier declaration

Observability must be reproducible locally or it rots. `make verify` runs the same JSON-log, semconv, metric-naming, and `promtool` lints CI runs, byte-for-byte through the repository Makefile. The existing local/CI parity contract extends to telemetry checks; no new mechanism is needed.

Ship a `docker-compose.observability.yml` bringing up an OTel Collector + Grafana LGTM stack (Tempo/Mimir/Loki/Pyroscope) so a developer sees their own traces. The Collector pipeline is fixed:

```yaml
receivers:  [otlp, filelog]            # otlp: grpc 4317 + http 4318; filelog: stdout JSON
processors: [memory_limiter, batch, resource]   # memory_limiter FIRST
exporters:  [otlphttp/tempo, prometheusremotewrite/mimir, loki, otlphttp/pyroscope]
# TLS on all exporter connections in prod.
```

| Metric | Target | Measured by | Gate |
|--------|--------|-------------|------|
| Tier declared [OBS-21] | `## Observability` section names tier A/B/C and lists any N/A-with-reason | doc-lint asserts heading + tier token present | AUTO-GATE |
| Local telemetry parity [OBS-22] | `make verify` runs the same telemetry lints as CI | CI diff of lint invocations | AUTO-GATE |

---

## 8. Frontends / PWAs — Core Web Vitals (Tier B)

Instrument with `@opentelemetry/sdk-web` (stable spans for interactions + API calls) plus `@opentelemetry/browser-instrumentation` (experimental: navigation/resource timing). Emit Core Web Vitals via the `web-vitals` library as OTel metric events with `trace_id` for correlation. Every Tier-B frontend implements this RUM beacon path.

**Field SLI (p75 of real-user sessions) and the Lighthouse-CI lab gate share thresholds:**

| Metric | Target (p75 field SLI = lab gate) | Measured by | Gate |
|--------|-----------------------------------|-------------|------|
| LCP [OBS-23] | < 2500 ms | Lighthouse CI on main routes (lab); RUM p75 in Grafana (field) | AUTO-GATE (lab) |
| INP [OBS-24] | < 200 ms | as above | AUTO-GATE (lab) |
| CLS [OBS-25] | < 0.1 | as above | AUTO-GATE (lab) |
| ≥75% of sessions "good" per CWV [OBS-26] | met | RUM dashboard | REVIEW-GATE |

Lighthouse-CI lab numbers are the merge gate; field p75 RUM data is tracked separately (lab is a regression tripwire, not ground truth). This extends, and shares the budget envelope with, the existing Lighthouse gates in `QUALITY-AND-METRICS-STANDARD.md §2`.

---

## 9. Continuous profiling (REVIEW-GATE only — alpha, do not auto-gate)

The OTel **Profiles** signal is alpha in 2026; **do not depend on its API stability** and do not make it merge-blocking. Where a Tier-A service has profiling appetite, use `pyroscope-otel` → Pyroscope 2.0 / Grafana Cloud Profiles, correlated to traces via `trace_id`. Pin the profiler client version.

| Metric | Target | Measured by | Gate |
|--------|--------|-------------|------|
| Profiling runbook [OBS-27] | CPU+heap collected in prod, overhead ≤ 1%, profiles trace-correlated, endpoint configured | runbook entry per service onboarding | REVIEW-GATE |

---

## 10. When this standard does NOT apply

- **Tier C OTel tracing/metrics/SLOs/health:** N/A for libraries and local-only CLIs. Declare it: `Observability: Tier C — OTel tracing out-of-scope (no network surface). Opt-in --log-format json only.`
- **`/livez`/`/readyz`:** N/A for non-long-lived serverless surfaces — declare with reason.
- **CWV / Lighthouse:** N/A for non-UI repos.
- **The PII/secrets-in-logs gate is NEVER N/A** for any repo that logs.
- **A not-yet-implemented privacy-sensitive tool** authors this standard into its initial scaffold (structlog JSON, tier declaration, PII-log gate) before feature code, and only after its consent gate per `RESPONSIBLE-TECH-FRAMEWORK.md`.

Any skipped control is recorded as **N/A-with-reason** in the repo's `## Observability` section. Silent omission fails the tier-declaration gate (§7).

---

## GenAI telemetry — OTel semantic conventions (Tier A, AI-bearing repos)

For any repo with an LLM call path, LLM telemetry uses the **OpenTelemetry
GenAI semantic conventions** — but through the pinned shim, never raw strings:

- **Attribute names come from `STANDARDS/lib/genai_telemetry/attributes.py`**, not
  inline `gen_ai.*` literals. The conventions are **pre-stable (Development
  status)** — the shim owns the pinned `SEMCONV_VERSION` so a spec change touches
  one file. (AUTO-GATE candidate: a lint that rejects inline `gen_ai.` literals in
  instrumentation code.)
- Every LLM call records: `gen_ai.request.model`, `gen_ai.usage.input_tokens` /
  `output_tokens`, `gen_ai.usage.cache_creation.input_tokens` /
  `cache_read.input_tokens` (→ cache-hit rate = cache_read / input_tokens),
  operation duration, and `gen_ai.response.time_to_first_chunk` for streaming
  (this supplies the p95-first-token metric). Agentic paths record
  `execute_tool` spans + tool-call error rate.
- **Cost per request/conversation** is computed by `lib/genai_telemetry/pricing.py`
  from those token attributes × the pinned `pricing.json` (an estimate, not
  billing). A repository cannot claim the cost metric until this harness exists.
- **Content capture is opt-in and off by default** (OTel GenAI default + this
  portfolio's local-first stance). No prompt/response content in telemetry unless a
  repo makes a documented per-repo opt-in.

Track A (how the portfolio is *built* with AI tools) is a separate standard:
`AI-DEVELOPMENT-MEASUREMENT-STANDARD.md`, incl. the local Claude Code OTel
collector at `automation/telemetry/`.

## Metrics ledger (per repo)

Each Tier-A/B repo's `docs/ROADMAP.md` carries an **Observability** table in the portfolio-standard shape (`Metric | Target | Measured by | Gate | Owner`), filled with that repo's *values* — its service name, its SLO targets, its span-coverage artifact path. The gates themselves are not restated; they live here.

Last verified: 2026-06-21 · Recheck cadence: per OpenTelemetry Semantic Conventions release (currently v1.42.0), OTel Python Logs SDK GA, Core Web Vitals threshold revision, and OWASP Top 10 revision — confirm all four at build time.
