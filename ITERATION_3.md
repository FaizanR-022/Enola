# Enola — Iteration 3: close the gaps

Finish everything still mock or unbuilt. Written after checking what actually exists — two of the three gaps are much smaller than the original staging implied.

## What's actually missing

| Gap | Backend | Front end | Real work |
|---|---|---|---|
| **Academics** | Complete — `/courses`, `/assessments`, `/fyp-milestones`, `/documents?scope=`, `/chat` with `scope` | Mock | Data hooks + rewire the screen |
| **Job discovery** | `JobPosting` has `dedupe_key`, `match_score`, `match_reason`, `location_kind`, `status=discovered`. The Jobs screen already renders a Discovery feed | Done | Source adapters + a worker job |
| **Email** | Nothing | Mock | A whole subsystem — and blocked on a decision |

## Step 1 — Academics

Add the missing hooks to `web/src/data/index.ts`: `useCourses`, `useAssessments`, `useFypMilestones`, `useDocuments`, plus mutations for courses and assessments.

Rewire `screens/scaffold/Academics.tsx` onto them and move it to `screens/Academics.tsx`. Three tabs, as the mock has:

- **Courses** — list; per-course deadlines (assessments), materials (documents scoped `course:<id>`), upload, and a chat scoped to that course.
- **FYP** — milestones with states, research notes.
- **Prep** — there is no question-generation endpoint. Say so honestly in the UI rather than faking it.

Keep the `paper` theme and serif headings. Handle empty, loading and error states the mock skips.

*Gate:* Academics renders live data; creating an assessment shows up in Tasks (the service already syncs); course-scoped chat only retrieves that course's documents; no `scaffold/mock` import remains; works at 400px.

## Step 2 — Job discovery

New `enola/ingest/jobs_sources/` behind one `JobSource` protocol, so a rotting source can be disabled without touching the rest.

**Both remote and onsite are in scope.** Remote is preferred and weighted higher; onsite Karachi is never filtered out.

| Source | Key | Covers |
|---|---|---|
| Remotive, RemoteOK, Arbeitnow | none | Remote — works today, no signup |
| JSearch (RapidAPI) | free key | **Onsite Karachi and remote.** Reads Google for Jobs, so it is the only free route to local listings. Enabled only when `JSEARCH_API_KEY` is set |

The keyless sources work immediately. Onsite coverage lights up when a free RapidAPI key is added — the adapter stays dormant and logs why when the key is absent, rather than erroring.

A worker job polls once a day, normalises each posting, computes `dedupe_key`, skips anything already in `job_posting` or matching an existing `application`, scores the match, and inserts with `status=discovered`. The existing Discovery feed picks them up with no UI change.

Scoring is a transparent heuristic with a written `match_reason` — not a model call, so it costs nothing and stays explainable:

- Skills fit against the owner's stack.
- **Remote weighted above onsite, onsite never excluded.**
- For remote: UTC+5 overlap — EU and async-first rank above US-Pacific-with-full-overlap.
- For onsite: Karachi ranks above other cities; elsewhere in Pakistan ranks above abroad.

*Gate:* the worker job inserts real postings from the keyless sources; running it twice inserts nothing the second time; a posting matching an existing application never appears; both a remote and an onsite posting can rank, with a `match_reason` a human can read.

## Step 3 — Email (IMAP)

**Decided: IMAP + a Google app password.** No OAuth, no Cloud project, no consent screen, no weekly token expiry. Enough for read and draft.

- Read via IMAP, drafts written back with IMAP `APPEND` to `[Gmail]/Drafts`.
- Triage into needs-reply / FYI / noise, thread summaries, and recruiter mail parsed into application updates.
- **Sending stays an `EXTERNAL` tool and goes to Held.** Unchanged.
- Credentials in env (`ENOLA_IMAP_*`), never committed. The screen and tools degrade honestly when unset, exactly as the agent does without a model key.

Needs from the owner before it can be tested: 2FA enabled on the Google account, an app password generated, and IMAP switched on in Gmail settings.

## Rules

Unchanged from `FABLE_PROMPT.md`: propose-never-act, no tool bypasses the registry, the four gate tests pass after every step, `mypy enola` clean, TS strict, tokens only, no editing applied migrations.
