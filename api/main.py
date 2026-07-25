"""FastAPI app: CORS + router registration."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import coverage, documents, export, modules, runs, settings, test_case_library, test_cases

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
# Groq/Anthropic/urllib3 are chatty at INFO (every HTTP request) — keep our
# own modules at INFO, everything else at WARNING.
for noisy in ("httpx", "httpcore", "urllib3"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

app = FastAPI(title="RAG Test Case Generator API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server default; extend for prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(runs.router)
app.include_router(documents.router)
app.include_router(test_cases.router)
app.include_router(test_case_library.router)
app.include_router(coverage.router)
app.include_router(export.router)
app.include_router(modules.router)
app.include_router(settings.router)


@app.get("/")
async def health():
    return {"status": "ok"}
