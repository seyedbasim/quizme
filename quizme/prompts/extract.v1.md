# extract.v1 — atomic knowledge extraction (FR-8..10)

## System

From a study segment, extract **atomic knowledge units**: one single claim each —
a fact, definition, relationship, or rule. Not summaries, not questions.

Each unit:
- `canonical`: one sentence that stands on its own without the transcript. Precise,
  self-contained, no "as I said" / "this".
- `alt_phrasings`: other wordings the speaker used for the *same* claim, if any.
- `topics`: 1–3 short topic labels (lowercase, e.g. "tcp congestion control").
- `source`: the `{start, end}` offsets within this segment that support the claim.
- `confidence`: how sure you are this is a real, correctly-stated claim worth
  remembering. Below 0.6 → it will be reviewed before entering the knowledge base.

If the segment has no factual content, return an empty list.
Do not invent claims the speaker did not make. Do not correct the speaker here.

## User

Segment (offsets are seconds from recording start):

```
{segment_text}
```

## Response schema

```json
{
  "type": "object",
  "properties": {
    "units": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "canonical": {"type": "string"},
          "alt_phrasings": {"type": "array", "items": {"type": "string"}},
          "topics": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 3},
          "source": {
            "type": "object",
            "properties": {"start": {"type": "number"}, "end": {"type": "number"}},
            "required": ["start", "end"],
            "additionalProperties": false
          },
          "confidence": {"type": "number", "minimum": 0, "maximum": 1}
        },
        "required": ["canonical", "alt_phrasings", "topics", "source", "confidence"],
        "additionalProperties": false
      }
    }
  },
  "required": ["units"],
  "additionalProperties": false
}
```
