# Prompts

Versioned prompt templates. The filename carries the `prompt_version` recorded on
every `llm_call` row and every `KUOperation` (AD-8). **Changing a prompt means a
new file and bumping the owning stage's `STAGE_VERSION`** (AD-4) — never edit a
version in place once it has produced data.

| File | Stage | FR |
| --- | --- | --- |
| `filter.v1.md` | filter | FR-5..7 |
| `extract.v1.md` | extract | FR-8..10 |
| `followups.v1.md` | followups | FR-40 |
| `consolidate.v1.md` | consolidate | FR-12 |
| `question.v1.md` | quiz build | FR-25 |
| `grade.v1.md` | grading | FR-29 |
| `topic_note.v1.md` | notes | FR-18 |

These are **first drafts**. They must be tuned against the hand-labelled eval set
(PRD Open Q 3 / Q 8) before the pipeline is trusted. Each expects a JSON-schema
response (structured output, AD-8 determinism).
