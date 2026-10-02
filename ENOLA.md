# Enola — project reference

A single document describing what Enola is, how it is built, what works, what does not, and the rules that constrain changes to it. Written to be read as context rather than as a tutorial.

**Last updated:** 1 October 2026.

---

## 1. What Enola is

A personal AI assistant web app for one person: **Faizan Raza**, a final-year CS student at FAST-NUCES Karachi (graduating 2027), job hunting for junior software engineering roles — remote preferred, onsite Karachi acceptable. Timezone Asia/Karachi (UTC+5).

Enola holds his context — people, tasks, job applications, coursework, finances, projects, documents, email — and acts on it.

**What it is not:** a product, a portfolio piece, a client deliverable, or multi-tenant. One user, one machine. Usefulness to that one person beats polish for an audience. There is no sign-up flow, no marketing page, no sharing, no team features.

**The defining idea:** Enola is an agent, not a CRUD app with a chatbot attached. It reads and writes real data, runs scheduled work in the background, and **pauses to ask permission before anything irreversible**. The UI exists to make an agent's behaviour legible — what it did, what it is about to do, why, and what it believes about its owner.

---

## 2. Current state

Working and in daily use. Roughly **9,300 lines of Python** and **6,900 lines of TypeScript** (excluding generated files), **67 tests**, 30 database tables, 4 migrations.

### Built and wired to real data

| Area | State |
|---|---|
| Dashboard, Tasks, People, Person, Jobs, Job detail, Log, Memory, Approvals, Chat | Live |
| Academics — courses, deadlines, materials, FYP, course-scoped chat | Live |
| Finance — expenses, income, transfers, splits, partial settlements | Live |
| Projects, Self-learning | Live |
| Email — IMAP read and triage, draft-and-approve sending | Live |
| Job discovery — three keyless remote boards, daily | Live |
| Approval gate, memory layer, scheduler and outbox | Live |
| Voice — push-to-talk and spoken replies | Live |

**No screen is a mock.** `web/src/screens/scaffold/` no longer exists.

### Not built

- **Test prep** (question generation from course materials) — the Academics tab says so plainly rather than faking it
- **Hosting** — runs locally only; see §13
- **Mobile push** — notifications are in-app and email-to-self
- **CI/CD, metrics, tracing, error tracking, backups**
- **Login rate limiting** — a blocker for any public deployment
- **Past-dated task completion** — see §12

---

## 3. Architecture

```
React SPA (Vite, TypeScript, CSS Modules)
        │  same-origin; Vite proxies /api in dev
        ▼
FastAPI  ──  LangGraph agent core  ──  Google Gemini
        │
        ▼
Postgres + pgvector  ◄── APScheduler worker (separate process)
        │
        ├─ Gmail IMAP (read) / SMTP (send)
        └─ Job boards (Remotive, RemoteOK, Arbeitnow, JSearch)
```

**The worker never shares in-process state with the API.** They communicate only through Postgres, so they can run on different machines.

### Layout

```
enola/
  api/       FastAPI: main.py, routers/, crud.py (one generic CRUD router pattern)
  core/      config, db, enums, models/, schemas/, services/, repository.py,
             storage.py, mailer.py, auth.py
  agent/     registry.py (risk classification = the gate), graph.py (LangGraph),
             service.py, models.py (provider + roles), tools/, memory/, prompts/
  workers/   scheduler.py, jobs/ (reminders, nudges, daily brief, discovery), outbox.py
  ingest/    documents.py, embeddings.py, mail.py, jobs_sources/
  scripts/   seed, demo_held, cache_check, export_openapi, export_enums, dev
web/
  src/       shell/ (nav, chat rail, command palette, splash), screens/, ui/, data/,
             lib/, theme/
```

Python lives under an `enola/` package rather than top-level `api/`, `core/` etc., to avoid generic top-level package names.

---

## 4. The approval gate — the central mechanism

**Rule: propose, never act unattended.** Anything writing outside Enola's own database halts and waits for a human click. There is no autonomous-send path, not behind a flag, not for voice.

Every tool declares a risk level **in the registry, never in the tool body**:

| Level | Behaviour | Count |
|---|---|---|
| `SAFE` | runs freely | 11 |
| `WRITE_LOCAL` | runs freely, written to `activity_log` | 8 |
| `EXTERNAL` | **halts → Held** | 2 |
| `DESTRUCTIVE` | **halts → Held** | 1 |
| `UNCLASSIFIED` | **halts → Held** — the default when no risk is given | — |

A tool registered with no risk level is gated. `ToolRegistry.is_gated()` also returns `True` for an unknown tool name: nothing runs on the strength of a name alone.

### How a Held action flows

1. The agent picks a tool; the graph consults the registry **before** executing it.
2. If gated, the graph calls LangGraph's `interrupt()`. The run **pauses**, an `approval_request` row is written with `state='held'`, and the graph state is checkpointed to Postgres.
3. The user sees the exact payload — recipient, subject, body — and may edit, approve or reject.
4. On approval the run **resumes from the checkpoint** and the tool executes. On rejection it aborts; the rejection reason is fed back as a tool result and the agent is told not to retry.

The paused state is called **"Held"** everywhere — database, API, UI, and conversation. One word for one concept.

Guarded by seven tests in `tests/test_approval_gate.py`, four of which are mandatory: the side effect does not occur before approval; resume preserves the original arguments and context and fires exactly once; rejection aborts cleanly with no partial writes; and an unclassified tool defaults to gated.

---

## 5. Data model

The spine that makes screens into views rather than separate apps:

```
Person ──┬─ interaction (touchpoint log, last_contacted_at)
         ├─ referral ──→ Application ──→ Company
         └─ transaction_split ──→ Transaction

Task ──→ task_link (polymorphic: Project | Course | Application | LearningGoal)

Document ──→ document_chunk (pgvector) ──→ attaches to any entity
```

Tables by group: **people** (`person`, `person_tag`, `interaction`) · **tasks** (`task`, `task_link`) · **jobs** (`company`, `application`, `application_event`, `job_posting`) · **academics** (`course`, `assessment`, `fyp_milestone`) · **finance** (`account`, `transaction`, `category`, `transaction_split`, `settlement`, `settlement_allocation`) · **projects** (`project`, `project_snapshot`) · **learning** (`learning_goal`, `learning_resource`) · **documents** (`document`, `document_chunk`) · **infra** (`memory_fact`, `approval_request`, `notification`, `activity_log`, `user_session`).

Two deliberate choices worth knowing:

- **`assessment` rows also write a `task` row.** A quiz deadline *is* a task underneath, so one reminder pipeline covers coursework and job follow-ups alike, and a deadline surfaces in the morning brief next to a recruiter nudge rather than hiding in the Academics tab.
- **Money balances are derived, never stored.** `settlement` plus `settlement_allocation` means a repayment can be partial, and can exist without being tied to any single expense — which is how paying someone back actually works.

---

## 6. The agent

**Provider:** Google Gemini. Both roles currently run `gemini-3.5-flash-lite`.

Two roles, each its own env var, both falling back to one default:

- `AGENT` — the chat loop (`ENOLA_AGENT_MODEL`)
- `UTILITY` — brief prose, classification, mail triage, summaries (`ENOLA_UTILITY_MODEL`)

An Anthropic path exists behind `ENOLA_MODEL_PROVIDER` and still works; prompt caching (`cache_control` on the stable prefix) is Anthropic-specific and inert on Gemini.

**Measured free-tier reality, not documentation:** Google no longer publishes static rate limits — they are per-project and visible only in AI Studio, which is why third-party tables disagree. On this project's key, `gemini-3.5-flash` allows **5 requests per minute**, and one chat turn spends two to four on tool calls, so the agent loop was unusable there. `gemini-3.5-flash-lite` ran 14 requests in 11 seconds without complaint, binds all 22 tools with no schema error, and picked the right tool in 5 of 5 realistic prompts. `gemini-2.5-*` models are listed by the API but return `ModelNotFound` for this key.

`max_retries` is deliberately **2**, not 5: the client retries a 429 quota error the same way it retries a transient 503, so a generous retry count spends six requests of quota failing to make one call.

**The loop short-circuits identical repeats.** A weaker model will sometimes call the same read tool two or three times in one turn; the gate hands back the result it already has with "do not call it again" rather than re-running the tool. Different arguments still run.

**System prompt** lives in `enola/agent/prompts/system.py` in two blocks: a stable cacheable block (the operating manual, tool guide, finance rules, worked examples) and a volatile block (memory facts, scope, today's date).

---

## 7. Memory

Three kinds, deliberately separate:

- **Structured** — the domain tables. The bulk of what Enola knows.
- **Profile facts** — `memory_fact` rows: durable statements about the owner, written by the agent via the `remember` tool, visible and editable on the Memory screen so a wrong belief can be corrected.
- **Semantic** — `document_chunk` with pgvector. Retrieval is **scoped**: the Academics chat for a course reaches that course's materials only, not finance and not other courses.

Embeddings default to a deterministic local hash (`ENOLA_EMBEDDER=hash`), which keeps the app and tests working without a key. Set `voyage` with `VOYAGE_API_KEY` for real semantic retrieval.

---

## 8. The worker, reminders and notifications

A separate process (`python -m enola.workers.scheduler`). Six jobs:

| Job | Cadence |
|---|---|
| reminders | every 15 min |
| follow-up nudges | hourly |
| daily brief | 07:00 |
| job discovery | 07:20 |
| deliver outbox | every 1 min |
| purge sessions | 03:30 |

Jobs never deliver anything themselves. They `enqueue()` rows into a `notification` outbox — **one row per channel**, deduplicated on `(dedupe_key, channel)` — and `deliver_due()` hands them to channels. Adding web push later is one new class and one line in `CHANNELS`.

Four reminder kinds: `TASK_DUE`, `ACADEMIC_DEADLINE` (both from open tasks due within 24h, one per task per local day), `THREAD_QUIET` (an application with no activity for 3 days), `CONTACT_COLD` (a person whose `cadence_days` has lapsed). `CONTACT_COLD` is **deliberately excluded** from the dashboard reminder list — cold contacts live under "Going cold" and on People, and showing them twice overwhelmed the dashboard.

**Two behaviours worth knowing:**

- **Reminders catch up; the daily brief does not.** Reminders query current state, so a reminder missed while the worker was off appears within 15 minutes of starting it. The brief is a cron moment with **no misfire grace** — if the worker is not running at 07:00, that day's brief is silently skipped. A one-line fix (`misfire_grace_time`) remains unmade.
- **A task with no due date is never reminded**, and a person with no `cadence_days` never goes cold. Both fields are nullable with no default.

---

## 9. Email

**Gmail over IMAP with a Google app password** — chosen over Gmail API + OAuth because a personal Cloud project with sensitive scopes left in Testing status expires refresh tokens roughly weekly, which would kill the habit.

**Reading is read-only by construction.** `enola/ingest/mail.py` opens every mailbox with `readonly=True` and contains no code path that appends, flags, moves or deletes. Nothing about mail is persisted; the API caches results in-process for 3 minutes.

**Triage is two passes, in this order for a reason.** Headers are free (`List-Unsubscribe`, `Precedence: bulk`, no-reply senders, transactional phrases) and remove ~90% of an inbox, so the model only ever classifies the handful that survive. With no model available the heuristic answer stands and the screen still works.

**Sending is real and gated.** `send_email` is `EXTERNAL`, so it always Holds first; once approved the message genuinely leaves via `enola/core/mailer.py`, the single SMTP transport shared with the notification outbox. It takes `reply_to_message_id` (surfaced by `read_email_thread`) so a reply threads in Gmail instead of starting a new conversation.

**Ordering that matters and is tested:** send first, log the interaction second. An interaction recorded for a message that never left would make the owner believe they had replied.

There is deliberately **no draft or send endpoint on the mail router** — a direct route would be a way around the gate.

---

## 10. Job discovery

Sources behind one `JobSource` protocol in `enola/ingest/jobs_sources/`, so a rotting source can be disabled without touching the rest. A source that cannot run reports *why* and is skipped; a source that fails is logged and skipped without costing the others their results.

| Source | Key | Covers |
|---|---|---|
| Remotive, RemoteOK, Arbeitnow | none | remote — works today |
| JSearch (RapidAPI, `letscrape-6bRBa3QguO5`) | free key | onsite Karachi **and** remote; dormant until `JSEARCH_API_KEY` is set |

Runs daily at 07:20. Dedupes on normalised `(company, title)`, skips anything matching an existing application, scores the match, and inserts with `status=discovered`. Below-threshold postings are filed as `dismissed` rather than dropped, so the threshold stays reviewable.

**Scoring is a transparent heuristic, not a model call** (`enola/core/services/job_match.py`): it costs nothing over a hundred postings a day, and every score carries a `match_reason` the owner can read and disagree with. Remote is weighted above onsite but **onsite is never filtered out**; UTC+5 overlap counts for remote roles, Karachi-first for onsite ones.

---

## 11. Design system

**Dark-first, with a light theme and one warm `[data-paper="1"]` mode used only by Academics.** All colour lives in `web/src/theme/tokens.css`; no component holds a hex value.

- **Semantic colours are fixed app-wide.** `--oc` means **Held** and nothing else, ever. `--gr` finished, `--rd` overdue and destructive.
- **Each screen overrides exactly one token, `--accent`** — cyan for Dashboard/Chat, indigo Jobs, rose People, green Tasks, teal Finance, paper-ink Academics, violet Projects, amber Self-learning, neutral for Memory and Log.
- **Chat is a toggleable right-hand rail plus a ⌘K/Ctrl+K command palette**, not a tab. A persistent shell owns nav, rail, palette and splash; screens mount inside it.
- Every screen must work at **400px** — Enola is used from a phone via a home-screen shortcut.

Two design passes in Sept–Oct 2026 fixed a measured hierarchy problem: 140 of 167 type declarations sat within 2px of each other, and the app separated things with 111 border declarations against 48 background ones. The fix was to use the existing scales properly — larger titles, real spacing rhythm, surface layering instead of borders, and visible per-screen accents — not to add colours.

---

## 12. Conventions that bind changes

1. **Propose, never act unattended.** No tool may bypass the registry.
2. The four mandatory gate tests must pass after every change. If a change breaks one, the change is wrong.
3. **Never put realistic-looking data in a system prompt.** Use placeholders (`<person>`, `<course>`, `<n>`). See §15.
4. No hardcoded `localhost`; all secrets from environment variables; `.env` is never committed.
5. Typed end to end — `mypy enola` clean, TypeScript `strict`, no `any`.
6. Thin routers, logic in services, one generic CRUD pattern (`enola/api/crud.py`, `enola/core/repository.py`).
7. TypeScript types and enums are **generated** from the OpenAPI schema, never hand-maintained.
8. Front end uses tokens only — no hex, no magic pixel values, no inline `style` except CSS-custom-property injection for genuinely dynamic values.
9. Never edit an applied migration; add a new one.
10. Abstract on the second or third repetition, not the first.

---

## 13. Running it

```bash
./enola.sh          # Git Bash / WSL
enola.cmd           # PowerShell, cmd, or double-click
enola               # any shell, with the venv active
```

One command starts Postgres (docker compose), waits for it to accept connections, applies migrations, then runs the API, the worker and the Vite dev server in one terminal with prefixed output, and opens the browser. Ctrl+C stops all three and sweeps their process trees.

Flags: `--no-web`, `--no-worker`, `--no-reload`, `--no-open`, `--no-db`.

- A native Postgres owns 5432, so the compose container maps to **5433** (`POSTGRES_HOST_PORT`).
- Python **3.14**, venv at `.venv`. Web on **5173**, API on **8000**.
- `python -m enola.scripts.seed --reset` wipes and reseeds; `--wipe` empties and stops.
- Local alias: `http://enola.localhost:5173` works with no setup (`*.localhost` resolves to loopback). Avoid `.local` (mDNS, slow on Windows) and `.dev` (HSTS-preloaded, forces HTTPS).

**Hosting is deferred.** The intended shape when it happens: Compute Engine `e2-micro` (not Cloud Run — it scales to zero and freezes the worker's background thread), with Tailscale so there is no public port, no domain, no certificate work, and the phone reaches it from anywhere. Login rate limiting must exist before any public exposure.

---

## 14. Open decisions and known gaps

- **Login has no rate limiting.** One password, unlimited guesses. Blocks public hosting.
- **The daily brief has no misfire grace** — skipped entirely on days the worker is not running at 07:00.
- **Past dates cannot be recorded in several places.** Tasks parse backwards now (`yesterday`, `3 days ago`, `last friday`) and have a date picker, but `completed_at` is absent from `TaskBase`, so "I finished this on Monday" is unexpressible from any client. The finance and interaction agent tools hardcode `datetime.now(UTC)`, so logging a past expense via chat silently records today.
- **No agent tools for courses, assessments, applications or companies** — those can only be created through the UI.
- **Drafts are not stored locally.** A reply goes straight to Approvals; there is no iterate-before-holding step.
- **Test prep** has no question-generation endpoint.
- **Prompt caching** is Anthropic-only and inert on the current provider.

---

## 15. Things learned the hard way

Recorded because each was non-obvious and each cost real time.

- **Realistic example data in a system prompt becomes hallucination fuel.** Against a completely empty database, Enola reported a quiz and a course that did not exist. Both appeared verbatim in the prompt's worked examples, which had been written using the seed data's own proper nouns. A weak model reads concrete examples as context. Every example is now a placeholder, and a test fails if a course-code shape or any of those names returns.
- **Substring matching on short words is a trap.** Job scoring treated "Tier III Service Desk Engineer" and "AI agent engineer" as junior-friendly because `"i"` matched inside them. Word-boundary matching now, with a regression test naming both titles.
- **A test suite that can reach a live SMTP server will eventually send real email.** It did — four of them — the moment `ENOLA_SMTP_FROM` was filled in. An autouse fixture now blanks the SMTP host for every test.
- **Terminating a supervisor leaves its worker.** The dev launcher killed uvicorn's reloader and orphaned the child holding port 8000. It now sweeps the whole process tree.
- **Things that look implemented are often not wired.** Sound cues fired at gain 0.035 — inaudible. A "reply arrived" cue was missing entirely. The sidebar's ⌘K chip was a styled label wired to nothing, and the label said ⌘ on a Windows machine. None of these are visible to tests; only use finds them.
- **Measure the model's limits, do not read about them.** Published Gemini free-tier numbers disagree across sources because Google stopped publishing them.
