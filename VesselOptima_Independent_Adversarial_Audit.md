# VesselOptima — Independent Adversarial Code Audit

**Scope:** `github.com/RP-Hubb/VesselOptima` @ commit `68acfb8` (2026-09-07), cross-checked against `MASTER_BUILD_SPECIFICATION_v1.0.md`, `FINAL_HARDENING_REPORT.md`, and `IMPLEMENTATION_STATUS.md`.

**Method:** Every finding below was reproduced directly — by reading the shipped source, by running the actual engine code against the shipped demo data, or by executing the real test suite — not inferred from the hardening report's own narrative. Where the report's claim and the code's behavior diverge, both are quoted.

**Headline result:** The repository does not currently build cleanly, its own test suite cannot collect without a code fix, its shipped data package fails its own integrity check on all 19 files, and at least four of the eleven "fully remediated" defects (DEF‑001, DEF‑002, DEF‑003, DEF‑006) are not actually fixed in the code paths that production traffic uses. **This is a NO‑GO.**

---

## 0. Can the repository even run? (blocks everything else)

**Severity: P0 — Blocker**

**Evidence:** `backend/app/engines/data/quality.py` uses `Tuple` in a function signature (`-> Tuple[FreshnessStatus, Optional[float]]`, line 28) but only imports `Any, Dict, List, Optional` from `typing` (line 7), and the file has no `from __future__ import annotations`. Importing `app.main` (which every test and the API server does) raises:

```
NameError: name 'Tuple' is not defined
  app/engines/data/quality.py:28
```

I confirmed this is not an artifact of my environment — I wrote a small AST scanner over every `.py` file in `backend/app` checking for typing names used-but-not-imported; `quality.py` is the only offender, and the failure is deterministic on any Python version. Running `pytest` against the untouched repo fails at the **collection** stage, before a single test executes:

```
ImportError while loading conftest '/…/backend/tests/conftest.py'.
tests/conftest.py:20: in <module>
    from app.main import app as fastapi_app
...
NameError: name 'Tuple' is not defined
```

**Why it matters:** `FINAL_HARDENING_REPORT.md` states "293/293 PASS," "100% green," "UNCONDITIONAL GO for production deployment." None of that is possible against this commit — the application does not import, so nothing could have been executed against this exact code. Either the report was generated against a different (older or newer) state of the code than what's on GitHub, or it was not actually run. Either way, the report's core evidentiary claim is false for the commit under review.

**Recommended fix:** Add `Tuple` to the `typing` import in `quality.py` (one-line fix), then re-run the *entire* suite from a clean checkout as CI would, and commit a CI gate that fails the build on any import error — this exact class of defect (a missing import in a rarely-exercised code path) is exactly what a real CI pipeline catches before merge and what "293/293, 100% green" is supposed to already guarantee.

---

## 1. LIVE vs OFFLINE_DEMO — no genuine mode-dependent behavior

**Verdict: FAILS**

**Severity: P1 — High**

**Evidence:**
- `backend/app/api/v1/runtime.py` and `services/runtime.py` are honest in isolation: `/v1/runtime/status` correctly reports `is_live_operational: false` and lists sources as unavailable when no live feed is configured.
- But **every engine that persists a decision hardcodes the mode instead of reading it**:
  - `engines/feasibility/service.py:791` → `runtime_mode=RuntimeModeEnum.OFFLINE_DEMO`
  - `engines/procurement/service.py:243` → same
  - `engines/employment/service.py:698` → same
  - `engines/optimization/service.py:263, 300` → same
  - The identical pattern also appears in `engines/backtest/service.py`, `engines/decision/service.py`, `engines/governance/service.py`, `engines/risk/risk_service.py`, `engines/scenarios/service.py`, `engines/data/service.py`, and `services/offline_package/loader.py` — **11 files total**, confirmed by `grep -rl "runtime_mode=RuntimeModeEnum.OFFLINE_DEMO" engines services`.
  - `core/exceptions.py` defines `LiveSourceUnavailableError` and `OfflineNetworkProhibitedError`, but `grep -rn` across the entire backend shows they are **never raised anywhere** — dead code.
  - No engine (forecast, feasibility, procurement, employment, optimization) references `settings.runtime_mode` at all; I grepped for it and found zero hits outside the two decorative runtime files.
- `backend/tests/test_runtime.py`'s 11 tests only exercise the two decorative endpoints. None of them assert that a decision persisted while in LIVE mode is actually tagged LIVE, or that a LIVE run blocks when a required source is unavailable.

**Why it matters:** An operator who switches the platform to LIVE mode gets a status widget that says LIVE, while every single decision record written to the database is still silently labeled `OFFLINE_DEMO`. This is worse than "silent fallback" — it's a mislabeled audit trail. A future compliance reviewer pulling governance records would see `OFFLINE_DEMO` on every decision and have no way to tell, from the persisted record itself, that the operator believed they were running LIVE. The Master Spec's explicit requirement ("A required source failure is an explicit LIVE DATA ERROR… must not use a stale cache, different source, or frozen demo package as a substitute") has no enforcement point anywhere in the decision-producing code.

**Recommended fix:** Thread `settings.runtime_mode` into every engine's persistence call instead of a literal enum constant; wire `LiveSourceUnavailableError` into the actual data-access layer so a LIVE run with no configured adapter raises rather than silently computing against offline data; add a regression test that asserts persisted `runtime_mode` on a `DecisionRun`/`BacktestRun`/etc. matches the mode the request was made under.

---

## 2. Employment authority gate — DEF‑001 is dead code on the real data path

**Verdict: FAILS (disproven live against the shipped demo package)**

**Severity: P0 — Critical**

**Evidence:**
- `engines/employment/service.py` reads the field as `employment_control_status` in five places (lines 77, 101, 127, 151, 567), defaulting to `"ESTABLISHED"` whenever the key is absent.
- The actual field — in both the ORM model (`models/domain.py:292, 1015` → `employment_control = Column(...)`) and the shipped CSV (`data/offline/packages/demo-v1/vessels/vessels.csv`, column 14, header `employment_control`) — is named **`employment_control`**, never `employment_control_status`. The two names never match, so the `.get(...)` / `getattr(...)` calls can never find real data and *always* fall through to the `"ESTABLISHED"` default.
- **Live proof against the shipped data:** the demo fleet has 10 vessels marked `NOT_CONTROLLED` and 2 marked `UNKNOWN` in `vessels.csv`. I ran `EmploymentService(db=None)._get_vessel(3)` (vessel 3 = "Pacific Falcon," ground truth `NOT_CONTROLLED`) directly against the unmodified code:
  ```
  Vessel 3 raw dict field employment_control_status: ESTABLISHED
  ```
  Every one of the 12 non-controlled/unknown vessels resolves to `ESTABLISHED` the same way — the gate is unreachable for 100% of real data.
- `backend/tests/test_employment_authority.py`'s four DEF‑001 regression tests all `monkeypatch service._get_vessel` to *inject the correctly-named key by hand*, bypassing the real loader entirely. None of the four tests exercises the actual CSV/DB path with real data.

**Why it matters:** This is precisely the failure mode the Master Spec's authority gate exists to prevent — the engine will happily evaluate and (subject to other, unrelated feasibility checks) recommend "alternative employment" for a vessel the operator does not commercially control, because the very check meant to stop that always reads a default value instead of the truth.

**Recommended fix:** Rename the lookup key to `employment_control` everywhere in `engines/employment/service.py` (and audit for the same mistake elsewhere), delete the monkeypatch-based tests, and add an integration test that loads a real `NOT_CONTROLLED` vessel from the shipped CSV/DB through the unmodified public API and asserts the gate actually fires.

---

## 3. Missing port constraints — DEF‑003 only covers the "zero constraints" case, not the far more common "partial constraints" case

**Verdict: FAILS (disproven live against real shipped port data)**

**Severity: P0 — Critical**

**Evidence:**
- `engines/feasibility/port_checks.py:52` — `if not constraints:` correctly fails the check when a port has **no** constraint rows at all (this part of DEF‑003 is genuinely fixed).
- But the loop (lines 65–178) initializes `draft_failed / loa_failed / beam_failed` to `False` and only flips them if a matching `rule_type` record is *present and violated*. There is no tracking of which rule types were ever checked, and only one reason code exists (`PORT_CONSTRAINTS_NOT_RECORDED`), fired only for the fully-empty case.
- The shipped `data/offline/packages/demo-v1/ports/port_constraints.csv` is **not** fully populated for most ports — e.g. "Outer Harbour" (port 3), "Haldia" (port 4), "Nelson Point" (port 6), "PWCS Kooragang" (port 7), "Muara Berau" (port 9) each have **only** a `MAX_DRAFT` row, with no `MAX_LOA` or `MAX_BEAM` record at all.
- **Live proof:** I fed the *actual* port‑7 constraint set (one `MAX_DRAFT` row) into `evaluate_port_constraints()` with a fictitious but deliberately absurd vessel (LOA 400 m, beam 65 m — larger than any bulk carrier in existence):
  ```
  is_pass: True
  failed_checks: []
  reason_codes: []
  checks recorded: ['origin_max_draft']
  ```
  No LOA or beam evidence is ever recorded; the vessel passes silently because those dimensions were never checked, not because they were checked and satisfied.

**Why it matters:** This is exactly the "unknown becomes feasible" failure the audit item asks about, and it is not a hypothetical edge case — it is the **normal state of the real, shipped port data**. Most ports in the demo package would silently wave through any vessel on the dimensions they haven't recorded.

**Recommended fix:** Require an explicit, positively-recorded pass/fail (or an explicit "not recorded" reason code) for each of MAX_DRAFT, MAX_LOA, and MAX_BEAM independently — partial data must degrade to "not recorded" per-dimension, not silently default to pass.

---

## 4. Backtest benchmarks — DEF‑002 fixed the frontend, not the backend that computes the numbers

**Verdict: FAILS**

**Severity: P1 — High**

**Evidence:**
- The frontend fix is real: `frontend/src/app/backtest/page.tsx` genuinely fetches `benchmarksData` from the API rather than a hardcoded array. Credit where due.
- But `backend/app/engines/backtest/benchmarks.py`, which computes the values the frontend displays, is full of constants with no derivation from vessel-, route-, or market-specific data:
  - `daily_idle = 6500.0` (line 84)
  - `fixture_contrib = 180000.0` (line 133)
  - `idle_cost = 65000.0` — repeated verbatim in three different strategy classes (lines 144, 212, 286)
  - a `120000.0` fallback default for missing candidate economics (line 199)
  - `contrib = float(item.get("realized_contribution_usd", item.get("contribution", 350000.0)))` (line 334) and `nominal = 80000.0` (line 346)
  - `util = 60.0  # Industry standard benchmark utilization` (line 356) — no citation, no source.
- Worse: the `HistoricalActualOutcomeBenchmark` strategy is labeled `strategy_type: HISTORICAL_ACTUAL`, `is_ex_post_outcome_baseline: True` — implying real observed chartering outcomes — but its `historical_actuals` input is **never populated anywhere**: I grepped the API schema (`schemas/backtest.py`), the router (`api/v1/backtest.py`), and the entire `data/` tree for `historical_actuals` and found nothing. Every real invocation falls into the synthetic-default branch (`$80,000`/vessel, `60%` utilization), yet it's displayed under a label implying it is real historical fact.

**Why it matters:** Users comparing "VesselOptima's decisions" against "industry benchmarks" are actually comparing against numbers with no economic grounding, one of which is explicitly mislabeled as historical fact when it is 100% fabricated.

**Recommended fix:** Either wire a real historical-outcomes dataset into `historical_actuals`, or rename/relabel the strategy to make clear it's a synthetic placeholder (`DEMO ASSUMPTION` per the Master Spec's own taxonomy — see Finding 10). Derive the other benchmark constants from actual per-vessel/per-route data already available in the snapshot rather than fixed dollar figures.

---

## 5. Forecast explainability — the SHAP mechanism is real but misdescribed; the "empirical" prediction intervals are fabricated

**Verdict: PARTIAL — mechanism is legitimate, report is inaccurate, intervals are not what they claim to be**

**Severity: P2 (documentation) / P1 (fabricated intervals)**

**Evidence:**
- `engines/forecast/models.py:298` genuinely uses `booster.predict(dmat, pred_contribs=True)` — XGBoost's native exact-Shapley contribution API. This is a legitimate, mathematically equivalent method to TreeSHAP for tree ensembles, and it does explain the actual loaded model that produced the point forecast (verified: `service.py`'s `get_forecast()` calls `.explain()` on the same deserialized `model` object used for `.predict()`).
- However, `FINAL_HARDENING_REPORT.md` specifically claims the implementation uses **`shap.TreeExplainer`**. I grepped the entire backend for `import shap` / `shap\.` — zero matches. The `shap` package is never used. This is a factually incorrect claim in the hardening report about its own remediation.
- The explanation only covers the first forecast step (t+1); a user viewing a 30-day horizon chart gets an explanation for day 1 only, with no indication the multi-step recursive forecast's later days have different, unexplained drivers.
- More seriously: `engines/forecast/evaluation.py` genuinely computes real out-of-sample walk-forward residuals during training (`residuals = actuals - preds`, line 146; stored in `EvaluationResult.residuals`). But `engines/forecast/service.py:132`, at forecast-serving time, **discards these real residuals and fabricates fake ones instead**:
  ```python
  # Synthetic residual spread based on out-of-sample validation error
  simulated_residuals = list(np.random.normal(0, val_rmse, 100))
  ```
  This feeds a genuinely well-built empirical-quantile engine (`uncertainty.py`, correctly implements percentile-based intervals) with **Gaussian noise instead of the real, possibly skewed/fat-tailed residual distribution** the freight/BDI domain is known to exhibit. The API still labels these "empirical prediction intervals" and reports `"validation_method": "expanding_window_walk_forward"`.

**Why it matters:** The uncertainty bands shown to a chartering decision-maker are not derived from the model's actual historical error distribution — they're a parametric normal approximation dressed up as empirical, using a fixed seed for reproducibility rather than genuine data.

**Recommended fix:** Persist the real `residuals` array from `evaluation.py` into `metrics.json` (the schema/plumbing already exists) and load it in `service.py` instead of calling `np.random.normal`. Correct the hardening report's technical description to reference the actual method used.

---

## 6. Backtest point-in-time economics — the leakage-prevention machinery is sound but is exercised against a fabricated, disconnected toy dataset

**Verdict: FAILS (mechanism is real; the data behind it is not)**

**Severity: P0 — Critical**

**Evidence:**
- `engines/backtest/events.py` and `leakage.py` are genuinely well-designed: immutable, hash-verified `HistoricalEvent` records, strict `availability_timestamp <= as_of` filtering (`events.py`, `get_events_available_at`), and a dedicated `InformationLeakageDetector` with real look-ahead detection logic. This part of the design is sound.
- But the entire event stream that feeds every real backtest run is **not** built from the platform's actual 19-CSV, 20-vessel `demo-v1` offline package. It comes from `engines/backtest/service.py:391`, `generate_demo_event_stream()` — a hand-typed Python function containing **4 fictional vessels**, **4 fictional cargoes**, **4 fictional freight routes**, and **one** operational delay event, all baked directly into source code (lines 399–497).
- **Confirmed this is the live production path, not a test fixture:** `service.py:167` — `stream = event_stream or self.generate_demo_event_stream(...)`. The only API entry point, `POST /v1/backtest/runs` (`api/v1/backtest.py:107-127`), **never supplies an `event_stream`**, so every real backtest run falls through to the fictional generator. The `dataset_versions` field the API schema exposes is accepted but never actually used to select real data.
- Every event in this fabricated stream sets `availability_timestamp == event_timestamp` (no line has a reporting lag), so the leakage detector — while architecturally correct — has never been exercised against a case where it would actually need to catch something.
- DEF‑006 claims "vessel-specific `consumption_laden`" was wired into voyage-cost calculations. In reality (`orchestrator.py:505-513`), `v.get("consumption_laden", <hardcoded per-class default>)` always falls to the class-bucket default (28/22/30/35 MT/day) because the fictional vessel payloads in `generate_demo_event_stream` never include a `consumption_laden` field at all — and those defaults don't match the real fleet's actual per-vessel values in `vessels.csv` (17.5–18.5 MT/day range). `idle_days_saved: 5.0` and `avoided_idle_cost: 32500.0` (`orchestrator.py`, candidate dict) are likewise flat constants applied identically to every candidate regardless of vessel or route.

**Why it matters:** Phase 13 markets itself as "Point-in-Time Reconstruction," "5-Benchmark Comparative Testing," and integration with Phase 12's data governance layer. In reality, the numbers a user sees from a backtest run are computed against a ~20-line fictional dataset with no connection to the real fleet, real cargo book, or real market data the rest of the platform uses — and the "no-look-ahead" guarantee, while correctly coded, is never actually tested against realistic reporting delays.

**Recommended fix:** Build the event stream from the real, versioned `demo-v1` package (Phase 12's data governance layer already has the versioning/provenance/hash machinery to do this correctly) rather than a hardcoded stub; introduce genuine reporting lags into event `availability_timestamp` so the leakage detector is meaningfully exercised; replace the per-class fuel/idle constants with real per-vessel data.

---

## 7. Model SHA-256 verification — genuinely implemented, but fails open when the hash is absent

**Verdict: MOSTLY PASSES — one real gap**

**Severity: P2 — Medium**

**Evidence:**
- `engines/forecast/artifacts.py`'s `load_artifact()` does read `metadata.json` first, compute the SHA-256 of `model.joblib`, and compare **before** calling `joblib.load()` (lines ~130-155). This is correctly ordered and DEF‑007's core claim is true.
- However, the check is gated by `if expected_hash:` — if `artifact_hash` is missing or falsy in `metadata.json`, verification is **silently skipped** and deserialization proceeds unconditionally.
- **Live proof:** I generated a normal artifact, stripped `artifact_hash` from its `metadata.json`, appended arbitrary bytes to `model.joblib` (simulating tampering), and called `load_artifact()` on the unmodified code:
  ```
  BYPASS CONFIRMED: tampered artifact loaded successfully with no hash present.
  ```
- `backend/tests/test_artifact_integrity.py` has three tests (success, tamper-detected, file-missing) but none covering the missing-hash-field bypass.

**Why it matters:** The verification is real for well-formed metadata, but "fail open on missing field" is the wrong default for a security control — any artifact directory lacking (or stripped of) the hash field defeats the entire mechanism.

**Recommended fix:** Change `if expected_hash:` to require the field — raise if `artifact_hash` is absent rather than silently trusting the artifact. Add a regression test for this exact case.

---

## 8. Governance / RBAC — trivially spoofable; there is no authentication layer at all

**Verdict: FAILS**

**Severity: P0 — Critical**

**Evidence:**
- `api/v1/governance.py`'s `_assert_actor_identity(actor, actor_role)` (line 42) only checks that `actor` is a non-empty string and `actor_role` is one of a fixed enum of role names. It does not — and cannot — verify the caller actually holds that role, because **there is no authentication mechanism anywhere in the backend**: I grepped the entire codebase for `OAuth2`, `JWT`, `jwt`, `APIKeyHeader`, `HTTPBearer`, `Authorization`, `get_current_user` — zero matches.
- `actor` and `actor_role` are plain fields in the client-submitted JSON body of every governance request (create/submit/approve/reject/override).
- The `mode_label = "AUTHENTICATED_LIVE" if is_live else "OFFLINE_DEMO_ASSERTION"` logging line (governance.py, near line 58) is itself misleading — it labels an action "AUTHENTICATED_LIVE" purely because a global settings flag equals `"LIVE"`, with no actual authentication having occurred.
- **Live proof (end-to-end, via `TestClient` against the real FastAPI app, no auth headers of any kind):**
  ```python
  # create + submit a package as an unprivileged "ANALYST" actor
  client.post("/v1/governance/packages", json={..., "created_by_role": "ANALYST"})
  client.post(f"/v1/governance/packages/{pkg_id}/submit", json={"actor_role": "ANALYST", ...})
  # a completely different, uncredentialed caller self-declares APPROVER and approves it
  client.post(f"/v1/governance/packages/{pkg_id}/approve",
              json={"actor": "totally_unverified_stranger", "actor_role": "APPROVER", ...})
  ```
  Nothing in the request proves `totally_unverified_stranger` is an approver — the string is simply believed.
- `test_governance_engine.py`'s role tests (`test_approval_role_authorization`, `test_governance_identity_assertion_and_role_validation`) only test that the *string* matches an allowed enum value and that separation-of-duties (creator ≠ approver by name) holds — neither test, nor any other in the suite, tests identity binding, because there is no identity system to test.

**Why it matters:** Every governance control described in Phase 11 — approval workflows, separation of duties, override justification — sits on top of a role claim any HTTP client can set to anything it wants. This is the single most severe finding in the audit: it means the entire "institutional control layer" the Master Spec and IMPLEMENTATION_STATUS.md describe as complete provides no actual access control.

**Recommended fix:** This needs a real authentication/authorization layer (session tokens, JWT, or SSO-backed identity) binding `actor` to a server-verified role before any of the governance business logic runs. Nothing in Phase 11 can be considered "institutional control" until this exists.

---

## 9. Phase 7 as sole optimizer — genuinely verified true

**Verdict: PASSES**

**Severity: N/A (positive finding)**

**Evidence:** I grepped the entire `engines/` tree for other solver libraries or hand-rolled assignment logic (`pulp`, `pyomo`, `ortools`, `scipy.optimize.linprog`, `cvxpy`, `highspy`, `linear_sum_assignment`) outside `engines/optimization` — no matches. I then traced `engines/backtest/orchestrator.py` directly: it imports `OptimizationModel` from `engines.optimization.model` (line 36) and calls `.solve()` on it (line 319) for its `OPTIMAL_POLICY` arm. The alternative benchmark "strategies" (`FirstFeasibleStrategy`, `ContinueCurrentEmploymentStrategy`, etc.) are explicitly non-MILP heuristic comparators — that's their intended purpose, not a hidden second optimizer.

**No action required**, beyond fixing the *inputs* to that shared solver call (see Finding 6).

---

## 10. Data provenance / claim labels — the Master Spec's taxonomy is not implemented

**Verdict: FAILS**

**Severity: P1 — High (root cause underlying findings 4–6)**

**Evidence:** The Master Spec (§ table, lines 15–19) mandates a five-tier disclosure taxonomy on every displayed figure: **PROVEN**, **MODELED**, **DEMO ASSUMPTION**, **PROXY ESTIMATE**, **DATA UNAVAILABLE**, each with specific required metadata (source/version, model version + run ID, `demo=true` + validity period, formula + calibration, missing-field + recovery action, respectively). I grepped the entire backend for these literal tokens (`PROVEN`, `MODELED`, `DEMO_ASSUMPTION`, `PROXY_ESTIMATE`, `DATA_UNAVAILABLE`, `ClaimLabel`, `claim_label`, `claim_tag`) and found only two loosely related, differently-named reason codes in two unrelated engines (`ECONOMIC_DATA_UNAVAILABLE` in employment, `FORECAST_DATA_UNAVAILABLE` in procurement) — **not** the standardized taxonomy, and not applied to forecast values, freight rates, cost estimates, or backtest benchmarks anywhere.

**Why it matters:** This is the structural reason Findings 4 and 6 could ship unnoticed — there is no systematic tagging discipline anywhere that would force a developer (or a reviewer) to mark a `$80,000` synthetic default as `DEMO ASSUMPTION` rather than let it flow to the UI unlabeled next to a field named `is_ex_post_outcome_baseline: True`.

**Recommended fix:** Implement the five-tier taxonomy as a real, shared schema type; require every numeric field returned by every engine to declare one, and fail CI/schema validation on any output field missing a label.

---

## 11. Documentation vs. implementation

**Verdict: FAILS — material misstatements in both audit documents**

| Claim (source) | Reality |
|---|---|
| "293/293 PASS… 100% green… UNCONDITIONAL GO" (`FINAL_HARDENING_REPORT.md`) | Repo does not import; pytest cannot collect. After a one-line fix + running the migrations the setup docs imply but never automate, actual result is **285 passed, 8 failed** (manifest hash failures — see §12). |
| "native `shap.TreeExplainer` computing exact Shapley values" (`FINAL_HARDENING_REPORT.md`, DEF‑005) | `shap` is never imported anywhere in the repo; the real mechanism is XGBoost's own `pred_contribs=True`. Equivalent math, but a specifically false library citation. |
| DEF‑001 "Employment Authority Enforcement — Fully Remediated" | Dead code on real data due to a field-name mismatch (Finding 2). |
| DEF‑002 "Backtest Benchmark Hardcoding — Fully Remediated" | True for the frontend only; backend generation remains full of hardcoded constants, including a mislabeled synthetic "historical actual" (Finding 4). |
| DEF‑003 "Port Constraint Validation — Fully Remediated" | True only for fully-empty constraint sets; silently passes on the far more common partially-recorded case, proven against the shipped data (Finding 3). |
| DEF‑006 "vessel-specific consumption_laden" | Falls back to class-bucket constants in the only code path actually used, because the backtest's fictional vessel data never carries this field (Finding 6). |
| `IMPLEMENTATION_STATUS.md`, Phase 13: "Full Platform Regression: 293/293 PASS (100% green)… UNCONDITIONAL GO for production deployment" | Same as row 1. |

**Recommended fix:** Regenerate both documents only after an actual, reproducible, from-clean-checkout CI run; remove specific technical claims (e.g., which library is used) that weren't verified against the code.

---

## 12. Other hidden defects found during this audit (not on the original checklist, but material)

**Severity: P0 — the shipped offline data package fails its own integrity check on every file**

**Evidence:** `backend/tests/test_offline_package.py::test_manifest_verification_pristine` fails on a clean checkout. I extended the check to all 19 files declared in `data/offline/packages/demo-v1/manifest.json`:
```
Total files declared: 19
Mismatches: 19
```
Every single file's actual SHA-256 differs from the hash recorded in `manifest.json`, even though row counts match exactly for every file (confirming this isn't a content/schema change, but a stale-manifest problem — the CSVs were regenerated/edited after the manifest was last committed, and the manifest was never regenerated before commit). This cascades into two further test failures whose assertions target the wrong error message (`test_manifest_detects_missing_file` / `test_manifest_detects_row_count_mismatch` expect a "missing file" or "row count" error but get a hash-mismatch error first, because the fixture copies the already-broken package).

**Why it matters:** Phase 2 and Phase 12 both center their claims on SHA-256–verified data integrity for the offline package. That verification currently fails for the entire package as committed. Nothing downstream (forecast training provenance, `package_id: "demo-v1"` stamped onto every decision record) can be trusted to match a specific, verifiable data snapshot until this is fixed.

**Severity: P1 — test suite has a latent cross-contamination bug in DB session fixtures**

**Evidence:** `test_governance_engine.py`, `test_procurement_engine.py`, `test_risk_engine.py`, `test_scenario_engine.py`, and `test_offline_isolation.py` each define their own local `db_session` fixture using `SessionLocal` imported directly from `app.db.session` (the **production** default engine, `sqlite:///./vesseloptima.db`), instead of the `db`/`client` fixtures `conftest.py` provides (bound to `test_vesseloptima.db`, the only database that actually gets `Base.metadata.create_all()` run against it). On a genuinely clean checkout with no pre-existing `vesseloptima.db`, this produces `sqlite3.OperationalError: no such table: …` for 24 tests — which is what I observed before manually running `alembic upgrade head` out-of-band. This means the claimed test count is contingent on an undocumented, unautomated setup step (or a stale local `vesseloptima.db` left over from prior development), not a reproducible CI process.

**Recommended fix:** Standardize every test file on the shared `conftest.py` fixtures; never import `SessionLocal` directly in a test. Document (or better, script) the migration step required before tests can pass, and run it in CI from a genuinely clean state to confirm.

---

## Summary Table

| # | Area | Verdict | Severity |
|---|---|---|---|
| 0 | Repository imports/builds at all | **FAIL** | P0 Blocker |
| 1 | LIVE vs OFFLINE_DEMO enforcement | FAIL | P1 |
| 2 | Employment authority gate | **FAIL** (dead code, proven live) | P0 |
| 3 | Missing port constraints → PASS | **FAIL** (proven live, real data) | P0 |
| 4 | Backtest benchmarks dynamic | FAIL (backend) | P1 |
| 5 | Forecast SHAP / explainability | PARTIAL | P1–P2 |
| 6 | Backtest point-in-time economics | **FAIL** (real mechanism, fake data) | P0 |
| 7 | Model SHA-256 before deserialization | PASS w/ gap | P2 |
| 8 | Governance/RBAC spoofing | **FAIL** (no auth layer exists) | P0 |
| 9 | Phase 7 sole optimizer | **PASS** | — |
| 10 | Provenance/claim label taxonomy | FAIL | P1 |
| 11 | Documentation accuracy | FAIL | P1 |
| 12 | Data package integrity / test isolation | **FAIL** | P0 / P1 |

**Tally: 2 genuine passes (9, and 7-with-a-gap), 1 partial (5), 9 outright failures — 5 of them P0.**

---

## Independent Verdict: **NO-GO**

The claimed "293/293, UNCONDITIONAL GO" state is not reproducible against the reviewed commit: the application does not import, the shipped data package fails its own hash verification on all 19 files, and — most seriously — four of the specific defects the hardening report says were "fully remediated" (employment authority, port constraints, backtest benchmark realism, backtest vessel-specific economics) are demonstrably not fixed in the code paths real traffic uses, and one control (governance RBAC) has no enforcement mechanism at all because there is no authentication layer anywhere in the backend.

None of this reflects an unsalvageable architecture — the underlying design in several places (point-in-time snapshot/leakage detection, artifact hash verification, the MILP solver reuse in backtesting) is genuinely well-built. The problem is a repeated pattern: the *mechanism* is implemented correctly, but the *data feeding it* is either fictional, mismatched by field name, or synthetic-but-mislabeled — and the test suite's monkeypatching in several cases certifies the mechanism in isolation without ever exercising it against the real data path.

**Do not proceed to Phase 14.** Recommended sequence before any further phase work:
1. Fix the P0 blocker (Finding 0) and get a real, reproducible, clean-checkout CI run.
2. Regenerate the offline package manifest and add a CI gate that runs `verify_manifest()` on every commit.
3. Fix the four field-mapping/data-wiring defects (Findings 2, 3, 6) — these are the ones that actually defeat safety-relevant gates in production use, not just cosmetic issues.
4. Build a real authentication/authorization layer before governance/RBAC can be considered implemented at all (Finding 8).
5. Only after 1–4 are independently re-verified (ideally by someone other than whoever wrote the original hardening report) should a "GO" of any kind — conditional or otherwise — be considered.
