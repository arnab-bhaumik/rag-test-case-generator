# RAG-Based Test Case Generator

Generates test cases from design docs and Jira tickets using Retrieval-Augmented Generation, styled after your team's existing test cases. Review, edit, and approve generated cases in a web UI, then export to Excel or push straight into Jira as linked "Test Case" issues. Approved cases feed back into the pattern library, so generation keeps learning your team's conventions.

All 10 sprints in [plan.md](plan.md) are complete, plus a series of post-launch features and fixes — see that file for the full build log, architecture rationale, and what was verified at every step (including live, real-LLM verification, not just unit tests).

## Features

- **Generate** — kick off a run from a Jira ticket key or an uploaded PDF/DOCX design doc. Optional controls:
  - **Module** — scopes retrieval and tags the run.
  - **Focus / Scope** — narrow generation to part of a larger requirement (e.g. only the new/changed behavior in a design doc reused across releases). A `.docx` upload auto-detects red-marked text and pre-fills this as a suggestion — always editable, never applied silently.
  - **Test Case ID Prefix** — override the default `TC_{MODULE}_001` auto-numbering with your own convention (e.g. `DEMND002_Reg_TC_`), used verbatim and continued sequentially across runs.
  - Live step-by-step progress while the pipeline runs (decompose → retrieve → generate → audit coverage).
- **Review** — cases grouped by category (Positive/Negative/Boundary/Edge/Security/Integration/Data Validation), inline editing of every field (including the Test Case ID itself, with collision protection), single-case regenerate, bulk approve/reject with a grounding gate for ungrounded cases, coverage-gap fill/acknowledge, and filters by priority and verification status.
- **Coverage Matrix** — requirement-to-test-case traceability (RTM), covered/uncovered status per condition.
- **Export** — download an approved-cases Excel workbook (+ RTM sheet) or push approved cases into Jira as linked "Test Case" issues.
- **Test Case Library** — the RAG style/pattern source: import old test cases from CSV/XLSX, browse/search them, grouped into "Uploaded" and "Generated" sessions so you can trace any case back to exactly the upload or run it came from.
- **Run History** — every run this backend process has executed (in-memory — see [Known limitations](#known-limitations)).
- **Settings** — LLM provider/model and Jira credentials (editable, with a "Test connection" check before saving; keys are write-only, never echoed back), plus module management (add/rename/delete).

## Setup

1. Create and activate a virtual environment:
   ```
   python -m venv .venv
   .venv\Scripts\activate        # Windows
   source .venv/bin/activate     # macOS/Linux
   ```
2. Install backend dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and fill in the keys you have:
   ```
   cp .env.example .env
   ```
   - `LLM_PROVIDER` selects the default provider (`groq` or `claude`) used by `src/generation/llm_client.py`.
   - `JIRA_BASE_URL`/`JIRA_EMAIL`/`JIRA_API_TOKEN` are required for ticket ingestion and Jira upload. The connected Jira project needs a **"Test Case"** issue type (see plan.md §7) — if yours doesn't have one, `jira_uploader.py`'s `ISSUE_TYPE_NAME` will need adjusting.
   - `JIRA_PROJECT_KEY` is only needed as a fallback upload target for doc-sourced runs (a run started from a Jira ticket uploads into that ticket's own project automatically).
   - All of the above can also be set (and tested) from the app's **Settings** screen after it's running, instead of editing `.env` by hand.
4. Install frontend dependencies:
   ```
   cd frontend && npm install
   ```

## Running the app

Backend (from the repo root):
```
uvicorn api.main:app --reload --port 8000
```

Frontend (in a second terminal):
```
cd frontend
npm run dev            # http://localhost:5173
```

Open `http://localhost:5173`. The frontend talks to the API at `http://localhost:8000` by default (override with a `VITE_API_URL` env var); CORS is pre-configured for the Vite dev server's origin.

Start on **Generate** with a Jira ticket key or an uploaded PDF/DOCX; a run takes 1-2 minutes (several sequential LLM calls) and you'll see live step-by-step progress.

## Testing

```
python -m pytest              # backend — fast, hermetic (no live LLM/Jira/Chroma calls)
cd frontend && npx tsc -b     # frontend type-check
cd frontend && npm run build  # frontend production build
```

The backend suite covers the pure/deterministic logic in every module — chunking, decomposition parsing, generation parsing, sequential test case ID assignment, coverage auditing, retrieval reranking, RTM building, Excel export, Jira upload (mocked HTTP), and the CSV/XLSX import column-matching logic. It deliberately does not hit real APIs, so it runs the same with or without keys configured.

For live, end-to-end verification (real LLM calls, a real Jira ticket, a real Jira upload), use the sanity scripts below and drive the actual UI — the pytest suite alone doesn't cover that path.

### Sprint 0 sanity checks

```
python -m scripts.verify_chroma        # confirms local persistent Chroma client works
python -m scripts.hello_world_checks   # confirms LLM provider(s) + Jira are reachable
```

Both scripts skip (not fail) any provider whose keys aren't set in `.env`.

## Project layout

See [plan.md §4](plan.md) for the full folder structure and the rationale behind each module.

## Architecture notes

- **Vector store**: ChromaDB, persisted locally to `chroma_db/` (gitignored) — two collections, `old_test_cases` (the style/pattern library) and `design_docs` (retrieval context for generation).
- **Retries & resilience**: LLM calls (`llm_client.py`) and Jira HTTP calls (`jira_client.py`, `jira_uploader.py`) retry transient failures (rate limits, timeouts, connection errors, 5xx) up to 3 times with exponential backoff, via `tenacity`. Auth/bad-request errors are not retried. A single condition's generation or audit failure never aborts an entire run — it degrades to zero cases for that condition (a gap the reviewer can fill or acknowledge) rather than discarding everything else already generated.
- **Test Case ID scheme**: sequential `TC_{MODULE}_001`-style ids (or a fully custom prefix, see Features above), continuing from the highest number already used with that exact prefix across the whole library — safe against collisions both within a run and across concurrent unapproved runs.

## Known limitations

- **Run history is in-memory only** and lost on backend restart — an intentional MVP simplification (see plan.md §3/§7), not yet addressed. The persisted Test Case Library (Chroma) is unaffected by a restart; only in-progress/unreviewed run data is not persisted.
- **Local-only by default**: this app runs entirely on your machine (backend + Chroma + frontend). See plan.md for a discussion of hosting options if you want it running elsewhere.
