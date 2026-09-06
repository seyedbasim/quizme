# Quizme

A personal knowledge system that grows from your own study recordings and quizzes you daily.

You record yourself talking through what you study. Quizme transcribes it, keeps only the
study-relevant parts, extracts **atomic knowledge units** (single claims, each linked back to
the exact recording and timestamp), and consolidates them into a coherent, deduplicated
knowledge base. Every day it picks what you're most at risk of forgetting and quizzes you
over Telegram; an LLM grades your free-text answers and updates the schedule.

**This repo is a v1 scaffold.** The design is fully specified in [`docs/`](docs/) — read the
PRD and the Architecture Spine first. The domain layer (`quizme/domain/`) has real,
tested logic; everything else is a typed skeleton with `NotImplementedError` and docstrings
that cite the governing FR / AD numbers.

## Design docs

| Doc | What it is |
| --- | --- |
| [`docs/prd.md`](docs/prd.md) | What the system must do — 53 functional requirements, grouped by feature |
| [`docs/architecture-spine.md`](docs/architecture-spine.md) | The invariants (AD-1..AD-19), stack, and structure |
| [`docs/prd.html`](docs/prd.html) / [`docs/architecture-spine.html`](docs/architecture-spine.html) | Rendered, with diagrams |

## Shape

Hexagonal core + pipes-and-filters ingestion pipeline + append-only operation log.

```
quizme/
  domain/        pure logic, no I/O, no cloud SDK (AD-11, AD-18)
  application/   orchestration; depends on domain + port protocols
  adapters/      Azure implementations of the ports (+ AD-18 local fallback stubs)
  web/           FastAPI app — the WebApp adapter (FR-46..52)
functions/       Azure Functions host: HTTP app, quiz timer, queue worker
migrations/      Alembic
```

Deployed serverless-first on Azure (Functions / Container Apps, scale-to-zero) in **Southeast
Asia**, funded by a Visual Studio Enterprise (MCT) $150/mo credit — which carries dev/test
terms and a **hard spending cap**, hence `FR-53` / `AD-19` (degrade before the cap) and
`AD-18` (stay exportable / re-hostable locally).

## Getting started

```bash
uv sync --extra dev              # create the venv, install deps
uv run pytest                    # domain tests should pass
uv run ruff check .
uv run uvicorn quizme.web.app:app --reload   # web app (routes are stubs)
```

See [`infra/README.md`](infra/README.md) for the Azure resources to provision.

## Status

Nothing is wired end-to-end yet. Next steps, in order:

1. Provision Azure resources (`infra/`), confirm the chat model + quota in Southeast Asia (PRD Open Q 13).
2. Implement `adapters/store_postgres.py` + the initial migration, run it.
3. Implement `adapters/transcriber_speech.py` and `adapters/llm_foundry.py`.
4. Fill in the pipeline stages against the prompt drafts in `quizme/prompts/`.
5. Build the eval set: hand-label ~5 recordings (PRD Open Q 3 / Q 8).
