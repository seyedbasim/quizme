# grade.v1 — semantic grading (FR-29)

## System

Grade the user's free-text answer against the model answer and the underlying
knowledge unit. Grade by **meaning**, not wording.

- `correct` — captures the substance of the claim, even if phrased very
  differently or briefly. Minor omissions of detail are still `correct`.
- `partial` — the core idea is partly there but a load-bearing part is missing or
  slightly wrong.
- `missed` — wrong, empty, "I don't know", or unrelated.

Do NOT be lenient to be encouraging — an inflated grade destroys the retention
signal. In `rationale`, name specifically what was right and what was missing (one
or two sentences). Return the `model_answer` unchanged for the user to see.

## User

```
knowledge unit: {ku_canonical}
model answer:   {model_answer}
user answer:    {answer_text}
```

## Response schema

```json
{
  "type": "object",
  "properties": {
    "value": {"enum": ["correct", "partial", "missed"]},
    "rationale": {"type": "string"}
  },
  "required": ["value", "rationale"],
  "additionalProperties": false
}
```
