---
title: Quizme
status: draft
created: 2026-09-06
updated: 2026-09-06
---

# PRD: Quizme
*Working title — confirm.*

## 0. Document Purpose

This PRD is for the builder (also the sole user) and any future collaborator or agent implementing Quizme. It defines **what** the system must do, not how. It is Glossary-anchored: features are grouped, Functional Requirements (FR-N) are nested and globally numbered, assumptions are tagged inline as `[ASSUMPTION]` and indexed in §9. Technical choices (stack, transports, model IDs) live in the companion **Architecture Spine** (`docs/architecture-spine.md`), not here — but the platform shape is load-bearing enough to state up front:

- **Quizme is a hosted web application on Microsoft Azure**, deployed **serverless-first** (Azure Functions / Container Apps, scale-to-zero where possible), backed by managed Postgres and Blob Storage, in region **Southeast Asia** (Singapore), in the user's own subscription.
- **Funding is a Visual Studio Enterprise (MCT) subscription monthly Azure credit — $150/month.** It carries **dev/test-only terms and a hard spending cap** — see §5.2; this shapes the deployment model and makes the budget guardrail (FR-38, FR-53) and the export/re-host hedge (§5.2, AD-18) load-bearing, not nice-to-have.
- **Recordings are uploaded manually** through the web app — no folder watch or device sync.
- **AI inference runs on Azure AI Foundry** (chat) and **Azure AI Speech** (transcription) deployments inside the user's own Azure tenant — not a third-party consumer API.
- **The daily quiz is delivered by a Telegram bot**; everything else (upload, review, browsing, to-do list, retention) lives in the web app.

Internet fact-validation and a concept knowledge-graph are explicitly deferred (see §5.1, §6.2). A fully-local deployment (Ollama + local whisper on the user's Mac) is retained as a **documented fallback** for the day the credits lapse (§5.2, §6.2) — the architecture keeps every model/storage boundary swappable.

## 1. Vision

Quizme turns a habit the user already has — talking through study material out loud and recording it on an iPhone — into a durable, self-maintaining body of knowledge that quizzes them back.

The user records long, unstructured audio while studying. Most of that audio is thinking-out-loud, tangents, and repetition; a fraction is real material worth keeping. Quizme ingests each recording, transcribes it, keeps only the study-relevant parts, and extracts atomic **Knowledge Units** — single factual claims with a link back to the exact recording and timestamp they came from. As recordings accumulate, the same fact will be stated many times across many files; Quizme's **Consolidation Engine** uses an LLM to merge duplicates, absorb elaborations, and flag contradictions, so the knowledge base stays coherent instead of growing into noise. A readable **Topic Note** per subject is regenerated from the units whenever they change.

Every day, Quizme picks the units the user is most at risk of forgetting (spaced-repetition scheduling), generates questions from them, and delivers a short quiz. The user answers in free text; an LLM grades semantically and the schedule updates. The result is a personal knowledge system that grows from the user's own voice and actively defends their retention over months and years.

## 2. Target User

### 2.1 Jobs To Be Done

- **Functional:** "Capture what I learn while studying without stopping to write notes."
- **Functional:** "Keep everything I've learned in one place that doesn't rot as it grows."
- **Functional:** "Make sure I actually retain it — test me before I forget."
- **Emotional:** "Feel confident my knowledge is still there, not quietly decaying."
- **Contextual:** "Fit into a phone-first daily routine; the quiz has to be frictionless or I won't do it."
- **Builder framing:** "This is for me. Success is that I use it daily and it survives contact with a year of recordings."

### 2.2 Non-Users (v1)

- Multiple users / shared knowledge bases. `[ASSUMPTION: single user; the web app authenticates exactly one identity.]`
- People who want a note-taking app they type into. Quizme's input is voice; manual editing exists only as a correction path (§4.9).
- Learners who need authoritative correctness against external sources on day one — that is the deferred validation layer (§5.1).

### 2.3 Key User Journeys

- **UJ-1. Basim records a study session and uploads it.**
  - **Persona + context:** Basim studies a technical topic by explaining it aloud while pacing. He does this most days for 20–60 minutes.
  - **Entry state:** iPhone Voice Memos. At his desk (or on his phone browser) he opens the Quizme web app, already signed in.
  - **Path:** He shares / exports the recording(s) and drops them onto the upload page → the app confirms "3 recordings received, processing" → the pipeline transcribes, filters, extracts units, and consolidates them into the knowledge base in the background.
  - **Climax:** Within a few minutes the ingestion status page shows "+12 units, 2 merges, 1 contradiction to review"; the next morning's quiz already reflects what he said.
  - **Resolution:** Knowledge base is current. One item waits in the Review Queue.
  - **Edge case:** He uploads the same file twice → the second upload is recognized by content hash and skipped, not reprocessed.

- **UJ-2. Basim takes the daily quiz on his phone.**
  - **Persona + context:** Morning coffee, 5 minutes, phone in hand.
  - **Entry state:** A push notification: "Today's quiz — 8 questions."
  - **Path:** He opens the chat, gets one question at a time, types a free-text answer, sees "correct / partially correct / missed" with the model answer and the source recording reference, moves to the next.
  - **Climax:** Finishing the quiz — he sees which topics are weak and that his schedule updated.
  - **Resolution:** Done for the day. Weak units resurface sooner.
  - **Edge case:** He disputes a grade → one tap flags the question; it goes to the Review Queue and does not count against him.

- **UJ-3. Basim resolves a contradiction.**
  - **Persona + context:** He earlier recorded two different values for the same fact (misremembered once).
  - **Entry state:** The web app shows a Review Queue badge: 1 item.
  - **Path:** He opens the queue → sees both claims side by side, each with its recording + timestamp → picks the correct one (or edits a merged version) → the loser is archived with a tombstone, not deleted.
  - **Climax:** The knowledge base now holds one correct unit; provenance from both recordings is retained.
  - **Resolution:** Queue empty.

- **UJ-4. Basim works through what he told himself to look up.**
  - **Persona + context:** While recording, Basim repeatedly says things like "I'm not sure about this, need to check the RFC" or "should read more on this later." He also missed two quiz questions this week.
  - **Entry state:** He opens the web app with a spare 20 minutes.
  - **Path:** He opens the To-Do page → sees a list grouped by Topic: 4 **Follow-up** items (each with the exact quote and the recording timestamp) and 2 **Revisit** items (KUs he missed, with the model answer) → he researches one follow-up, marks it done; snoozes another to next week; re-reads a Revisit KU's Topic Note.
  - **Climax:** The list shrinks; the two Revisit KUs are back in the quiz rotation sooner.
  - **Resolution:** Open items down to 3, one snoozed. Next time he answers those KUs correctly twice, the Revisit items close themselves.
  - **Edge case:** He said "check this" about the same thing in three separate recordings → it appears as **one** item with `trigger_count: 3`, not three items.

## 3. Glossary

Downstream code, prompts, and docs use these terms **exactly**. No synonyms elsewhere.

- **Recording** — one audio file the user has **uploaded** through the web app (originating from iPhone Voice Memos). Immutable once accepted. Has a stable `recording_id` and a content hash.
- **Upload** — one user action submitting one or more audio files to the web app. Produces one Recording per accepted file; duplicates (by content hash) are rejected.
- **Transcript** — the full speech-to-text output for one Recording, with word- or segment-level timestamps. Immutable.
- **Web App** — the authenticated single-user Azure-hosted web interface: upload, ingestion status, Review Queue, knowledge-base browsing, To-Do list, retention view. The system of engagement for everything except the daily quiz.
- **Segment** — a contiguous span of a Transcript, classified as `study` or `noise`. Only `study` Segments proceed.
- **Knowledge Unit (KU)** — one atomic claim (a single fact, definition, or relationship), with a canonical phrasing, optional alternate phrasings, one or more Topics, a `status`, and a `sources` list. The single source of truth for what the user knows.
- **Source** — a `(recording_id, start, end)` reference on a KU, pointing at the span that supports it. A KU may have many.
- **Topic** — a label grouping related KUs. Has a slug. Assigned by the extraction/consolidation LLM, editable by the user.
- **Topic Note** — a human-readable Markdown document for one Topic, **regenerated** from that Topic's KUs. Never hand-authored as source of truth.
- **Consolidation** — the process that takes newly extracted KUs and reconciles them against the existing knowledge base: merge, elaborate, flag contradiction, or insert as new.
- **KU Operation** — one recorded, append-only change to the knowledge base (`create`, `merge`, `elaborate`, `flag_contradiction`, `split`, `archive`, `edit`). The knowledge base state is the fold of all KU Operations.
- **Contradiction** — two KUs that make incompatible claims about the same subject. Never auto-resolved.
- **Review Queue** — the list of items requiring a user decision (contradictions, low-confidence extractions, disputed quiz grades).
- **Card** — spaced-repetition scheduling state (FSRS) attached to one KU: due date, stability, difficulty, review history.
- **Quiz** — the set of Questions delivered on one day.
- **Question** — one item generated from one KU for one Quiz. Types: short-answer, cloze (fill-in-the-blank), free recall.
- **Grade** — the LLM's evaluation of a free-text Answer against the KU: `correct`, `partial`, or `missed`, with a rationale.
- **Answer** — the user's free-text response to a Question.
- **Action Item** — a task for the user to do *outside* Quizme (research a topic, verify a claim, re-learn something). Has an `origin`, a `status` (`open`, `done`, `dismissed`, `snoozed`), a Source and/or a linked KU and Topic, timestamps, an optional revisit date, and a `trigger_count`.
- **Follow-up** — an Action Item `origin`: in a Recording the user expressed intent to check, research, or verify something later ("I should look into…", "need to confirm…", "TODO: read the paper on…").
- **Revisit** — an Action Item `origin`: the user answered a Question `missed` (or repeatedly `partial`), so the linked KU is queued to be re-learned.

## 4. Features

### 4.1 Audio Ingestion & Transcription

**Description:** The user uploads recordings through the web app (§4.12, FR-47). Each accepted Recording is stored immutably, then processed exactly once through the background pipeline: transcribe, store the Transcript, and hand off to filtering. Realizes UJ-1. `[ASSUMPTION: recordings are m4a/mp3/wav exported from iPhone Voice Memos; per-file size cap is configured.]` `[ASSUMPTION: transcription uses Azure AI Speech batch/fast transcription (Whisper model), which is available in the Southeast Asia region — Azure OpenAI's Whisper deployment is not in that region.]` `[ASSUMPTION: English only for v1.]`

**Functional Requirements:**

#### FR-1: Accept an uploaded recording exactly once

On a successful Upload, the system durably stores each new audio file as a Recording and enqueues it for processing; a re-upload of the same bytes is recognized and not stored or processed again.

**Consequences (testable):**
- The web request returns success only after the file is durably stored (not merely received in memory).
- Two uploads of byte-identical content produce one Recording; the second is reported as "already have this."
- A queued-but-not-yet-processed Recording survives an application restart.
- An upload that fails midway leaves no partial Recording.

#### FR-2: Preserve the original immutably

The system stores each Recording's original bytes in content-addressed object storage and never mutates or deletes them from the pipeline.

**Consequences (testable):**
- The stored original is byte-identical to what was uploaded.
- No pipeline stage modifies or deletes a stored Recording.
- The knowledge base can be fully rebuilt from stored Recordings + Transcripts alone.

#### FR-3: Transcribe with timestamps

The system produces a Transcript with at least segment-level timestamps for every Recording.

**Consequences (testable):**
- Every Transcript segment carries a start and end time.
- Transcription failure is recorded against the Recording and retried, not silently dropped.
- Transcript is stored immutably and linked to its Recording.

#### FR-4: Report ingestion outcome

For each processed Recording (or batch), the system records and shows a summary: transcription status, units added, merges, contradictions raised, follow-ups detected, failures.

**Consequences (testable):**
- The summary is visible on the web app's ingestion status page (FR-48) with per-Recording detail.
- A batch that raises a contradiction or a failure also pushes a short Telegram notice; a clean batch does not (no noise).

### 4.2 Relevance Filtering & Segmentation

**Description:** Most recorded audio is not study content. An LLM pass splits each Transcript into Segments and labels each `study` or `noise`; only `study` Segments continue. Realizes UJ-1.

**Functional Requirements:**

#### FR-5: Classify transcript segments

The system partitions each Transcript into Segments and assigns each a `study` / `noise` label with a confidence.

**Consequences (testable):**
- Every part of the Transcript belongs to exactly one Segment (no gaps, no overlap).
- Each Segment records the label, confidence, and the model/prompt version that produced it.
- Re-running classification with an unchanged prompt version is a no-op.

#### FR-6: Retain full context for audit

`noise` Segments are retained (not discarded), linked to the Transcript, and excluded only from downstream extraction.

**Consequences (testable):**
- A reviewer can view the whole Transcript with `study`/`noise` shading.
- Reclassifying a Segment `noise → study` later triggers extraction for just that Segment.

#### FR-7: Low-confidence handling

Segments near the `study`/`noise` decision boundary are treated as `study` (fail toward keeping content) but marked for optional review.

**Consequences (testable):**
- A Segment with confidence below a configured threshold is still extracted from.
- Such Segments are listed in an "uncertain" view.

### 4.3 Knowledge Extraction

**Description:** From `study` Segments, an LLM extracts atomic Knowledge Units — one claim each — with a canonical phrasing, candidate Topics, and Sources pointing at the originating span. The same pass also scans `study` Segments for **Follow-up** intents — moments where the user says they need to check, verify, or research something later — which become Action Items (§4.11, FR-40). Realizes UJ-1, UJ-4.

**Functional Requirements:**

#### FR-8: Extract atomic units

The system produces Knowledge Units from `study` Segments, each expressing exactly one claim.

**Consequences (testable):**
- Each KU has a canonical phrasing that stands alone without the surrounding transcript.
- Each KU has at least one Source `(recording_id, start, end)`.
- Each KU has at least one candidate Topic.
- A Segment yielding no factual content produces zero KUs (not an empty KU).

#### FR-9: Capture alternate phrasings

When the same Segment states a claim more than one way, the system keeps the additional phrasings on the KU.

**Consequences (testable):**
- Alternate phrasings are stored as a list on the KU and are available to Question generation.

#### FR-10: Flag uncertain extractions

Extractions the model is not confident represent a real, correct-as-stated claim are marked for review rather than silently inserted.

**Consequences (testable):**
- A low-confidence KU enters the Review Queue with its Source.
- It does not appear in quizzes until confirmed.

### 4.4 Consolidation Engine

**Description:** New KUs are reconciled against the existing knowledge base. For each new KU the system finds semantically near existing KUs and an LLM decides, per candidate pair: **duplicate** (merge), **elaboration** (merge and enrich), **contradiction** (flag, keep both), or **new** (insert). All changes are recorded as append-only KU Operations. Consolidation is always scoped to one recording's output plus neighbors, or to one Topic — never the whole corpus. Realizes UJ-1, UJ-3.

**Functional Requirements:**

#### FR-11: Semantic candidate retrieval

For each new KU the system retrieves the most semantically similar existing KUs as merge candidates.

**Consequences (testable):**
- Retrieval uses vector similarity over KU embeddings.
- The candidate set size is bounded by configuration.

#### FR-12: Adjudicate each candidate

An LLM classifies each `(new KU, existing KU)` pair as `duplicate`, `elaboration`, `contradiction`, or `unrelated`.

**Consequences (testable):**
- The decision, rationale, model version, and prompt version are recorded on the resulting KU Operation.
- `unrelated` for all candidates results in the new KU being inserted as `create`.

#### FR-13: Merge duplicates without losing provenance

A `duplicate` decision merges the two KUs into one, keeping the richer canonical phrasing, unioning Sources, and appending the other phrasing to alternates.

**Consequences (testable):**
- The merged KU's `sources` is the set union of both inputs' Sources — no Source is dropped.
- The superseded KU id is retained as a tombstone pointing at the survivor.
- The operation is reversible from the KU Operation log.

#### FR-14: Absorb elaborations

An `elaboration` decision updates the surviving KU's claim to the more complete form and unions Sources.

**Consequences (testable):**
- The pre-elaboration phrasing is retained in history.
- Topics are unioned.

#### FR-15: Flag contradictions, never auto-resolve

A `contradiction` decision creates a Review Queue item holding both KUs; neither is edited, merged, or archived automatically.

**Consequences (testable):**
- Both KUs remain individually queryable until the user decides.
- Both KUs are suppressed from quizzes while the contradiction is open (configurable).
- Resolving the item records a user-attributed KU Operation.

#### FR-16: Periodic per-Topic reorganization

When a Topic accumulates a configured amount of change, the system runs a scoped LLM pass over only that Topic's KUs to split overly broad claims, merge stragglers, and tidy Topic assignment.

**Consequences (testable):**
- The pass never receives KUs from outside the Topic.
- Every change is a logged KU Operation.
- The run is skippable and does not block ingestion.

**Feature-specific NFRs:**
- No single LLM call in this feature receives more than one recording's KUs plus their retrieval neighbors, or one Topic's KUs.

### 4.5 Knowledge Base & Topic Notes

**Description:** The knowledge base is the set of live KUs, derived by folding the KU Operation log. Per Topic, a readable Markdown Topic Note is regenerated from the live KUs whenever they change. Realizes UJ-1.

**Functional Requirements:**

#### FR-17: Knowledge base as a projection

Current knowledge base state is deterministically derived from the append-only KU Operation log.

**Consequences (testable):**
- Replaying the log from empty reproduces the identical live KU set.
- No KU is mutated in place outside a recorded KU Operation.

#### FR-18: Regenerate Topic Notes

After KUs in a Topic change, the system regenerates that Topic Note from its live KUs.

**Consequences (testable):**
- A Topic Note is never an input to any other pipeline stage.
- Each Topic Note lists or links the Sources behind its content.
- Regeneration is idempotent given unchanged KUs and prompt version.

#### FR-19: Browse and search

In the web app (FR-50) the user can browse Topics, read Topic Notes, and search KUs by text and by Topic.

**Consequences (testable):**
- Every KU shown exposes its Sources (recording + timestamp), with a link to play the audio span.
- Search covers canonical and alternate phrasings.

#### FR-20: Full rebuild

The system can rebuild the entire knowledge base from stored Recordings + Transcripts (re-running filter → extract → consolidate) on demand.

**Consequences (testable):**
- A rebuild into an empty store completes without manual intervention.
- Rebuild uses current prompt/model versions and records that in the new KU Operations.

### 4.6 Review Queue

**Description:** A single place for everything needing a human decision: contradictions (FR-15), uncertain segments/extractions (FR-7, FR-10), and disputed quiz grades (FR-31). Realizes UJ-3.

**Functional Requirements:**

#### FR-21: Unified queue

All items requiring a decision appear in one list in the web app (FR-49) with type, context, and the relevant Sources.

**Consequences (testable):**
- A contradiction item shows both KUs with their recordings and timestamps.
- Items are actionable without leaving the queue view.

#### FR-22: Resolve with attribution

Resolving an item records a user-attributed KU Operation (or grade correction) and removes it from the queue.

**Consequences (testable):**
- The chosen resolution (keep A / keep B / keep edited merge / dismiss) is logged.
- Archived KUs are tombstoned, not deleted.

#### FR-23: Queue does not block ingestion

New recordings continue to be ingested while queue items are open.

**Consequences (testable):**
- Ingestion of unrelated Topics is unaffected by an open contradiction.

### 4.7 Daily Quiz — Scheduling & Generation

**Description:** Once per day the system selects the KUs most due for review (FSRS), generates a Question per selected KU, and delivers the Quiz to the user's channel one question at a time. Realizes UJ-2.

**Functional Requirements:**

#### FR-24: Spaced-repetition scheduling

Each quiz-eligible KU has a Card with FSRS scheduling state; selection prioritizes KUs whose predicted recall has dropped toward a configured threshold.

**Consequences (testable):**
- A new KU gets a Card on first becoming quiz-eligible.
- A KU under an open contradiction or awaiting review confirmation is not selected.
- Daily selection is capped at a configured maximum number of Questions.

#### FR-25: Generate questions from KUs

The system generates one Question per selected KU, varying type across short-answer, cloze, and free recall.

**Consequences (testable):**
- A Question is answerable from the KU alone (no outside knowledge required beyond the studied material).
- The Question stores which KU and which phrasing it derives from.
- Cloze questions blank a load-bearing term, not a trivial word.

#### FR-26: Deliver one question at a time

The Quiz is delivered conversationally: one Question, wait for an Answer, respond with the Grade, then the next.

**Consequences (testable):**
- The user can stop mid-quiz and resume later the same day.
- An unfinished quiz does not corrupt scheduling (only answered Questions update Cards).

#### FR-27: Notify when the quiz is ready

The system sends a notification at the configured time with the question count.

**Consequences (testable):**
- Exactly one notification per day unless the user requests a re-send.
- If there are zero due KUs, the notification says so rather than fabricating questions.

#### FR-28: Configurable cadence and volume

Quiz time of day and maximum questions per day are user-configurable.

**Consequences (testable):**
- Changing the time takes effect the next day.
- Lowering the cap does not lose the un-quizzed KUs; they remain due.

### 4.8 Answer Grading & Retention Tracking

**Description:** The user's free-text Answer is graded semantically by an LLM against the KU; the Grade drives the FSRS update. A failing Grade also spawns a **Revisit** Action Item for that KU (§4.11, FR-41). Realizes UJ-2, UJ-4.

**Functional Requirements:**

#### FR-29: Semantic grading

The system grades each Answer as `correct`, `partial`, or `missed` by meaning, not string match, with a short rationale and the model answer.

**Consequences (testable):**
- A correct answer phrased differently from the KU is graded `correct`.
- The rationale references what was right/missing.
- The Grade records the model and prompt version.

#### FR-30: Update the schedule

Each Grade updates the KU's Card via FSRS: `correct` pushes the next review out, `partial`/`missed` pull it in.

**Consequences (testable):**
- Card stability/difficulty/due-date change per the FSRS algorithm on each graded Answer.
- Review history is retained per Card.

#### FR-31: Dispute a grade

The user can dispute any Grade in one action; disputed Questions go to the Review Queue and do not update the Card until resolved.

**Consequences (testable):**
- A disputed Question's Card is left unchanged pending resolution.
- Resolution can overturn the Grade and then apply the corrected FSRS update.

#### FR-32: Retention view

In the web app (FR-52) the user can see, per Topic, how many KUs are strong / weak / overdue.

**Consequences (testable):**
- The view is derived from Card state.
- It updates after each quiz.

### 4.9 Corrections & Manual Edits

**Description:** The user can directly correct the knowledge base — fix a wrong KU, merge two, re-topic, archive — through the same KU Operation log used by the engine. Realizes UJ-3.

**Functional Requirements:**

#### FR-33: Edit a KU

The user can edit a KU's canonical phrasing or Topics; the change is a recorded, user-attributed KU Operation.

**Consequences (testable):**
- Prior phrasing is retained in history.
- A user edit is never silently overwritten by later consolidation (consolidation treats a user-edited claim as authoritative unless a new contradiction is detected).

#### FR-34: Manual merge / split / archive

The user can merge two KUs, split one, or archive one, each as a recorded KU Operation.

**Consequences (testable):**
- Archived KUs are tombstoned and excluded from quizzes and Topic Notes.
- Sources are preserved through manual merges (union rule, FR-13).

#### FR-35: Correct a Source

The user can adjust a KU's Source span or remove an incorrect Source.

**Consequences (testable):**
- A KU must retain at least one Source or be archived.

### 4.10 Operability

**Description:** The system runs unattended as a serverless-first Azure deployment (HTTP-triggered web/API + Telegram webhook, timer-triggered daily quiz, queue-triggered pipeline worker) and must be observable and recoverable by a single technical operator. `[ASSUMPTION: Azure Functions or Container Apps, scaling to zero where possible to fit dev/test credit terms and stretch the budget; Postgres Flexible Server (Burstable) is the one always-billing component.]`

**Functional Requirements:**

#### FR-36: Unattended operation

Ingestion processing and quiz delivery happen without the user starting anything; the app recovers on its own from restarts and transient failures.

**Consequences (testable):**
- After a compute restart, cold start, or redeploy, queued Recordings are still processed and the daily quiz still fires.
- A failure in one pipeline stage for one Recording does not block other Recordings or the quiz.
- A failed stage is retried with backoff; after N attempts it is parked with a visible error, not lost.

#### FR-37: Structured logs and run history

Every pipeline run and model call is logged with enough detail to diagnose a bad extraction or merge, and retained.

**Consequences (testable):**
- Each model call logs model, prompt version, token counts, prompt hash, latency, and estimated cost.
- A given KU can be traced back through its KU Operations to the exact recording spans and model/prompt versions involved.
- Logs and run history survive redeploys (not on the ephemeral app filesystem).

#### FR-38: Usage & spend visibility

The system tracks model and transcription usage — tokens, audio-minutes, latency, estimated cost — per run and cumulatively per month, and warns before the monthly Azure budget is exhausted.

**Consequences (testable):**
- A monthly running-cost estimate is visible in the web app.
- Crossing a configurable percentage of the monthly budget pushes a Telegram warning.
- The estimate breaks down by component (transcription, each LLM stage, infrastructure).

#### FR-53: Degrade before the credit cap

When projected month-end spend would exceed the budget, the system throttles paid work — deferring new pipeline processing and the per-Topic reorganization — while keeping the daily quiz and any in-flight items running, and tells the user.

**Consequences (testable):**
- Above the configured danger threshold, newly uploaded Recordings are still accepted and stored (cheap) but their pipeline processing is held until the budget resets.
- The daily quiz and grading continue to run in the throttled state.
- The user is notified when throttling engages and when it clears.
- Held Recordings are processed automatically once the new billing period begins.

### 4.11 Action Items (To-Do List)

**Description:** Quizme maintains a single to-do list of things the user should act on outside the app. Items arrive from two origins: **Follow-up** — the user, in a Recording, said they need to check / verify / research something later (detected during extraction, FR-40); and **Revisit** — the user failed a quiz Question, so the underlying KU is queued to be re-learned (FR-41). The user works the list, and items can close themselves when the evidence shows the gap is filled. Realizes UJ-4.

**Functional Requirements:**

#### FR-39: Maintain a unified action-item list

The system keeps one list of Action Items, each with `origin` (`follow_up` | `revisit`), `status` (`open` | `snoozed` | `done` | `dismissed`), the verbatim trigger context, links to the relevant Source / KU / Topic, `trigger_count`, created/updated timestamps, and an optional revisit date.

**Consequences (testable):**
- Every Action Item is traceable to what created it: a Recording span (follow-up) or a graded Question + KU (revisit).
- `done` and `dismissed` items are retained with a resolution timestamp, not deleted.
- The list is queryable by status, origin, and Topic.

#### FR-40: Create Follow-up items from recordings

During extraction, the system detects Segments where the user expresses intent to check, verify, or research something later, and creates a `follow_up` Action Item capturing the verbatim quote and its Source `(recording_id, start, end)`.

**Consequences (testable):**
- The item stores the exact transcript text that triggered it.
- A passing remark with no real intent ("anyway, moving on") does not create an item.
- If the follow-up is clearly about an existing Topic or KU, the item is linked to it.
- Detection confidence below a configured threshold routes the item to the Review Queue for confirmation instead of the open list.

#### FR-41: Create Revisit items from quiz failures

When a Question is graded `missed`, or graded `partial` on a configured number of consecutive reviews, the system creates or refreshes a `revisit` Action Item linked to that KU and its Topic.

**Consequences (testable):**
- A `missed` grade always produces or refreshes a Revisit item for that KU.
- The item carries the KU's canonical phrasing and the model answer from the failed Question.
- A disputed Grade (FR-31) that is later overturned in the user's favor removes the Revisit item it created.

#### FR-42: Deduplicate action items

Repeated triggers for the same underlying thing update the existing Action Item rather than creating duplicates.

**Consequences (testable):**
- Follow-ups the model judges to be about the same thing (within a Topic) collapse to one item with `trigger_count` incremented and all Sources retained.
- Repeated failures of the same KU increment `trigger_count` on the one Revisit item, not create new ones.
- A dismissed item is not silently re-created by the next identical trigger within a configured cooldown; it is instead re-surfaced with a note.

#### FR-43: Surface action items to the user

The daily Telegram notification includes the count of open Action Items; the web app's To-Do page (FR-51) lists them grouped by Topic with overdue and snoozed-due items highlighted.

**Consequences (testable):**
- Open-item count appears alongside the daily quiz notification (FR-27).
- Snoozed items reappear as open on their revisit date.
- The list view shows, per item, its origin, trigger context, and links.

#### FR-44: Manage action items

The user can mark an item `done`, `dismissed`, or `snoozed` (with a revisit date) in one action, from the list or inline after a quiz question.

**Consequences (testable):**
- Each state change records a timestamp and (for snooze) the revisit date.
- Marking a Revisit item `done` does not itself change the KU's Card; only quiz answers do (AD-9).

#### FR-45: Close the loop automatically

A `revisit` item auto-resolves when its KU is subsequently answered `correct` on two consecutive reviews. The system flags a `follow_up` item as "possibly addressed" when a later Recording adds KUs to its linked Topic.

**Consequences (testable):**
- The auto-resolve is recorded with `origin=auto` on the resolution.
- A "possibly addressed" follow-up is not closed automatically — it moves to the Review Queue for the user to confirm or keep open.

**Feature-specific NFRs:**
- Action Items are tracked task state, not knowledge: creating, resolving, or deleting them never writes a KU Operation and never changes a Card.

**Notes:** `[NOTE FOR PM: the Follow-up detection threshold and the "what counts as real intent to research later" rubric need ~5 hand-labelled recordings before FR-40 can be tuned — same ground-truth exercise as FR-5.]`

### 4.12 Web Application

**Description:** The authenticated single-user web app is Quizme's primary surface — the only way recordings get in, and the place the user reviews, browses, and manages everything the pipeline produces. The daily quiz is the one thing that lives elsewhere (Telegram, §4.7). Realizes UJ-1, UJ-3, UJ-4.

**Functional Requirements:**

#### FR-46: Authenticated single-user access

The web app is reachable only by the one authorized identity; there is no signup, no second account, no anonymous access.

**Consequences (testable):**
- An unauthenticated request to any page or API route is rejected.
- Authentication is enforced at the platform edge, before application code runs.
- Losing the session requires re-authenticating; there is no "guest" view.

#### FR-47: Upload recordings

The user can upload one or more audio files in a single action, see per-file progress, and get a clear result per file (accepted / duplicate / rejected-with-reason).

**Consequences (testable):**
- Multiple files can be selected and uploaded together.
- Progress is shown during upload; a large file does not appear to hang.
- Unsupported formats and over-size files are rejected client-side and server-side with a stated reason.
- A duplicate (by content hash) is reported as such and not re-ingested (FR-1).
- Closing the tab mid-upload does not corrupt state; already-transferred files are handled per FR-1.

#### FR-48: Ingestion status & run history

The user can see what has been ingested and what is in flight: per Recording — transcription state, counts of KUs/merges/contradictions/follow-ups, and any error.

**Consequences (testable):**
- A Recording still processing shows an in-progress state that updates without a manual refresh, or with an obvious refresh control.
- A failed Recording shows the failing stage and the error, with a retry action.
- History is retained and browsable, not just the last run.

#### FR-49: Review Queue UI

The web app renders the Review Queue (§4.6) and lets the user resolve each item — contradictions, uncertain extractions, uncertain follow-ups, disputed grades — with the full context inline.

**Consequences (testable):**
- Each item type has an appropriate resolution control (keep A / keep B / edit merge / confirm / dismiss).
- Resolving an item updates the badge count and records the attributed operation (FR-22).

#### FR-50: Knowledge-base browsing

The web app provides the browse/search experience of FR-19: Topics, Topic Notes, KU search, and per-KU detail with Sources and audio playback of the source span.

**Consequences (testable):**
- From a KU the user can reach every Recording span that supports it and play it.
- From a KU the user can trigger the manual corrections of §4.9 (edit, merge, split, archive, fix Source).

#### FR-51: To-Do (Action Items) UI

The web app renders the Action Item list (§4.11) grouped by Topic, with done / dismiss / snooze controls and the trigger context for each item.

**Consequences (testable):**
- Filtering by status and origin works.
- Overdue and snoozed-due items are visually distinct.

#### FR-52: Retention & settings

The web app shows the retention view (FR-32) and exposes the user-configurable settings: quiz time and daily cap (FR-28), thresholds referenced by other FRs, and the monthly budget figure (FR-38).

**Consequences (testable):**
- A settings change persists across restarts and takes effect per the owning FR's rules.

**Feature-specific NFRs:**
- The web app is a thin surface over the application layer — it holds no business logic the pipeline and quiz flows don't also enforce.
- No durable state is written to the app's local filesystem (it is ephemeral); everything persists to managed storage.

## 5. Non-Goals, Constraints & Guardrails

### 5.1 Non-Goals

- **Not** validating claims against the internet in v1. Deferred to v2 as an advisory layer that never auto-overwrites a KU. `[NOTE FOR PM: user confirmed deferral; keep the KU schema and Review Queue ready for it.]`
- **Not** building a concept knowledge-graph (e.g. cognee) in v1. Flat KUs + embeddings + Topic tags + a lightweight link table are the v1 model; graph structure is added only if retrieval quality demonstrably falls short.
- **Not** a multi-user or shareable product. The web app authenticates one identity; no signup, no accounts, no collaboration, no sharing links.
- **Not** a native mobile app. The web app is responsive and usable from a phone browser; the daily quiz is a Telegram bot. No App Store presence, no offline mobile client.
- **Not** a general note-taking or document-import tool. Input is the user's own study audio, uploaded manually.
- **Not** real-time transcription or live capture. Recordings are processed after the fact.
- **Not** a diarization / multi-speaker product. `[ASSUMPTION: recordings are the user speaking alone; basic single-speaker handling only.]`
- **Not** a general task manager or GTD system. Action Items (§4.11) exist only to serve learning — research follow-ups the user dictated and knowledge gaps the quiz exposed. No projects, sub-tasks, priorities, or arbitrary user-created tasks.
- **Not** integrated with external task or calendar apps (Apple Reminders, Todoist, Google Calendar) in v1. `[ASSUMPTION: the to-do list lives inside Quizme only — revisit for v1.1.]`

### 5.2 Constraints & Guardrails

**Hosting**
- Quizme is deployed to **Microsoft Azure**, region **Southeast Asia** (Singapore — note: the AWS-style code `ap-southeast-1` is not an Azure region name), in the user's own subscription: serverless compute (Azure Functions / Container Apps), Azure Database for PostgreSQL Flexible Server (Burstable), Azure Blob Storage, Azure Storage Queue, Azure AI Foundry (chat), Azure AI Speech (transcription — Whisper via Azure OpenAI is not offered in Southeast Asia), Key Vault.
- Compute is **serverless-first and scales to zero** where the workload allows (HTTP web/API, Telegram webhook, timers, queue worker). Postgres is the one component that bills continuously.
- All compute filesystems are ephemeral: **all durable state lives in managed Postgres and Blob Storage** (AD-17).

**Funding & its constraints (Visual Studio / MCT subscription credit)**
- The Azure credit is the **Visual Studio Enterprise (MCT) monthly benefit — $150/month.** At the ~$55–100/month running estimate below, that leaves meaningful headroom even with a top-tier model on every stage.
- These credits are **for individual dev/test use, not production workloads.** Microsoft may suspend compute it judges to be production, and historically suspends any single instance running continuously past ~120 hours. **This is why the deployment is serverless / scale-to-zero** — it keeps compute intermittent and within the spirit of the terms. It is still a grey area for a personally-used "production" app; the user accepts that risk knowingly. A pay-as-you-go subscription (paying ~$60–90/month) is the fully-compliant alternative if it ever matters.
- The credit is a **hard spending cap**: when it is exhausted, Azure **disables the subscription's services for the rest of the billing period** — Quizme goes offline until the 1st, it does not silently run up a bill. **This makes FR-53 (degrade before the cap) a real requirement, not an optimisation.**

**Privacy**
- AI inference runs on **Azure AI Foundry / Azure AI Speech deployments in the user's own Azure tenant** — not OpenAI's or Anthropic's public consumer APIs. Audio, Transcripts, Knowledge Units, and Topic Notes are stored only in the user's Azure resources.
- **PROVISIONED (2026-09-06), with two deviations from the earlier plan:**
  - **No Regional/DataZone chat deployment.** In Southeast Asia the top chat models offer only `GlobalStandard` or PTU, and on this VS/MCT subscription **`gpt-4.1` / `gpt-5.2` / `gpt-5.4` have zero default quota** (a quota-increase request is required). `DataZoneStandard` deployments were created but did not resolve at the endpoint. → **v1 runs `gpt-5-mini` on `GlobalStandard`** (deployment name `chat`), and `text-embedding-3-small` on `GlobalStandard` (`embed`). GlobalStandard means inference may be **processed in any Azure region** (data at rest stays in the resource). Transcription (**Azure AI Speech**) *is* region-pinned to Southeast Asia — that part holds.
  - **Path to close both:** submit an Azure OpenAI quota-increase request for a top-tier model on `DataZoneStandard`; when granted, either flip `[llm].default_deployment` or point only the consolidation + grade stages at it via `[llm.stages]` (AD-8). `gpt-5-mini` stays the default for the high-volume stages — good for the budget.
- **One accepted exception: quiz delivery.** Generated Questions, model answers, and the user's typed Answers transit Telegram's servers. This exposes the substance of individual Knowledge Units *as they are quizzed*. It does **not** expose raw audio, Transcripts, Sources, Topic Notes, the Review Queue, or the knowledge base as a whole.
- The web app is reachable on the public internet but gated by **App Service / Functions built-in "Easy Auth"** (Entra ID) restricted to the single authorized identity (FR-46).

**Cost**
- The running cost must stay **within the $150/month credit.** Serverless-first estimate at ~1–1.5 hours of audio/day: Postgres ~$15–20, Blob/Queue ~$2, Functions/Container Apps ~$0–10 (mostly within free grants at this volume), transcription (AI Speech) ~$10–15, LLM ~$25–55 with a top-tier model on every stage → **~$55–100/month**, comfortably under $150. The per-stage model override (relevance filter + follow-up detection → cheaper model) is the first dial if audio volume grows.
- **Credit-lapse must not be catastrophic.** The knowledge base is exportable on demand (Postgres dump + Blob manifest), and every model / storage boundary is behind a port with a documented local implementation (Ollama + local whisper + SQLite) so the system can be moved back to the user's Mac (AD-18). `[NOTE FOR PM: deliberate hedge against the credit being temporary or capped — see §6.2.]`

**Quality**
- With capable Foundry models on every stage, the judgment-heavy jobs (contradiction detection, answer grading) are expected to be solid. The Review Queue (§4.6) and grade dispute (FR-31) remain the safety nets. Consolidation still errs toward **not merging when unsure** (an over-merge loses information; a missed merge is cleaned up later by FR-16 or a manual merge) — this is defense-in-depth, not a model-capability workaround.
- Model behavior is validated against a small eval set built from hand-labelled recordings (§8 Open Q 3) before and after v1.

## 6. MVP Scope

### 6.1 In Scope

- Azure deployment in Southeast Asia: serverless compute (Functions / Container Apps, scale-to-zero), managed Postgres + pgvector, Blob Storage, Storage Queue, Key Vault + Managed Identity, one Foundry chat deployment + Azure AI Speech for transcription (§5.2).
- Web app: authenticated single-user access, upload, ingestion status/history, Review Queue UI, KB browsing with audio playback, To-Do UI, retention & settings (FR-46–FR-52).
- Manual upload ingestion, immutable Blob storage, dedup on content hash (FR-1–FR-4).
- Azure AI Speech transcription with word/segment timestamps (FR-3).
- Foundry LLM inference for every stage — filtering, extraction, consolidation, follow-up detection, question generation, grading, note regeneration.
- LLM relevance filtering / segmentation (FR-5–FR-7).
- LLM atomic KU extraction with Sources (FR-8–FR-10).
- Consolidation Engine: scoped semantic dedup, elaboration, contradiction flagging, append-only KU Operation log (FR-11–FR-15).
- Knowledge base as a log projection; regenerated Topic Notes; browse/search; full rebuild (FR-17–FR-20).
- Unified Review Queue (FR-21–FR-23).
- Daily FSRS-scheduled quiz on Telegram, question generation, one-at-a-time delivery, notification (FR-24–FR-28).
- Semantic grading, FSRS updates, grade dispute, retention view (FR-29–FR-32).
- Manual corrections through the KU Operation log (FR-33–FR-35).
- Unattended operation, retained logs & run history, spend tracking with budget warning, degrade-before-cap throttling (FR-36–FR-38, FR-53).
- Action Items: Follow-up extraction, Revisit items from quiz failures, dedup, list management, daily-notification count, `correct`×2 auto-resolve (FR-39–FR-44, and the auto-resolve half of FR-45).
- On-demand export of the knowledge base (Postgres dump + Blob manifest) — the credit-lapse hedge (§5.2).

### 6.2 Out of Scope for MVP

- Internet fact-validation (v2). Load-bearing — revisit once the ingestion→quiz loop is proven. `[NOTE FOR PM]`
- Per-Topic periodic reorganization (FR-16) — desirable early but can trail the first release by weeks; ship the ingest-time consolidation first.
- Concept knowledge-graph / multi-hop retrieval (v2+).
- Multi-language transcription (v2).
- Speaker diarization (v2, only if recordings start including others).
- Infrastructure-as-code for the full Azure estate, blue/green deploys, multi-region, and automated DB failover (v1.1+ — v1 provisions resources with scripts/portal and relies on Azure's managed backups).
- A **fully-local deployment** (Ollama + local whisper + SQLite on the user's Mac). The adapter seams and the export in §6.1 make this possible; actually building and testing that deployment is deferred until/unless Azure credits lapse. `[NOTE FOR PM: this is the documented exit, not a shipped feature.]`
- Weekly/periodic digest emails (nice-to-have, v1.1).
- Action Items: the "possibly addressed" detection for Follow-ups (second half of FR-45) — v1.1. Also external task/calendar sync, recurring items, and priority ordering (v2).
- The quiz in the web app (Telegram only for v1).

## 7. Success Metrics

**Primary**
- **SM-1: Daily quiz completion.** The user completes the daily quiz on ≥ 5 of 7 days, sustained over 4+ weeks. Validates FR-24–FR-30. *This is the make-or-break metric — the loop only works if the habit holds.*
- **SM-2: Knowledge base coherence.** After 100+ recordings, a manual audit of a random 50-KU sample finds ≤ 10% that are duplicates, contradictions missed, or wrongly merged. Validates FR-11–FR-16.

**Secondary**
- **SM-3: Extraction usefulness.** ≥ 70% of extracted KUs are judged "worth being quizzed on" by the user in a spot review. Validates FR-8.
- **SM-4: Filter precision.** Manual review of 10 recordings finds < 15% of `study` Segment content is actually noise, and < 5% of real study content was dropped as noise. Validates FR-5.
- **SM-5: Grading trust.** Grade dispute rate < 5% of graded answers, and ≥ 80% of disputes resolve in the user's favor when raised. Validates FR-29.
- **SM-6: Action items get resolved.** Median time-to-resolution for an Action Item is under 3 weeks, and open items older than 60 days stay below 20% of the list. Validates FR-39–FR-45. *A to-do list that only grows is a failed feature.*
- **SM-7: Follow-up precision.** In a spot review of 20 detected Follow-ups, ≥ 75% represent a real intent the user recognizes as worth tracking. Validates FR-40.
- **SM-8: Runs within budget.** Total monthly Azure spend stays at or below the $150 credit for every month of normal use — and ideally below a ~$120 soft ceiling so a heavier month has slack. Validates FR-38, FR-53, §5.2.

**Counter-metrics (do not optimize)**
- **SM-C1: KU volume.** Total KU count must *not* be maximized — inflating it by keeping weak or near-duplicate units games SM-3 and buries SM-2. Counterbalances SM-3.
- **SM-C2: Questions per day.** Do *not* raise the daily cap to look thorough; an overlong quiz kills SM-1. Counterbalances SM-1.
- **SM-C3: "Correct" rate.** A high quiz score is not a goal; a lenient grader that inflates `correct` destroys the retention signal. Counterbalances SM-5.
- **SM-C4: Action-item creation rate.** Do *not* treat more detected Follow-ups as better — a trigger-happy detector floods the list and destroys SM-6. Counterbalances SM-7.

## 8. Open Questions

1. ~~**Delivery surface**~~ — **RESOLVED: daily quiz on Telegram; everything else in the web app** (§4.12). The privacy trade-off (Questions and Answers transit Telegram; nothing else does) is accepted — see §5.2. Moving the quiz into the web app later touches only the delivery adapter.
2. ~~**How does audio reach the system**~~ — **RESOLVED: manual upload through the web app** (FR-47). No device sync, no folder watch.
3. **What counts as "study-relevant"** — needs a written rubric with examples before FR-5 can be tuned. Hand-label ~5 recordings as ground truth, and extend that set into an eval for the Foundry model on consolidation adjudication and grading; run it before locking the model choice and again after v1.
4. **When does a KU become quiz-eligible** — immediately on `create`, or only after surviving one consolidation pass, or only after the user has seen it once? Affects FR-24.
5. ~~**Azure credit type**~~ — **RESOLVED: Visual Studio Enterprise (MCT) credit, $150/month.** Dev/test-only terms, hard spending cap (overrun → subscription disabled until next period). Drives serverless-first deployment (§5.2) and FR-53.
6. **Contradiction suppression** — while a contradiction is open, suppress both KUs from quizzes (safer) or keep quizzing the older one (more continuity)? FR-15 default is suppress; confirm.
7. **Retention of raw audio** — keep every Recording forever, or age out the Blob after N months once Transcripts are stable (Blob lifecycle tiering could also just move it to cool/archive storage cheaply)? FR-2/FR-20 currently assume forever.
8. **What counts as a real Follow-up** — the line between "I wonder about X" (skip) and "I need to check X" (track) needs a written rubric with examples. Hand-label ~5 recordings for ground truth (FR-40).
9. **External to-do sync** — should Action Items push to Apple Reminders / a calendar so they surface where the user already looks? Assumed no for v1; revisit for v1.1.
10. **Consecutive-`partial` threshold** — how many consecutive `partial` grades on a KU should spawn a Revisit item (FR-41)? Default assumption: 2.
11. ~~**Azure region**~~ — **RESOLVED: Southeast Asia (Singapore).** Foundry chat models are available there; Azure OpenAI Whisper is not (→ use Azure AI Speech, which is).
12. ~~**Web auth mechanism**~~ — **RESOLVED: Easy Auth** (App Service / Functions built-in auth, Entra ID), locked to one identity via "assignment required" + a principal check in middleware (FR-46).
13. ~~**Chat model in Southeast Asia**~~ — **PARTLY RESOLVED.** Provisioned on `gpt-5-mini` / `GlobalStandard` (§5.2) because the top-tier models have **zero default quota** on this subscription and DataZone deployments did not resolve. **Open sub-task:** submit an Azure OpenAI quota-increase request for `gpt-5.2` (or `gpt-4.1`) on `DataZoneStandard` — that both raises quality for the judgement stages and restores in-geo processing.
14. **Dev/test terms risk** — the VS credit is not licensed for production. Serverless-first mitigates but does not eliminate this. Decide whether to accept the grey area for a personal app or move to pay-as-you-go (~$60–90/mo) before any real reliance.

## 9. Assumptions Index

- §0, §2.2 — Single user; the web app authenticates exactly one identity.
- §0, §5.2 — **DECIDED:** hosted on Azure in **Southeast Asia**, serverless-first (Functions / Container Apps), PostgreSQL Flexible Server, Blob, AI Foundry (chat), AI Speech (STT), Key Vault — in the user's own subscription.
- §0, §5.2 — **DECIDED:** funded by the Visual Studio Enterprise (MCT) credit, $150/month. Dev/test-only terms; hard cap → subscription disables on overrun. Serverless-first and FR-53 exist because of this.
- §0, §4.1 — **DECIDED:** recordings enter only by manual upload through the web app; no folder watch or device sync.
- §4.1 — Recordings are m4a/mp3/wav exported from Voice Memos; per-file size cap configured.
- §4.1 — Transcription uses Azure AI Speech (Whisper model), available in Southeast Asia; Azure OpenAI Whisper is not in that region.
- §4.1 — English only for v1.
- §4.10 — Serverless compute scaling to zero where possible; Postgres is the one always-billing component; the daily quiz is timer-triggered.
- §5.1 / §5.2 — **DECIDED:** the daily quiz is a Telegram bot; everything else is in the web app. Questions and Answers transit Telegram; no other data does.
- §5.1 — Recordings are single-speaker (the user); no diarization in v1.
- §5.1 — The to-do list lives inside Quizme only; no external task/calendar integration in v1.
- §5.2 — **DECIDED (top model everywhere):** a top-tier Foundry model serves every LLM stage; high-volume low-judgment stages can be downgraded per-stage in config if the budget tightens.
- §5.2 — All inference is via Foundry / AI Speech deployments in the user's Azure tenant; no third-party consumer model API.
- §5.2 — **PROVISIONED:** chat = `gpt-5-mini` / GlobalStandard, embeddings = `text-embedding-3-small` / GlobalStandard (top-tier quota is 0 on this subscription; DataZone didn't resolve). GlobalStandard → inference may be processed outside Singapore. Transcription (Azure AI Speech) is region-pinned. Quota request for DataZone top-tier is the path to close both gaps.
- §5.2 — Running cost must stay within the monthly credit; the system tracks spend, warns, and throttles paid work before the hard cap (FR-38, FR-53).
- §5.2 — Web auth is Easy Auth (Entra), locked to one identity.
- §5.2, §6.2 — A fully-local deployment (Ollama + local whisper + SQLite) is the documented exit for credit-lapse; the KB is exportable on demand; it is not built in v1.
- §4.11 — A `missed` grade always spawns a Revisit item; the consecutive-`partial` threshold defaults to 2.
- §6.2 — v1 relies on Azure's managed backups for Postgres and Blob; no custom DR automation.
