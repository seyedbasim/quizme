# consolidate.v1 — per-pair verdict (FR-12)

## System

You are given ONE new knowledge unit and a short list of existing units retrieved
as its nearest neighbours. For **each** existing unit, judge its relationship to
the new one:

- `duplicate` — same claim, no new information. (The system will merge.)
- `elaboration` — same subject, and one is strictly more complete/precise than the
  other. Say which in the rationale.
- `contradiction` — they make incompatible claims about the same thing. (The
  system will NOT merge — it flags both for the user.)
- `unrelated` — different claims.

Be conservative: only say `duplicate`/`elaboration` when you are confident. If two
units are merely about the same topic, that is `unrelated`. A wrong merge destroys
a distinction; a missed merge is cheaply fixed later.

`confidence` is your certainty in the label (0–1). The system only auto-merges
above a threshold.

## User

New unit:
```
{new_unit}
```

Existing neighbours:
```
{neighbours}
```

## Response schema

```json
{
  "type": "object",
  "properties": {
    "judgements": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "existing_ku_id": {"type": "string"},
          "verdict": {"enum": ["duplicate", "elaboration", "contradiction", "unrelated"]},
          "confidence": {"type": "number", "minimum": 0, "maximum": 1},
          "rationale": {"type": "string"}
        },
        "required": ["existing_ku_id", "verdict", "confidence", "rationale"],
        "additionalProperties": false
      }
    }
  },
  "required": ["judgements"],
  "additionalProperties": false
}
```
