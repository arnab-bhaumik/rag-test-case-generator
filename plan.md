# RAG-Based Test Case Generator — Project Plan

## 1. Overview

An application that generates comprehensive test cases from design documents (docs/PDFs) and Jira work items, using Retrieval-Augmented Generation. It retrieves relevant requirements plus your team's existing test case patterns, then generates new test cases that follow your established style and maximize requirement coverage. Generated test cases are shown in a UI for review, and can then be downloaded as Excel or uploaded directly into Jira as test issues. Approved outputs feed back into the pattern library, so the system's style improves over time.

Built iteratively in VS Code with Claude Code as the build assistant.

---

## 2. Prerequisites

### Accounts / keys (you provide)
- [ ] Groq API key — generation + decomposition + audit calls
- [ ] (Optional) Anthropic API key (Claude) — can be used instead of, or alongside, Groq (see §3 LLM abstraction)
- [ ] Jira API token + base URL (`https://<your-domain>.atlassian.net`) + email for basic auth
- [ ] (Optional) Cohere/Voyage rerank API key — only if you later want reranking; not required to start

### Local environment
- [ ] Python 3.11+
- [ ] Node.js 20+ and npm — for the React frontend (see §3)
- [ ] VS Code + Claude Code extension
- [ ] Git + a repo (GitHub/GitLab) for version control
- [ ] `pip` / `venv` or `uv` for dependency management

### Data you should have ready before Sprint 1
- [ ] Export of old test cases as CSV/Excel (at least a representative sample — 50-100 rows ideal)
- [ ] 2-3 sample design docs/PDFs
- [ ] 2-3 sample Jira ticket keys to test ingestion against
- [ ] Column mapping decided for your CSV (Test Case ID, Title, Preconditions, Steps, Expected Result, Module, Priority)

---

## 3. Language & Tech Stack

| Layer | Choice | Why |
|---|---|---|
| Core language | **Python 3.11+** | Best RAG/LLM ecosystem, fastest to iterate with Claude Code |
| LLM | Groq (default) and/or Claude (Anthropic) via a swappable `llm_client.py` | Generation, decomposition, coverage audit — Groq for cheap/fast calls, Claude optionally for the highest-quality generation/audit passes |
| Embeddings | **Local** — `sentence-transformers` (`all-MiniLM-L6-v2`), used via Chroma's built-in default embedding function | Free, runs on CPU, no API key needed |
| Vector DB | **ChromaDB** (embedded, in-process) | Free, no separate service to run, persists to local disk, simplest to start with |
| Jira integration | `jira` Python package or raw REST calls via `requests` | Official REST API v3 |
| Doc/PDF parsing | `pdfplumber`, `python-docx` | Handles text-based PDFs/DOCX directly; `unstructured` deferred — only worth the extra weight if OCR (scanned PDFs) or complex table extraction is actually needed |
| API layer | FastAPI, CORS enabled | Endpoints the frontend calls (runs, review, coverage, export, upload); run status is polled (multi-step progress), not just single request/response |
| Frontend | **React + Vite + TypeScript** | UX Screen/ mockups (custom sidebar nav, modals, drag-drop upload, inline editing, live run-progress) are far more bespoke than Streamlit comfortably delivers — a real frontend matches them directly. Talks to the FastAPI backend over REST. |
| Excel export | `openpyxl` | Write approved test cases to a formatted `.xlsx` |
| Config/secrets | `.env` + `python-dotenv` | Never commit keys |
| Orchestration | Plain Python modules first; LangChain only if complexity demands it | Avoid framework overhead early |

Note: run progress (Decomposing → Retrieving context → Generating → Checking coverage, per Screen 1's in-progress state) is tracked in-process/local storage, not a full task queue (Celery/Redis) — revisit only if real ticket volume demands it (see §7 open decisions).

---

## 4. Folder Structure

```
rag-test-case-generator/
├── plan.md
├── README.md
├── .env.example
├── .gitignore
├── requirements.txt
├── UX Screen/                        # target UI mockups (4 screens) — source of truth for frontend/
├── chroma_db/                       # Chroma's persisted local data (gitignored)
│
├── src/
│   ├── config.py                   # loads env vars, constants
│   │
│   ├── ingestion/
│   │   ├── jira_client.py          # fetch Jira issues via REST API
│   │   ├── doc_parser.py           # parse PDFs/docx into text + metadata
│   │   ├── csv_test_case_loader.py # load old test cases from CSV/Excel
│   │   └── chunker.py              # semantic chunking logic
│   │
│   ├── embeddings/
│   │   └── embedder.py             # wraps local sentence-transformers model (or Chroma's default embedding function directly)
│   │
│   ├── vectorstore/
│   │   ├── chroma_client.py        # persistent client + collection setup
│   │   ├── design_docs_store.py    # CRUD for design_docs collection
│   │   └── test_cases_store.py     # CRUD for old_test_cases collection
│   │
│   ├── retrieval/
│   │   └── retriever.py            # hybrid search + filtering + reranking
│   │
│   ├── generation/
│   │   ├── llm_client.py           # provider abstraction: Groq and/or Claude, switchable via config
│   │   ├── decomposer.py           # requirement → atomic testable conditions
│   │   ├── prompts.py               # all system prompts (generation, audit)
│   │   ├── generator.py            # calls LLM (via llm_client) to generate test cases
│   │   └── coverage_auditor.py     # self-critique pass, finds gaps
│   │
│   ├── traceability/
│   │   └── rtm_builder.py          # builds Requirement Traceability Matrix
│   │
│   ├── export/
│   │   ├── excel_exporter.py       # writes approved test cases to .xlsx
│   │   └── jira_uploader.py        # creates Jira test issues/subtasks from approved test cases
│   │
│   ├── models/
│   │   └── schemas.py              # Pydantic models: TestCase (incl. category, grounded, manuallyVerified, status),
│   │                                #   Requirement, Condition, Run (incl. step-progress state), CoverageGap
│   │
│   └── pipeline.py                 # orchestrates the full end-to-end flow
│
├── api/
│   ├── main.py                     # FastAPI app + CORS setup
│   └── routers/
│       ├── runs.py                 # POST /runs, GET /runs, GET /runs/{id}, GET /runs/{id}/status
│       ├── test_cases.py           # PATCH /test-cases/{id}, bulk approve/reject, regenerate
│       ├── test_case_library.py    # POST /library/import (CSV/XLSX upload), GET /library (search/browse), GET /library/{id}
│       ├── coverage.py             # GET /runs/{id}/coverage, POST gaps/{category}/acknowledge
│       ├── export.py               # POST /export/excel, POST /export/jira
│       └── modules.py              # GET /modules — distinct module values from old_test_cases metadata
│
├── frontend/                       # React + Vite + TypeScript — see UX Screen/ for the 4 target screens
│   ├── package.json
│   ├── vite.config.ts
│   └── src/
│       ├── main.tsx
│       ├── App.tsx                 # router + sidebar shell (Generate/Review/Coverage Matrix/Export/Test Case Library/Run History/Settings)
│       ├── api/client.ts           # typed fetch wrappers for the FastAPI backend
│       ├── pages/
│       │   ├── Generate.tsx        # Screen 1 — input/trigger + live run-status polling
│       │   ├── Review.tsx          # Screen 2 — review queue
│       │   ├── CoverageMatrix.tsx  # Screen 3 — traceability matrix
│       │   ├── Export.tsx          # Screen 4 — Excel/Jira export
│       │   ├── TestCaseLibrary.tsx # Screen 5 — browse/search the old_test_cases pattern library + import CSV/XLSX
│       │   ├── RunHistory.tsx
│       │   └── Settings.tsx
│       ├── components/             # shared: Sidebar, Modal, StatusPill, Spinner, etc.
│       └── styles/tokens.css       # OKLCH design tokens extracted from UX Screen/
│
├── scripts/
│   ├── init_chroma_collections.py  # one-time collection setup
│   ├── bulk_import_old_test_cases.py
│   └── run_pipeline_cli.py         # CLI entry point for local testing
│
├── data/
│   ├── raw/                        # uploaded docs/CSVs (gitignored)
│   └── sample/                     # small sample fixtures for testing
│
├── tests/
│   ├── test_chunker.py
│   ├── test_retriever.py
│   ├── test_decomposer.py
│   └── test_generator.py
│
└── outputs/
    ├── generated_test_cases/
    └── rtm/
```

---

## 5. End-to-End Flow

1. **Trigger** (Screen 1 — Generate) — user provides a Jira ticket key or uploads a design doc, optionally scoped to a module; the run starts as a background job (`POST /runs`) and the UI polls `GET /runs/{id}/status` to drive the step tracker.
2. **Ingestion** — `jira_client.py` or `doc_parser.py` pulls raw content + metadata. *(status step: n/a — precedes "Decomposing")*
3. **Decomposition** — `decomposer.py` calls the LLM (via `llm_client.py`) to break the requirement into atomic testable conditions. *(status step: "Decomposing requirement")*
4. **Retrieval** — for each condition, `retriever.py` queries: *(status step: "Retrieving related context")*
   - `design_docs` collection for related requirement context
   - `old_test_cases` collection for style examples (similarity) and module history (coverage patterns)
5. **Generation** — `generator.py` calls the LLM with the condition + retrieved context + a fixed 7-category taxonomy (**Positive, Negative, Boundary, Edge, Security, Integration, Data Validation**), returns structured JSON test cases per category, each tagged `grounded: bool` (could the coverage-audit pass confirm it against the source requirement?). *(status step: "Generating test cases")*
6. **Coverage audit** — `coverage_auditor.py` runs a second LLM pass checking every condition/category is covered, sets the `grounded` flag per case, and loops back into generation for gaps only. A category with zero cases becomes a **coverage gap**, which the reviewer can later fill (regenerate) or acknowledge (mark not applicable). *(status step: "Checking coverage")*
7. **RTM build** — `rtm_builder.py` produces the Requirement Traceability Matrix mapping conditions → test case IDs, including unacknowledged/acknowledged gap state.
8. **Review** (Screen 2 — Review Queue) — generated test cases are shown grouped by category, with inline edit (title/preconditions/steps/expected result), bulk select/approve/reject, single-case regenerate, and gap-section actions ("Generate manually" / "Mark reviewed — not applicable"). A case with `grounded: false` cannot be approved until the reviewer checks "I have manually verified this against the requirement."
9. **Coverage Matrix** (Screen 3) — a dedicated, filterable (search/module/coverage-status) view of the RTM: AC → linked test cases → covered/uncovered.
10. **Feedback write-back** — approved test cases are upserted into the `old_test_cases` Chroma collection, closing the loop.
11. **Export/upload** (Screen 4 — Export) — enabled only when there's ≥1 approved case, no case still needs verification, and no unacknowledged coverage gaps. The reviewer either:
    - **Downloads Excel** — `excel_exporter.py` writes approved cases (+ RTM) to a formatted `.xlsx`, or
    - **Uploads to Jira** — behind a confirmation modal, `jira_uploader.py` creates a test issue (or subtask, depending on your Jira setup — plain issue type vs Xray "Test" issue type) per approved test case, linked back to the original requirement/story. Per-item results (success/failure + reason) are shown, with "Retry failed only" on partial failure.
12. **Run History** — past runs are listable and reopenable back into the Review flow.

**Library management** (Screen 5 — Test Case Library, independent of any single generation run): the reviewer uploads a CSV/XLSX of old test cases (drag-drop, same pattern as Screen 1's document upload — accepts .csv/.xlsx, rejects other types with the same inline error style), previews the parsed rows against the expected column mapping (Test Case ID, Title, Preconditions, Steps, Expected Result, Module, Priority — §2), confirms import, and sees a summary (N imported, M skipped — missing ID, duplicate ID, etc.). `csv_test_case_loader.py` parses the file (Sprint 1) and `test_cases_store.py` upserts into the `old_test_cases` Chroma collection that both retrieval (§5 step 4) and the style/pattern library draw on. The same screen supports browsing/searching what's already imported, filterable by module — and the distinct `module` values already present here double as the answer to the §7 module-list open decision, so `GET /modules` needs no separate config source.

---

## 6. Sprint Plan (2-week sprints, adjust pace as needed)

### Sprint 0 — Setup (pre-work, ~2-3 days)
- Repo scaffolding, folder structure, `.env`, `requirements.txt`
- `pip install chromadb`, verify a local persistent client initializes and writes to `chroma_db/`
- `llm_client.py`: build the Groq/Claude provider abstraction; test a "hello world" call through each provider you have a key for
- Jira API key wired into `config.py` and tested with a "hello world" call

### Sprint 1 — Ingestion + Old Test Case Store ✅ done
- `schemas.py`: `TestCase` Pydantic model (category/priority/status enums, grounded/manually_verified/edited flags for later sprints)
- `csv_test_case_loader.py`: parses CSV (via stdlib `csv`) and XLSX (via `openpyxl`, no `pandas` dependency) into `TestCase`, configurable column mapping (default: Test Case ID, Title, Preconditions, Steps, Expected Result, Module, Priority)
- `embedder.py`: thin wrapper around Chroma's default local embedding function (ONNX MiniLM-L6-v2, CPU, no API key)
- `chroma_client.py` + `test_cases_store.py`: create `old_test_cases` collection, `upsert()`/`query_similar()`/`count()`
- `scripts/bulk_import_old_test_cases.py` + `scripts/query_test_case_store.py`, backed by a 15-row sample fixture (`data/sample/old_test_cases_sample.csv`) spanning Auth/Search/Payments/Profile modules
- **Deliverable:** verified — importing the sample and querying (e.g. "user enters wrong password too many times", "apply a discount code during checkout") returns the correct top matches, and module-scoped queries filter correctly
- This is also the backend for Screen 5 (Test Case Library)'s import action, built out in Sprint 6

### Sprint 2 — Design Doc + Jira Ingestion ✅ done, fully live-verified
- `jira_client.py`: `get_issue_content()` flattens a fetched issue into summary/description/comments; `adf_to_text()` converts Jira Cloud's Atlassian Document Format into plain text; `extract_acceptance_criteria()` best-effort pulls an AC section from the description (a dedicated AC custom field varies per Jira instance and can't be assumed generically)
- `doc_parser.py`: `parse_pdf()` (one section per page, via `pdfplumber`) and `parse_docx()` (one section per Heading-styled paragraph, via `python-docx`) — `unstructured` deferred, see §3
- `chunker.py`: splits sections into ~1000-char chunks on paragraph boundaries with overlap, scoped to their source heading/page
- `design_docs_store.py`: `design_docs` Chroma collection, `upsert()`/`query_similar()` filterable by `source_type` (doc/jira) and `source_id`
- `scripts/ingest_sample_docs.py` + `scripts/query_design_docs.py`, backed by two generated sample docs (`data/sample/payments_refund_design_doc.docx`, `search_filtering_design_doc.pdf`) and a synthetic Jira ADF payload (no live Jira credentials configured yet — this exercises `adf_to_text()` without a real API call)
- **Deliverable:** verified — queries like "how long is the refund window" and "what happens when a search has no matches" return the correct sections from the right doc, and `source_type=jira` filtering isolates the synthetic ticket correctly
- **Live-verified:** Groq + Jira credentials added to `.env`; `get_issue_content()` tested against a real ticket (SCRUM-8 in the connected Jira instance) — ADF parsing correctly flattened preconditions/steps/expected-result and pulled the comment thread. Also discovered Jira Cloud's old `GET /rest/api/3/search` is deprecated (410 Gone) in favor of `POST /rest/api/3/search/jql` — noted for whenever a future sprint adds issue search; `jira_client.py` itself only uses `/myself` and `/issue/{key}`, unaffected.

### Sprint 3 — Retrieval + Decomposition ✅ done, fully live-verified
- `schemas.py`: added `Requirement` and `Condition` models
- `retriever.py`: `retrieve_context()` — the two lookups plan.md §5 step 4 calls for (design_docs context + old_test_cases style examples), each with hard module-scoped payload filtering, plus a lightweight lexical-overlap rerank on top of vector similarity (no external rerank API needed to start, see §2)
- Extended `chunker.Chunk` and `design_docs_store` with a `module` field so design-doc chunks can be scoped the same way old test cases already are; re-ingested the Sprint 2 sample docs with module tags (Payments/Search/Auth)
- `decomposer.py`: split into `build_user_prompt()` + `parse_conditions()` (pure/deterministic, unit-testable without a live API) and `decompose()` (the actual LLM call via `llm_client.py`)
- `scripts/query_retriever.py`, `scripts/decompose_demo.py`
- **Deliverable:** verified — `decompose_demo.py` decomposes a sample refund requirement into 6 atomic conditions (each correctly tagged with its AC), and for each condition `retriever.py` pulls back the matching design-doc section plus relevant style examples
- **Live-verified:** with a real Groq key, `decompose_demo.py` decomposed the same requirement into 12 well-formed conditions (more granular than the dry-run's canned 6 — the real model split each AC line out individually), all valid JSON, correct `ac_ref`s, retrieval context spot-on for every condition.

### Sprint 4 — Generation + Coverage Audit ✅ done, fully live-verified
- `prompts.py`: `GENERATION_SYSTEM_PROMPT` with the fixed 7-category taxonomy (Positive, Negative, Boundary, Edge, Security, Integration, Data Validation) — matches `UX Screen/Screen2-ReviewQueue.dc.html`'s `CATEGORY_ORDER` exactly; a targeted variant scopes generation to specific categories for gap-filling; `AUDIT_SYSTEM_PROMPT` for the grounding pass
- `generator.py`: `parse_test_cases()` (pure/deterministic) + `generate_test_cases()`/`generate_test_cases_for_categories()` (the LLM calls) — every freshly generated case starts `grounded=False` until audited, so a skipped audit fails closed rather than reading as trusted
- `coverage_auditor.py`: `audit_grounding()` sets the real `grounded` flag per case via a second LLM pass; `find_gaps()` is pure/deterministic — which of the 7 categories have zero cases; `regenerate_gaps()` re-runs generation scoped to just the missing categories (tolerates a category staying empty if the model judges it genuinely doesn't apply)
- `scripts/generate_demo.py`
- **Deliverable:** verified — dry run generates 5 categorized cases for a sample condition, the audit pass correctly flags one as needing verification, gap detection correctly finds the 2 missing categories (Security, Integration), targeted regeneration fills Security, and Integration is honestly reported as still-missing rather than forced
- **Caught and fixed during verification:** `TestCase.category` is a `str, Enum` — f-string interpolation (`f"{tc.category}"`) renders `"Category.positive"` instead of `"Positive"` on this Python version. Fixed by using `.value` explicitly everywhere a category is displayed *or sent to the LLM* — the audit prompt build in particular would have silently sent the wrong text to a real model.
- **Live-verified:** with a real Groq key, `generate_demo.py` generated 7 categorized cases (all but Edge), the audit pass genuinely flagged 4 of them as needing verification (Boundary/Security/Integration/Data Validation cases the model itself judged as going beyond what the requirement text states — the audit is doing real work, not rubber-stamping), gap detection correctly found Edge missing, and targeted regeneration filled it with 2 cases — final set spans all 7 categories.

### Sprint 5 — Traceability + API (jobs, coverage, bulk actions) ✅ done, fully live-verified
- `schemas.py`: added `Run` (single source of truth per run — steps, conditions, test_cases, gaps, persisted `requirement_text` so later single-case regenerate doesn't need to re-fetch Jira/doc), `RunStep`/`RunStepStatus`, `CoverageGap`; `TestCase` gained `condition_id` (links a generated case back to its Condition — needed for RTM building)
- `pipeline.py`: `execute_run()` orchestrates ingest → decompose → (per condition) retrieve → generate → audit+gap-fill → aggregate run-level gaps, mutating an in-process `RUNS: dict[str, Run]` as it goes so status polling reflects live progress. Explicitly in-memory, not a database or task queue — run history is lost on restart, MVP tradeoff per §3/§7, revisit if real volume demands it
- `rtm_builder.py`: `build_rtm()` — pure/deterministic, conditions → linked test case IDs → covered (at least one **approved** linked case, matching the mockup's exact definition)
- `test_cases_store.py`: added `list_all()`/`get_by_id()` for plain browsing (Screen 5) alongside the existing similarity search
- FastAPI app (`api/main.py`) + 5 routers exactly matching the endpoints below; CORS enabled for the Vite dev origin
  - `POST /runs` (multipart — Jira ticket key or uploaded PDF/DOCX + optional module), `GET /runs`, `GET /runs/{id}`, `GET /runs/{id}/status`
  - `GET /modules`
  - `PATCH /test-cases/{id}` (edit fields or toggle `manually_verified`), `POST /test-cases/bulk-approve` (write-back into `old_test_cases`), `POST /test-cases/bulk-reject`, `POST /test-cases/{id}/regenerate`
  - `POST /library/import`, `GET /library` (search or plain browse), `GET /library/{id}`
  - `GET /runs/{id}/coverage`, `POST /runs/{id}/gaps/{category}/acknowledge`
- **Deliverable — live-verified end to end:** started `uvicorn api.main:app` and drove the real API with `curl`: imported the Sprint 1 sample library, ran a full generation against a real Jira ticket (SCRUM-8) — polled `/status` and watched it move through all 4 steps live, landing on 7 conditions × 68 test cases across all 7 categories with 0 run-level gaps; bulk-approved grounded cases (write-back into the library confirmed via search), confirmed the grounded/manually-verified approval gate blocks an ungrounded case until verified, and `GET /coverage` showed the RTM correctly flipping `covered` to `true` only for conditions with an approved case.
- **Bugs caught and fixed during this verification:**
  1. `generator.parse_test_cases()` IDed cases as `{condition_id}::G{loop_index}`, restarting from 1 every call — fine in Sprint 4's demo where batches were never merged, but a real collision once `pipeline.py` merges initial-generation + gap-fill-regeneration into one `run.test_cases` list. Switched to a UUID suffix.
  2. Generated `TestCase`s never carried the run's `module`, so approved cases wrote back into the library with `module=""` — invisible to future module-scoped retrieval. Threaded `module` through `generate_test_cases()`/`generate_test_cases_for_categories()`/`regenerate_gaps()`/`parse_test_cases()` and all their call sites; verified live that both the parse path and the real LLM path now set it correctly.

### Sprint 6 — Frontend Foundation (Generate + Test Case Library screens) ✅ done, verified in a real browser
- Scaffolded `frontend/` (React 19 + Vite 8 + TypeScript, React Router) — see `frontend/README.md`'s generated defaults; deleted the default marketing-page template (`App.css`, hero/react/vite assets) entirely
- `styles/tokens.css`: every OKLCH value, radius, and shadow across all 4 mockups extracted into CSS custom properties (surfaces, borders, text scale, brand, success/danger/warning, the 7 category-dot colors, priority-pill colors) plus shared global utility classes (`.page`, `.card`, `.pageEyebrow/pageTitle/pageMeta`, `.textInput`, `.label`) so per-screen CSS modules don't redeclare the same card/header pattern
- `api/client.ts`: typed fetch wrappers + TypeScript interfaces mirroring `schemas.py` exactly (`TestCase`, `Run`, `RunStep`, `CoverageGap`, etc.) — covers the runs/library/modules endpoints this sprint's two screens need; test-cases/coverage/export calls land with their screens in Sprints 7-8
- Shared components: `Sidebar` (7-item nav reconciling Screen 1 vs. Screens 2-4's inconsistent lists, icons picked per-item from whichever mockup had the better fit — e.g. Export gets a proper download icon instead of the mockup's reused clock icon), `Button`, `Pill`, `Modal` (first real consumer is Sprint 8's Jira-upload confirmation), `Spinner`, `ComingSoon` (placeholder for the 5 not-yet-built routes, each labeled with the sprint that builds it)
- Screen 1 (Generate): both tabs (Jira ticket / upload doc), client-side ticket-key format validation, file-type validation, module dropdown sourced from `GET /modules`, submits to `POST /runs`, polls `GET /runs/{id}/status` every 2s, renders the live 4-step tracker, and a results/failure state — all from real backend state, not mocked
- Screen 5 (Test Case Library): upload → `POST /library/import` → result banner; debounced search + module filter → `GET /library`, falling back to plain browse when the search box is empty
- **Deliverable — verified in an actual headless Chromium browser** (no `chromium-cli` on this Windows box, so used Playwright directly per the `run` skill's fallback guidance), both dev servers running together: drove the Generate screen through all its input states (empty/invalid-key/valid), submitted a real run against Jira ticket SCRUM-8, watched live step-progress polling render through to "Generated 57 test cases across 6 conditions — All 7 categories covered," then navigated to the Library screen and confirmed both the full browse list and a relevance-ranked search (query "wrong password too many times" correctly top-matched TC-104 "Account lockout after repeated failed logins") render correctly. Zero browser console errors throughout. Screenshots taken at each step.
- **Bug caught and fixed during this verification:** `pipeline.py` only marked the first step `in_progress` *after* Jira/doc ingestion completed, so for the first several seconds of every run the UI showed all 4 steps as "Waiting" with no indication anything was happening (ingestion has no dedicated step of its own, per plan.md §5 step 2). Reordered so "Decomposing requirement" flips to `in_progress` before ingestion starts instead of after — this would not have been obvious from reading the code, only from watching real wall-clock screenshots during a live run.
- **Deliverable met:** a reviewer can kick off a real run from the UI and watch it progress, and can import/browse the old test case library

### Sprint 7 — Review Queue + Coverage Matrix ✅ done, verified in a real browser
- Backend additions: `pipeline.fill_gap_category()` + `POST /runs/{id}/gaps/{category}/generate` — Screen 2's "Generate manually" needed an endpoint that didn't exist yet (Sprint 5's `regenerate_gaps()` is per-condition; a run-level gap has no single condition to scope to, so this retries targeted generation against every condition in the run). `PATCH /test-cases/{id}` extended to accept `status: "unreviewed"` only — the "Undo reject" action, kept deliberately narrow so `bulk_approve`'s grounding-gate check stays the *only* path that can set `status=approved`, not duplicated per call site. `bulk-approve`/`bulk-reject` now return full `TestCase` objects instead of bare ids, so the frontend can update state without a refetch.
- `frontend/src/lib/lastRun.ts`: Review and Coverage Matrix are per-run screens, but Run History (the natural way to pick a run) doesn't exist until Sprint 8 — so the sidebar links to `/review`/`/coverage` fall back to the most recently completed run via `localStorage`, while `Generate.tsx`'s "Review generated test cases" CTA links to the specific run directly (`/review/:runId`)
- Screen 2 (Review Queue): 7 category sections (counts, "N unreviewed" / "all reviewed"), inline-editable case detail (title/preconditions/steps incl. add/remove/expected result, saved on blur) with an "Edited" badge, bulk select/approve/reject, the grounded/needs-verification approval gate (blocks approve until either grounded or manually verified, enforced server-side in `bulk_approve` — not just hidden client-side), single-case regenerate, undo-reject, and gap sections wired to the two new "Generate manually"/"Mark reviewed" actions
- Screen 3 (Coverage Matrix): RTM computed client-side from the already-fetched `Run` (mirrors `rtm_builder.build_rtm()` — avoids a second request since the linked-case status is needed for pill coloring anyway), covered/uncovered banner, search + coverage-status filter, "Jump to gaps" jumps straight to the uncovered filter. Dropped the mockup's module filter — a single run has one module, so filtering by it within one run's matrix isn't meaningful; module filtering matters at the Test Case Library level instead, where it's already built.
- Approve write-back into `old_test_cases` (built in Sprint 5) verified live end-to-end for the first time
- **Deliverable — verified in a real browser**, not just built: ran a fresh generation against SCRUM-8 (54 cases, 6 conditions, 0 run-level gaps), then in Review: approved a grounded case individually, inline-edited a second case's title and confirmed the "Edited" badge appeared and persisted, bulk-selected and approved two more (stats correctly read "3 Approved / 53 Unreviewed"). Then on Coverage Matrix for the same run: exactly 3 of 6 conditions showed "Covered" and 3 "Not covered," matching which conditions actually had an approved case — and the linked-test-case pills were color-coded correctly. Zero console errors throughout.
- **Two real bugs caught and fixed while building, before they ever reached the browser:** (1) the Approve/Reject/Undo buttons in my first draft only mutated local React state and never called the backend at all — Approve in particular sent an empty PATCH body that silently did nothing; caught by reading my own draft against what the buttons were supposed to do, not by the type checker, since it was type-correct nonsense. (2) `regenerateTestCase()` returns cases with entirely new IDs (the old case is deleted server-side), but my initial local-state merge only handled "update matching ids, append new ones" — so a regenerated case would leave the stale original sitting in the list alongside the replacement. Fixed with a dedicated `replaceCaseLocal()` path instead of overloading the generic save callback.

### Sprint 8 — Export + Run History + Settings ✅ done, verified in a real browser (real Jira issues created)
- **§7 open decision resolved by inspecting the live instance, not guessing:** queried `/rest/api/3/project/SCRUM` and found a purpose-built **"Test Case"** issue type already configured (alongside Task/Bug/Story/Epic/Subtask) — so `jira_uploader.py` targets that directly, no Xray/plugin fallback needed. Checked `/createmeta` too: only `summary`/`project`/`issuetype`/`reporter` are required.
- `TestCase.jira_key` added to schema (tracks upload state so re-upload skips already-uploaded cases); `JIRA_PROJECT_KEY` config added as the fallback target project for doc-sourced runs (a Jira-ticket-sourced run uploads into that ticket's own project instead, derived from the ticket key)
- `excel_exporter.py`: two-sheet workbook (Test Cases + RTM) via `openpyxl`, approved cases only
- `jira_uploader.py`: creates a "Test Case" issue per approved case (ADF-formatted description: preconditions/steps/expected result), labeled `generated-test-case`, linked back to the source ticket via a "Relates" issue link (best-effort — a failed link doesn't fail the upload, the issue already exists by that point)
- `api/routers/export.py`: `GET /export/{id}/status` (gating info + the mockup's exact blocked-reason wording), `POST /export/excel`, `POST /export/jira` (optional `test_case_ids` — omitted means "every approved case not yet uploaded," which is what powers "Retry failed only"). Gating is enforced server-side, not just hidden client-side: blocked if 0 approved, or any *unreviewed* case still needs verification, or any gap is unacknowledged — note rejected cases don't count against "needs verification," since rejecting is itself a resolution.
- `api/routers/settings.py`: `GET /config` — read-only, non-secret visibility (provider/model, whether keys are configured as booleans, Jira base URL/project) for the Settings screen; never returns actual keys/tokens
- Screen 4 (Export): gated buttons with the blocked-reason banner, confirm modal before Jira upload, progress spinner, results list with per-item Jira links or failure reasons, "Retry failed only" re-calls upload scoped to just the failed ids
- Run History screen: lists all runs (status pill, case/approved counts), click reopens into Review (or back into Generate if still in-progress)
- Settings screen: LLM provider/model + configured-or-not, Jira base URL/fallback project/credentials-configured, and the module list currently in use — all read-only per plan.md's "minimal for MVP" framing (made fully editable post-Sprint-9, see below)
- **Deliverable — verified in a real browser, with real side effects, not a mock:** fully triaged a fresh 54-case run (bulk-rejected everything, then selectively un-rejected and approved 2), confirmed the Export screen's blocked banner rendered the exact "Export is disabled: ..." reasons before triage and cleared after, downloaded a real .xlsx (verified via `openpyxl`: correct 2-sheet structure, correct data, the "—" placeholder is genuinely U+2014 not corruption — a `�` in my own terminal output was just a Windows console codepage artifact, not a data bug), and confirmed via the modal → progress → results flow. **Cross-checked directly against the Jira API** (not just the app's own success message): the two issues it created are real, correctly typed as "Test Case," carry the `generated-test-case` label, and are linked "relates to" SCRUM-8. Run History and Settings both verified live too. Zero console errors throughout.
- **One real bug caught by the browser, not the type checker:** `/export/:runId` was never added as a route in `App.tsx` (only the paramless `/export`existed) — Playwright's wait for the Export page timed out on a blank render. `tsc` had nothing to say about it since a missing route isn't a type error; only actually navigating there in a browser surfaced it. Same class of gap as Sprint 7's two bugs — this project's real defects have consistently been in wiring and state transitions, not syntax.

### Sprint 9 — Hardening + Polish ✅ done
- **Retries:** `llm_client.py` and `jira_client.py`/`jira_uploader.py` now retry transient failures (rate limits, timeouts, connection errors, 5xx) up to 3 attempts with exponential backoff via `tenacity` — already a transitive dependency (via `chromadb`), pinned explicitly now that it's imported directly. Auth/bad-request errors are deliberately not retried; classification is by exception-class-name matching for the LLM SDKs (avoids eagerly importing either just for exception types) and by status code for Jira's `requests`-based calls.
- **Error handling:** `pipeline.execute_run()` no longer lets one condition's generation/audit failure abort the entire run — each condition is isolated in its own try/except, degrading to zero cases (a natural, reviewable gap) on failure rather than discarding every other condition's already-successful work. Ingestion/decomposition failures still fail the whole run, correctly — nothing downstream is possible without conditions.
- **Logging:** `logging.basicConfig` configured in `api/main.py`; key pipeline/export events logged at INFO, retries and per-condition failures at WARNING/ERROR; noisy third-party HTTP loggers (httpx/httpcore/urllib3) turned down to WARNING so they don't drown out the app's own log lines.
- **Tests — 75 pytest tests across 9 files, all passing, ~2.7s, fully hermetic** (no live LLM/Jira/Chroma calls — every test exercises pure/deterministic logic or mocks the network boundary): `test_chunker.py`, `test_decomposer.py`, `test_generator.py`, `test_coverage_auditor.py`, `test_rtm_builder.py`, `test_retriever.py` (reranking logic, with `monkeypatch`-mocked Chroma queries), `test_excel_exporter.py`, `test_jira_client.py` (ADF parsing, retry classification — this had zero test coverage since Sprint 2), `test_jira_uploader.py` (ADF description building, error extraction, mocked upload flow). Added `pytest.ini` to disable class-based test collection — pytest's default `Test*` pattern kept mis-treating the `TestCase` Pydantic model as a test class whenever a test file imported it.
- **README.md** rewritten with full backend+frontend setup, how to run both dev servers, a testing section explaining what the pytest suite does and doesn't cover (no live calls — use the Sprint 0 sanity scripts and the actual UI for that), and a summary of this sprint's hardening changes.
- **Deliverable met:** `python -m pytest` (75 passed), `npx tsc -b` (clean), `npm run build` (clean), and live smoke tests confirming the retry-decorated LLM and Jira calls still work unchanged for the success path.

### Post-Sprint-9 fixes (real usage surfaced these — not caught by the test suite or prior verification)
- **`doc_parser.py` crash on real user-uploaded DOCX files:** `para.style.name` assumed `para.style` is always resolvable. `python-docx` returns `None` when a paragraph references a style ID missing from the document's style catalog — common in DOCX files from Google Docs or non-Word tools, not just corrupted ones. Every prior test used a fixture generated by `python-docx` itself, which never hit this. Fixed to treat an unresolvable style as body text; added `tests/test_doc_parser.py` as a regression guard (77 tests total now).
- **Bulk-approve silently swallowed blocked cases:** `handleBulkApprove` in `Review.tsx` called the API and discarded the `blocked` list entirely. Selecting a batch that included ungrounded/unverified cases would approve only the eligible ones with **zero feedback** — indistinguishable from "the button doesn't work" from the user's side, which is exactly how it was reported. Reproduced live (selected 4, got 1 approved + 3 silently blocked), then fixed: the toolbar now shows a warning banner naming how many were blocked and what to do next. The individual per-case Approve/Reject/Undo buttons were already correct — this was specifically the bulk-toolbar path.
- **Export gate relaxed — deliberate behavior change, not a bug:** the original gate (matching the mockup's own demo text verbatim) blocked export until the *entire* run was triaged — every case resolved, every gap acknowledged. That's fine for a handful of cases but unworkable at real scale (one run had 304): a reviewer couldn't ship the 6 cases already approved until the other 298 were individually resolved. Changed so export blocks only on 0 approved cases; pending verification and unacknowledged gaps now show as a non-blocking note ("N cases still need manual verification. Only the M approved case(s) will be exported.") instead of disabling the buttons. Confirmed with the user before changing, since it reverses documented, intentional mockup behavior. Added `tests/test_export_gating.py` (9 tests) — this gating logic had no test coverage before (86 tests total now).
- **Settings screen made editable — was read-only since Sprint 8, per explicit user request, plan agreed with the user before building:**
  - `config.py`: `update(**kwargs)` writes through to both this module's own globals (every other module reads config via `config.ATTRIBUTE`, never `from config import X`, so the mutation takes effect immediately, no restart needed) and `.env` on disk via `python-dotenv`'s `set_key()`, so it survives a restart too. Blank/omitted values are skipped, not written — the contract every field in the new forms below relies on: "leave blank to keep the existing value."
  - `llm_client.test_connection(provider, api_key, model)`: an isolated, standalone test call using *candidate* (typed-but-not-saved) credentials — deliberately not routed through the normal `LLMClient`, which only ever reads from saved global config. Same pattern in `api/routers/settings.py`'s `POST /config/jira/test` (a direct `requests.get(.../myself)` call), so "Test connection" always checks what's currently typed in the form, not what's already saved.
  - `api/routers/settings.py` extended: `PATCH /config/llm`, `PATCH /config/jira`, `POST /config/llm/test`, `POST /config/jira/test`. `GET /config` still never echoes back actual secret values, only `*_configured` booleans — that contract is unchanged and the new PATCH/test endpoints accept secrets write-only, same as before.
  - Module management added end-to-end: `src/modules_store.py` (a small JSON-persisted manual list at `data/modules.json`, for modules a user wants available before any test case actually uses them) plus `test_cases_store.rename_module()` (bulk metadata-only update via Chroma's `.update()`, no re-embedding). `GET /modules` now returns the union of derived (data-backed) and manual names; `POST/DELETE/PATCH /modules/{name}` give the CRUD the user asked for — delete is blocked with a 409 (rename instead) if a module is still in use by real test cases, so cascading rename is the only way to consolidate live data.
  - `frontend/src/components/ImportTestCasesCard.tsx` extracted from the Test Case Library screen's inline upload widget so Settings could reuse the exact same "upload old test cases" flow the user asked to have available from both places.
  - `Settings.tsx` rebuilt with editable forms (masked, always-blank-on-load password inputs for API keys/tokens — never pre-filled, matching the "keys are write-only" design), a "Test connection" button per LLM provider and for Jira, Save buttons, and full module add/rename/delete UI.
  - Added `tests/test_config.py` (7 tests, using an isolated tmp-path `.env` fixture so tests never touch the real credentials file) and `tests/test_modules_store.py` (11 tests) — 104 tests total now.
  - **Deliverable — verified in a real browser, with a real LLM call:** restarted the backend to pick up the new routes, then drove the live Settings screen with Playwright — added, renamed, and deleted a module (each change reflected immediately, no leftover test data afterward), triggered "Test connection" with a deliberately invalid Groq key (500ish text) and got back the SDK's real `401 Invalid API Key` error, then re-ran with the actual saved Groq key typed into the field and got back a genuine `Connected — model replied "OK"` — a real round trip to Groq's API, not a stubbed response. Jira's "Test connection" was also exercised against invalid credentials without crashing the page. Zero browser console errors throughout, and the real `.env` file was left untouched (only the in-browser candidate values were ever tested; Save was never clicked with test data).
- **Test Case Library regrouped by session, and full case detail exposed — per explicit user request, plan agreed with the user (including a scope-clarifying question about approved-only vs. full generated set) before building:**
  - `TestCase` schema gained `session_id`/`session_label`/`session_created_at`. Stamped in two places: `POST /library/import` mints one `session_id` per upload (label = filename), and `bulk_approve` stamps `run.id`/`run.source_id`/`run.created_at` onto every case approved out of that run — so every entry that ever enters `old_test_cases` is traceable to exactly the upload or the run it came from, confirming with the user's own framing: "if I run a thousand sessions, I should be able to find which session a test case came from."
  - Scope resolved with the user: a generated session shows only that run's *approved* cases, matching how the library has always worked (unreviewed/rejected cases never entered it) — avoids a much bigger change that would've required persisting Run History past the current in-memory/restart-loses-it design (§3).
  - `test_cases_store.py`: `list_sessions()` groups every entry by `session_id` (Chroma has no native GROUP BY, so this fetches and aggregates in Python, same approach as `modules.py`'s `_derived_modules()`); pre-existing entries with no session data land in a per-source "Unsorted (before session tracking)" bucket rather than disappearing. `_where()` extended so `GET /library` can filter by `session_id` the same way it already filters by `module`.
  - **Full test case detail, without a schema migration:** every library entry's embedding `document` already contained the full formatted Preconditions/Steps/Expected Result text (needed for retrieval) but it was never parsed back out for display. Added `_parse_document()` reversing the existing `_document()` format; `GET /library`/`GET /library/{id}` now return `preconditions`/`steps`/`expected_result` alongside the existing metadata, computed on read — works uniformly for every entry, old or new, no backfill needed for this part.
  - **Real bug caught during live verification, fixed same session:** Chroma's equality `where` filter only matches documents where the metadata key is *present* — entries written before `session_id` existed have no such key at all, not an empty one, so `{"session_id": ""}` silently matched zero of them. `curl`ing the filtered endpoint directly showed `[]` despite `list_sessions()` correctly counting 18/22 legacy entries (its Python-side aggregation tolerates a missing key; the Chroma-side filter didn't). Fixed with a self-healing backfill: `list_sessions()` now stamps `session_id`/`session_label`/`session_created_at` = `""` onto any entry missing the key the first time it's read, so the equality filter works from then on. Added dedicated regression tests for both the missing-key and key-already-present cases.
  - `frontend/src/pages/TestCaseLibrary.tsx` rebuilt: two collapsible sections ("Uploaded Test Cases" / "Generated Test Cases"), each an accordion of session groups (label, case count, date) that lazy-load their cases on first expand; each case row expands further to show the complete case (preconditions, numbered steps, expected result). Search/module filter still work across everything, now tagging each result with its originating session label so traceability holds in both grouped and filtered views.
  - Added `tests/test_test_cases_store.py` (13 tests: document round-trip parsing, `_where` filter construction including the unsorted pseudo-id split, session grouping/counting, and the backfill fix) — 117 tests total now.
  - **Deliverable — verified in a real browser, including a real end-to-end generation:** uploaded a fresh CSV and watched it appear as its own new "Uploaded" session immediately; expanded a legacy "Unsorted" case and confirmed full preconditions/steps/expected-result rendered correctly; ran a real generation against SCRUM-8, manually verified and approved 2 cases via the live API, and confirmed a new "SCRUM-8" session appeared under "Generated Test Cases" with exactly those 2 cases grouped inside — the core scenario the user asked for. Searched across everything and confirmed session tags appeared correctly on matching rows. Zero browser console errors throughout.
- **Test case field pattern standardized (Test Case ID / Test Scenario / Description / Pre-conditions / Steps / Expected Results / Priority) + a real data-loss bug in XLSX import fixed — reported by the user with a screenshot of their own uploaded file showing blank Preconditions/Steps:**
  - **Root-caused by reading the user's actual uploaded file directly** (still sitting in `data/raw/`, since nothing there gets cleaned up — see the open question below) rather than guessing: their real headers were `Test Scenario`, `Test Case Description`, `Pre-conditions`, `Test Steps` — none of which matched the loader's old exact-string `DEFAULT_COLUMN_MAP` (`Title`, `Preconditions`, `Steps`), so those columns were silently dropped to blank. `Test Case Description` in particular had nowhere to go at all — no such field existed on `TestCase` yet.
  - `TestCase` gained a `description: str = ""` field (the test objective — distinct from the title/scenario).
  - `csv_test_case_loader.py` rewritten around `FIELD_ALIASES` + `_resolve_column_map()`: each schema field now accepts several real-world header spellings ("Test Scenario"/"Title"/"Scenario" all map to `title`; "Pre-conditions"/"Preconditions"/"Prerequisites" all map to `preconditions`; etc.), matched case/whitespace/hyphen-insensitively — so the exact class of bug the user hit (a header that means the same thing but isn't spelled identically) can't silently drop data again. Also fixed `_split_steps()` to strip manual numbering/bullets ("1. ", "2)", "- ") the source file already had, so re-numbering in the UI doesn't double up on top of it — the user's real file had pre-numbered steps that would otherwise have rendered "1. 1. Navigate to login page".
  - `test_cases_store.py`'s `_document()`/`_parse_document()` extended to include Description, with the parsing regex treating the "Description:" line as optional — so entries written before this field existed (every pre-existing library entry) still parse correctly with `description=""` rather than breaking.
  - Generation prompt (`prompts.py`) and `generator.py`'s `parse_test_cases()` updated so LLM-generated cases produce a real `description` too, not just imported ones — verified live against a real Groq call, not just the parsing logic.
  - `excel_exporter.py` column headers renamed to match the pattern exactly (`Test Scenario`, new `Description` column, `Pre-conditions`, `Expected Results`), with `tests/test_excel_exporter.py`'s column-index assertions updated for the shift.
  - Frontend: `Review.tsx`'s case editor and `TestCaseLibrary.tsx`'s case detail view both relabeled to the same pattern and gained an editable/visible Description field; `ImportTestCasesCard.tsx`'s "columns expected" hint text updated to state the canonical names while noting common variants are auto-matched. `Module` stays as its own field beyond the user's 7-field list — it's load-bearing for filtering/Settings/session-grouping elsewhere in the app, dropping it would have been a regression the user didn't actually ask for.
  - Added `tests/test_csv_test_case_loader.py` (13 tests covering exact-match, real-world-variant, and case/hyphen-insensitive header resolution, step-prefix stripping, and full-row parsing for both CSV and XLSX) plus round-trip/backward-compat tests for the Description line in `test_cases_store.py` and `test_generator.py` — 129 tests total now.
  - **The user's already-broken data was fixed, not just prevented going forward:** re-POSTed their original `data/raw/...Login_Function_Test_Cases.xlsx` through the fixed `/library/import` after deploying the fix. Chroma's `upsert()` is idempotent by test case ID, so this overwrote the two broken `TC_LOGIN_001`/`TC_LOGIN_002` entries in place with correctly-parsed data — confirmed via direct `GET /library/{id}`, and the stale "Unsorted" session pointer for those two ids disappeared on its own (session grouping is recomputed fresh from current metadata every read, not cached).
  - **Deliverable — verified in a real browser against both data paths:** re-uploaded the corrected file and confirmed the Library screen's expanded case detail shows Title/Description/Pre-conditions/Steps/Expected Results all populated correctly, steps not double-numbered; ran a fresh real generation against SCRUM-8 and confirmed the Review screen's case editor shows the same Test Scenario/Description/Pre-conditions/Expected Results labels with genuine LLM-produced description text. Zero console errors in either check.
- **Generation scope control (Focus/Scope box) — for design docs reused across releases with only the new/changed requirement marked (commonly in red font), design discussed and refined with the user across several turns before building:**
  - **Design evolution, not a straight build**: the user's first framing was pure automatic red-text detection with inline markers embedded in the requirement text (`<<CHANGED>>...<<END_CHANGED>>`). Talking through it surfaced two real gaps: (1) not every doc uses a red-text convention — sometimes it's a plain full requirement doc with nothing marked, and (2) automatic, invisible filtering is fragile (inconsistent team conventions, no visibility into what got included/excluded) and doesn't help at all for Jira-ticket-sourced runs. The user's own proposed fix — a manual, editable scope field the user controls — turned out to be the more robust *general* mechanism; automatic red-detection was demoted to an optional pre-fill/suggestion for it rather than a silent filter. This is the actual shipped design.
  - `Run.scope: str | None` added to the schema — an optional free-text instruction, valid for *either* source type (Jira ticket or doc upload), not tied to document formatting at all.
  - `decomposer.build_user_prompt()`/`decompose()` gained an optional `scope` param: when set, prepends "Focus ONLY on generating conditions related to this scope: {scope}... use the rest of the requirement purely as supporting context" ahead of the full, unmarked requirement text. Empty scope = byte-identical behavior to before this feature existed.
  - `doc_parser.detect_red_text()`: scans a DOCX's paragraph runs for red-ish font color (`_is_reddish()` — a tolerance heuristic, not exact-hex match, since teams pick different reds: pure `FF0000`, Word's own default "Dark Red" `C00000`, etc. — red-dominant with green/blue both low, explicitly excluding orange/pink false positives) and returns the detected text joined by paragraph. Explicit RGB only — a run colored via a Word theme reference with no literal RGB value won't be caught, a known and documented limitation. PDF is out of scope for this feature — pdfplumber (used for PDF parsing here) doesn't expose per-character color through the API this app uses, and redline-by-color is overwhelmingly a Word convention anyway.
  - New `POST /documents/detect-changes` endpoint (own router, `api/routers/documents.py`) — pure scan, no Run created, temp file deleted immediately after scanning (unlike `runs.py`'s doc upload, which needs its temp file to survive into the background task).
  - Generate screen: new optional "Focus / Scope" textarea, under Module, for both tabs. Selecting a `.docx` file fires `detectChangedText()` in the background; if red text is found *and the user hasn't already typed their own scope*, it pre-fills the box with a "Detected from red text — edit or clear as needed" note — always visible and editable, never applied silently. `run.scope` is echoed back on both the Generate progress screen and the Review screen header for traceability.
  - Added `tests/test_doc_parser.py` (`_is_reddish` tolerance cases, `detect_red_text` extraction/no-match/non-docx cases) and `tests/test_decomposer.py` (scope-present vs. scope-absent prompt assertions) — 142 tests total now.
  - **Deliverable — verified live with a real LLM call, not just the parsing logic:** built a DOCX with three requirements — two plain/unmarked (login, password reset) and one red-marked (account lockout after 5 failed attempts) — uploaded it on the Generate screen, confirmed the Scope box auto-filled with exactly the red sentence, submitted the run, and confirmed via the actual API response that **all 7 generated conditions were about the lockout behavior only** — zero conditions about the unrelated plain-text login/reset content, despite the LLM having the full document as context. Confirms the design does what it was meant to: narrow generation to what's in scope while still using surrounding text to understand it, not literally exclude everything else from the model's view. Zero console errors.
- **Test Case ID scheme replaced (random UUID-suffix → `TC_{MODULE}_###`, sequential and user-editable) — per explicit user request, refined across several turns (a manual prefix field was simplified down to auto-deriving from the existing Module dropdown once the user pointed out modules vary — Login vs. Registration vs. Card vs. Checkout — and a fixed "not defined" fallback was added for when no module is set):**
  - Every id-minting call now funnels through `test_cases_store.next_sequence_ids(module, count, extra_existing_ids)` — module name normalized (`"Payment Gateway"` → `PAYMENT_GATEWAY`, blank/`None` → `NOT_DEFINED`), continuing from the highest number already used with that exact `TC_{MODULE}_` prefix in the persisted library. `generator.parse_test_cases()` no longer mints a `uuid4()`-suffixed id per case; it now reserves a contiguous block of sequential numbers for however many cases survive category/title validation in one LLM response.
  - **Cross-run collision found and fixed during live verification, before it could cause silent data loss:** the persisted library only gains entries on *approval*, so a first live test proved that two separate runs generating for the same module — neither approved yet — handed out the *same* `TC_AUTH_005` to two different cases, because numbering only checked the library plus the current run's own in-flight ids, not other still-unapproved runs sitting in memory. Since `bulk_approve` writes via Chroma `upsert()` (same id = silent overwrite, no error), approving both would have quietly destroyed one of them. Fixed by seeding the "ids already in play" set from **every** run currently in `RUNS`, not just the one being generated (`execute_run`, `fill_gap_category`, and `regenerate_test_case` all updated) — confirmed by re-reading the reproduction against the fix's logic; a full live end-to-end re-run of this exact scenario couldn't be completed the same session because Groq's *daily* token quota (not a short rate limit — a hard 100k-tokens/day cap) was exhausted by the volume of live testing done today. The fix is covered directly by unit tests exercising `next_sequence_ids`'s `extra_existing_ids` parameter, the exact mechanism involved.
  - **Test Case ID made editable** in the Review screen's case editor (same field-level edit pattern as Title/Description/etc.), with server-side collision validation extracted into a pure `validate_id_change()` function (mirrors `export.py`'s `_export_status` pattern for testability): blank → 400, collides with another case in the same run or a *different* case already in the library → 409 with a clear message, re-saving a case's own existing id or approving into its own prior library slot → allowed. Renaming updates the frontend's selection/expansion state (which were tracking the old id) via a dedicated `replaceCaseIdLocal`, the same category of fix as Sprint 7's regenerate-merge bug.
  - Added `tests/test_test_cases_store.py` id-sequencing tests (normalization, prefix building, continuation from existing numbers, cross-prefix isolation, `extra_existing_ids` handling), rewrote `tests/test_generator.py` to stub the library lookup for hermetic/deterministic ids, and added `tests/test_test_cases_router.py` for `validate_id_change` — 160 tests total now.
  - **Deliverable — verified live with real LLM calls where the quota allowed:** a real generation against SCRUM-8/module "Auth" produced 58 cases as `TC_AUTH_001`–`TC_AUTH_058`, all unique; approving two of them and confirming the library reflected exactly those. In the Review screen, renamed a live-generated case's id, confirmed the row updated everywhere immediately, then attempted to rename it to collide with a sibling case in the same run and confirmed a clean 409 rejection with the field reverting to its last valid value — no corrupted state. Zero console errors.
- **"Regenerate this one" crashed with an unexplained 500 — reported by the user from the browser network tab.** Root cause (found in the backend's own log, not guessed): Groq's *daily* token quota was genuinely exhausted from the same session's heavy live-testing volume — a real external failure, not a logic bug. But it exposed a real gap regardless: `regenerate_test_case` (and, on inspection, `fill_gap_category`'s "Generate manually" gap action) had **no error handling at all** around their LLM calls — unlike `execute_run`'s main loop, which has isolated per-condition try/except specifically for this (Sprint 9 hardening). Any transient failure there — quota, timeout, network blip — surfaced as an opaque, unexplained crash.
  - `regenerate_test_case`: wrapped in try/except, now raises a clean `502` with the real underlying reason instead of an unhandled 500. `run.test_cases` is only mutated after generation succeeds, so a failure here already left the original case untouched — confirmed, not assumed.
  - `fill_gap_category`: given the same per-condition isolation `execute_run` already uses, so one condition's LLM failure during a gap-fill attempt no longer discards whatever the other conditions already produced.
  - Frontend: `Review.tsx`'s "Regenerate this one" now catches and displays the error (previously silently swallowed — the user had to open dev tools to even know it failed, which is exactly how this was reported).
  - **Deliverable — verified against the real, still-active failure, not a simulated one:** re-ran the exact code path against Groq while the same daily quota was still exhausted (confirmed via the live server's own logs) and got back a clean `502` with the real rate-limit reason, plus confirmation the original test case was left completely intact. 160 tests still passing; no new tests added for this one since the fix is exception-handling plumbing around already-tested generation logic, verified live against a genuine failure instead.
- **User-defined Test Case ID prefix — second control alongside the module-derived scheme, refined through two corrections from the user before landing on the right shape:** first framing was a "starting number" override (building had already begun before the user caught it); the actual ask was a full custom *prefix string* the user types directly (e.g. `DEMND002_Reg_TC_`), not a number.
  - `test_cases_store.next_sequence_ids()` gained an optional `custom_prefix` param — used verbatim (no separator inserted, so the user's own trailing `_` is respected exactly) in place of the module-derived `TC_{MODULE}_` prefix when supplied, but reuses the exact same continuation logic either way (checks the persisted library + same-run not-yet-approved siblings) — so it's automatically collision-safe by construction, no separate validation path needed.
  - `id_prefix` threaded end-to-end the same way `scope` was: `Run.id_prefix` field, `POST /runs` form field (available on both the Jira-ticket and doc-upload tabs), through `generator.parse_test_cases()`/`generate_test_cases()`/`generate_test_cases_for_categories()`, `coverage_auditor.regenerate_gaps()`, and both call sites in `pipeline.py` (`execute_run`, `fill_gap_category`) plus `regenerate_test_case` — every path that mints an id for a given run consistently uses that run's chosen prefix, not just the initial generation.
  - Generate screen: new "Test Case ID Prefix" field (optional, monospace, same field on both tabs) with inline help text explaining the verbatim/no-separator behavior; the chosen prefix is echoed on both the Generate progress screen and the Review screen header, same treatment as Scope.
  - Added `tests/test_test_cases_store.py` custom-prefix tests (verbatim use, continuation from existing numbers under that prefix, interaction with `extra_existing_ids`) and a `tests/test_generator.py` test confirming `id_prefix` overrides the module-derived default end-to-end — 164 tests total now.
  - **Deliverable — verified live with a real generation using the user's own example prefix:** ran a real SCRUM-8 generation with `id_prefix=DEMND002_Reg_TC_` and no module set; got back 16 real cases as `DEMND002_Reg_TC_001`–`DEMND002_Reg_TC_016`, confirmed in both the API response and the Review screen (prefix shown in the header, ids on every row). Zero console errors.
- **Review screen: priority/verification filters + explicit Approved/Rejected status pills — user-requested from a screenshot of the case list.** Pure frontend change, no backend touched.
  - New filter bar above the bulk-action toolbar: toggleable chips for High/Medium/Low priority (multi-select — any combination) and "Needs verification," plus a "Clear filters" action and a "Showing N of M" count when a filter is active.
  - Filtering applies to the category sections, the "select all" checkbox, and bulk approve/reject — all scoped to what's currently visible, not the full run — so a reviewer can filter down to e.g. High-priority cases needing verification and bulk-act on just those.
  - Genuine coverage gaps (a category with zero cases ever generated) always stay visible regardless of active filters — only categories that *had* cases but none matching the current filter get hidden, so "Gap — no cases generated" never gets confused with "filtered out." Added a dedicated empty state ("No test cases match this filter") for when a filter hides every category.
  - Each case row now shows an explicit `Approved`/`Rejected` pill next to the Priority pill (previously status was only conveyed by a small icon at the row's edge, easy to miss at a glance — the same problem class as the earlier silently-swallowed bulk-approve feedback).
  - **Deliverable — verified live**: approved one case and rejected another via the API, loaded the Review screen and confirmed both status pills render correctly alongside Priority; toggled the "High" filter and confirmed only High-priority cases across the relevant categories remained visible with an accurate "Showing 5 of 16" count, and other categories collapsed out of view entirely rather than showing empty. Zero console errors. No backend changes, so the existing 164 tests stand unchanged.

---

## 7. Open Decisions to Confirm Before Sprint 0
- [x] Target test management tool for final export format — resolved to plain Excel (`excel_exporter.py`, Sprint 8) and direct Jira upload (below); no TestRail/Zephyr integration was needed
- [x] Jira upload target — resolved by inspecting the connected instance rather than guessing: it already has a purpose-built **"Test Case"** issue type (`/rest/api/3/project/SCRUM`), so `jira_uploader.py` targets that directly with a `generated-test-case` label and a "Relates" link back to the source ticket. No Xray/plugin dependency needed.
- [ ] Expected volume (tickets/month) — affects whether async/batching is needed early, and whether in-process run-status tracking (current default, see §3) is sufficient or a real task queue is needed
- [x] Who reviews/approves generated test cases, and where — resolved to a dedicated frontend (§3) per the `UX Screen/` mockups
- [x] Module list source for the module-scoping dropdown (Screen 1) and filter (Screen 3) — resolved: `GET /modules` returns the union of the distinct `module` values already stored on `old_test_cases` (populated via Screen 5's import) plus a small manually-managed list (`src/modules_store.py`, editable from Settings post-Sprint-9) for modules a user wants available before any test case uses them yet. No separate config needed unless Jira-component sync is wanted later.
- [ ] Run History retention — keep all runs indefinitely, or prune/archive after N days? Still unresolved — run history is in-memory only (§3) and lost on backend restart regardless, so this only matters once persistence is addressed.

---

## 8. How to Use This With Claude Code
Note: Claude Code here is your VS Code build assistant — it writes the codebase. Groq/Claude (via `llm_client.py`) is the LLM the *application itself* calls at runtime for decomposition, generation, and coverage auditing. The two are unrelated; don't mix up the API keys. `LLM_PROVIDER` in `.env` controls which one the app uses per step — set it globally, or pass a `provider` override into individual calls if you want a hybrid setup (e.g. Groq for decomposition, Claude for generation).

Work sprint by sprint. At the start of each sprint, point Claude Code at this `plan.md` and the relevant folder(s), and ask it to implement just that sprint's deliverables — keeps context focused and output reviewable in manageable chunks.
