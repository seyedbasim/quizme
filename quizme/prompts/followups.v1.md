# followups.v1 — follow-up intent detection (FR-40)

## System

Find moments where the speaker says they need to **check, verify, or research
something later** — a real intention to act, not idle musing.

Counts (→ extract): "I need to check the RFC on this", "I'm not sure that's right,
must confirm", "TODO: read the paper on X", "come back to this and look it up".

Does not count (→ skip): "I wonder why that is" with no intent to follow up,
rhetorical questions, "anyway, moving on".

For each real follow-up:
- `intent`: a short imperative of what to do ("Check the exact TCP RTO minimum in RFC 6298").
- `quote`: the speaker's verbatim words that triggered it.
- `source`: `{start, end}` offsets.
- `topic`: the topic it relates to, if clear.
- `confidence`: below 0.65 → routed to review instead of the open to-do list.

## User

```
{segment_text}
```

## Response schema

```json
{
  "type": "object",
  "properties": {
    "followups": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "intent": {"type": "string"},
          "quote": {"type": "string"},
          "topic": {"type": ["string", "null"]},
          "source": {
            "type": "object",
            "properties": {"start": {"type": "number"}, "end": {"type": "number"}},
            "required": ["start", "end"],
            "additionalProperties": false
          },
          "confidence": {"type": "number", "minimum": 0, "maximum": 1}
        },
        "required": ["intent", "quote", "topic", "source", "confidence"],
        "additionalProperties": false
      }
    }
  },
  "required": ["followups"],
  "additionalProperties": false
}
```
