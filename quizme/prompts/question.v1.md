# question.v1 — question generation (FR-25)

## System

Write ONE quiz question that tests recall of the given knowledge unit.

- Answerable from the unit alone — no outside knowledge beyond what the speaker
  studied.
- Vary the type across a quiz: `short_answer`, `cloze` (blank a load-bearing term,
  never a trivial word), `free_recall` ("explain / state ...").
- `model_answer` is the ideal answer, drawn from the unit.
- Do not give away the answer in the prompt.

## User

Knowledge unit:
```
canonical: {canonical}
alt_phrasings: {alt_phrasings}
topics: {topics}
```
Requested type: {requested_type}

## Response schema

```json
{
  "type": "object",
  "properties": {
    "type": {"enum": ["short_answer", "cloze", "free_recall"]},
    "prompt": {"type": "string"},
    "model_answer": {"type": "string"},
    "phrasing_used": {"type": "string"}
  },
  "required": ["type", "prompt", "model_answer", "phrasing_used"],
  "additionalProperties": false
}
```
