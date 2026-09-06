# topic_note.v1 — Topic Note regeneration (FR-18)

## System

Write a concise, readable Markdown note for one topic, built **only** from the
knowledge units given. This note is display-only — it is regenerated every time
the units change and is never read back by the system (AD-2).

- Organise the units logically (definitions first, then mechanisms, then edge
  cases). Group related ones.
- Do not add facts that are not in the units. Do not "improve" the claims.
- Every claim keeps a reference to its unit id so the UI can link to the source
  audio, e.g. `... the RTO minimum is 1 second [ku_01H...].`
- If units contradict each other, say so plainly rather than picking one.

## User

Topic: {topic_label}

Knowledge units:
```
{units}
```

## Response schema

```json
{
  "type": "object",
  "properties": {
    "markdown": {"type": "string"}
  },
  "required": ["markdown"],
  "additionalProperties": false
}
```
