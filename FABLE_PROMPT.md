# Build Enola — a personal agent

You are building **Enola**, a personal AI assistant web app, from an empty directory. One user, one machine. Not a product, not multi-tenant, no marketing pages, no sign-up flow.

The owner is a final-year CS student in Karachi (UTC+5), job hunting for SWE roles — remote preferred, onsite Karachi acceptable. Enola holds his personal context (people, tasks, job applications, coursework, finances, projects) and acts on it.

**Enola is an agent, not a CRUD app with a chatbot attached.** It reads and writes real data, runs scheduled work in the background, and pauses to ask permission before anything irreversible. The UI exists to make an agent's behavior legible: what it did, what it's about to do, why, and what it believes about the user.

Work through the phases in order. **Each phase has a gate. Do not begin the next phase until the current gate demonstrably passes.** A gate is not "the code looks right" — it is a command that runs and a result you can point to.

---

## Non-negotiable rules

These hold in every phase. They are the difference between Enola working and Enola looking like it works.

1. **Propose, never act unattended.** Enola drafts, queues, and notifies. Anything that writes outside its own database — sending email, posting anywhere, deleting records, bulk edits — halts and waits for a human click. There is no autonomous-send path, not even behind a flag.
2. **No tool may bypass the registry.** Risk classification lives in the tool registry, not in individual tool bodies. A tool registered without an explicit risk level defaults to **gated**, never to open.
3. **No hardcoded `localhost`.** API base URL, database URL, and allowed origins all come from config. The app will move to real hosting later; do not make that a rewrite.
4. **All secrets from environment variables.** Never commit a key. Never inline one in a source file, a notebook, or a test fixture.
5. **The worker never shares in-process state with the API.** They communicate through Postgres only. Assume they run on different machines.
6. **Real session auth from the start.** Single user, but not a `TODO: add auth` stub — assume this will eventually be reachable from the internet.
7. **Uploaded files go through a storage abstraction**, even though v1 writes to local disk.

---

## Stack

- **Backend:** Python, FastAPI, SQLAlchemy, Alembic, Pydantic
- **Agent:** LangGraph with a Postgres checkpointer (the interrupt/resume flow depends on checkpointing — do not substitute an in-memory saver)
- **Database:** Postgres with pgvector
- **Worker:** APScheduler in a separate process
- **Frontend:** React + Vite + TypeScript
- **Local infra:** docker-compose for Postgres + pgvector

---

## Engineering standards

This codebase will be maintained and extended by its owner for years. Write it for the version of him who returns in eight months having forgotten everything. Clarity and a single source of truth matter more than cleverness, and more than getting a screen on the page quickly.

### Structure

- **Typed end to end.** Python type hints everywhere, checked with mypy. TypeScript in `strict` mode. No `any`, no untyped dicts crossing a module boundary.
- **Layered, with thin routers.** Route handlers parse input, call a service, and shape the response — nothing more. Business logic lives in services; data access lives in repositories. No SQL and no domain rules inside a route handler.
- **One CRUD pattern, not ten.** There are roughly ten entity groups with near-identical create/read/update/list needs. Build a generic repository and a generic router factory once, then specialize only where an entity genuinely differs. Copy-pasting a router per entity is the single largest source of future drift in an app shaped like this one.
- **Schemas derived, not duplicated.** Pydantic models are the one definition of a shape. Generate the frontend's TypeScript types from the OpenAPI schema rather than hand-maintaining a parallel set that will silently fall out of sync.
- **No magic strings.** States, risk levels, application stages, notification kinds, and task priorities are enums shared between backend and frontend, not string literals sprinkled through both.

### Frontend

- **Primitives first.** Build a small set — Button, Card, Field, Table, Sheet, Badge, EmptyState — and compose screens from them. A screen that reaches for a raw styled `<div>` where a primitive exists is a bug.
- **Tokens only.** No hex values, no magic pixel numbers, no inline `style` attributes in screen code. Every color, space, and radius resolves to a token.
- **One data layer.** A single typed API client plus one server-state pattern for fetching, caching, and invalidation. Screens do not hand-roll `fetch` or manage their own loading booleans.
- **Held, empty, loading, and error states are part of every screen**, not an afterthought bolted on when someone notices.

### Practices

- **Structured logging** with correlation ids that tie an agent run, its tool calls, and any Held approval together. Debugging an agent without this is guesswork.
- **Consistent error handling.** One exception hierarchy, one error-response shape, one place that translates exceptions into HTTP responses.
- **Tests where they earn their keep:** the four approval-gate tests are mandatory. Beyond those, a smoke test per router and tests for the scoring, dedupe, and scheduling logic. Do not chase a coverage number.
- **Migrations are never edited after being applied.** Add a new one.
- **Docstrings on the non-obvious only.** Explain *why*, not *what*. Code that needs a comment to explain what it does should be rewritten instead.

### The counterweight

DRY is a tool, not a goal. Abstract on the **second or third** repetition, once the shape is actually known — not the first. A premature abstraction built around one example is harder to unwind than the duplication it prevented, and a solo project does not need an internal framework. When in doubt: duplicate once, abstract on the third.

---

## Repo layout

```
enola/
  api/
    main.py
    routers/          # people, tasks, jobs, approvals, chat, search, memory, log
    deps.py
  core/
    config.py         # env + secrets
    db.py
    models/           # SQLAlchemy, one module per entity group
    schemas/          # Pydantic
    storage.py        # file storage abstraction
  agent/
    graph.py          # LangGraph state machine
    registry.py       # tool registry + risk classification  ← the approval gate
    tools/
    memory/           # profile.py, retrieval.py
    prompts/
  workers/
    scheduler.py      # APScheduler entrypoint
    jobs/             # daily_brief.py, reminders.py, followup_nudge.py
    outbox.py
  ingest/
    documents.py      # chunk + embed
  web/
    src/
      shell/          # nav, chat rail, command palette, splash
      screens/
      lib/api.ts
      theme/tokens.css
  alembic/
  tests/
  docker-compose.yml
  .env.example
```

---

## Design system

A prototype lives in `design/` — `Enola.dc.html` (15 artboards) and `support.js`, extracted from `claude-design-folder.zip`.

**How to use it — read this carefully, it is easy to get wrong.** The prototype was authored in a canvas tool. It is a single 222KB file of inline-styled `<div>`s, `{{ handlebars }}` placeholders, and custom `<sc-if>` elements. It is a *picture of the intended design*, not a source file.

- **Do** read it for layout, hierarchy, spacing rhythm, component anatomy, copy tone, and the empty/loading/Held states it works through.
- **Do not** transpile, port, or mechanically convert it into React. Doing so produces exactly the inline-styled, copy-pasted, unmaintainable component tree this build must avoid.
- The tokens, type scale, shell structure, and screen inventory below are already distilled from it. Where this document and the prototype disagree, **this document wins**.
- Treat the design as structural direction, not a pixel spec. It is expected to change.

### Tokens

Define once in `web/src/theme/tokens.css` as CSS custom properties. Dark is the default; light is an override on `[data-theme="light"]`.

| Role | Dark | Light |
|---|---|---|
| `--canvas` / `--bg` | `#08090b` / `#101317` | `#dfe2e5` / `#fbfbfc` |
| `--s1` `--s2` `--s3` | `#161a1f` `#1c2127` `#232a31` | `#f3f4f6` `#eaecef` `#e1e4e8` |
| `--line` `--line2` | `#242a31` `#2f373f` | `#e2e5e9` `#ccd2d8` |
| `--tx` `--tx2` `--tx3` | `#e7eaed` `#98a1aa` `#8f989f` | `#14171a` `#596269` `#5f676e` |
| `--cy` (accent) | `#7cb8d8` | `#2a6888` |
| `--oc` `--gr` `--rd` | `#d6a250` `#7ba883` `#cf7a66` | `#85600f` `#3e6b47` `#a3452e` |

Type: Helvetica Neue for UI; **IBM Plex Mono** for small uppercase labels (10–11px, `letter-spacing: .09–.13em`); **Georgia serif** for Academics headings only.

### Theming rules

- Each screen may override **exactly one token: `--accent`**, used in its header, active nav state, and focus rings.
- Surfaces, text, and semantic colors (`--gr` success, `--rd` danger) are **fixed app-wide**. Never redefine a semantic color per screen — global surfaces render across every screen and must resolve consistently.
- Academics additionally gets `data-paper="1"`, a warm-surface mode layer. This is the **only** full mode shift in the app; that is what makes it read as a signal rather than as noise.

### Shell

A persistent shell owns navigation, the chat rail, the command palette, and the splash. **Screens mount inside the shell.** Do not build screens as independently routed pages that each own their own layout.

- **Chat rail** — toggleable right-hand panel, not a tab.
- **Command palette** — ⌘K, doubles as global search and "ask Enola".
- **Splash** — shown on boot while the dashboard loads. Click to skip. It must never hold longer than the data actually takes; no artificial timer.
- **Every screen must work at 1440px and at 400px.** The 400px case is real — the owner opens this from a phone home-screen shortcut.

---

## Domain model

The spine that makes screens into views rather than separate apps:

```
Person ──┬─ interaction (touchpoint log, last_contacted)
         ├─ referral ──→ Application ──→ Company
         └─ transaction_split ──→ Transaction

Task ──→ task_link (polymorphic: Project | Course | Application | LearningGoal)

Document ──→ document_chunk (vector) ──→ attaches to any entity
```

Tables:

- **People:** `person`, `person_tag`, `interaction`
- **Tasks:** `task`, `task_link`
- **Jobs:** `company`, `application`, `application_event`, `job_posting`
- **Academics:** `course`, `assessment`, `fyp_milestone`
- **Finance:** `account`, `transaction`, `category`, `transaction_split`
- **Projects:** `project`, `project_snapshot`
- **Learning:** `learning_goal`, `learning_resource`
- **Documents:** `document`, `document_chunk`
- **Infra:** `memory_fact`, `approval_request`, `notification`, `activity_log`

`assessment` rows (assignments, quizzes, exams) **also write into `task`** so that one reminder pipeline covers everything and academic deadlines surface in the daily brief next to job follow-ups.

---

## The approval gate — the heart of the system

This is the part most likely to be faked. It is invisible in a screenshot and easy to stub with something that returns success. Build it first, prove it with automated tests, and do not proceed on a manual click-through.

### Risk levels

| Level | Examples | Behavior |
|---|---|---|
| `SAFE` | read own DB, search web | Runs freely |
| `WRITE_LOCAL` | create task, log transaction | Runs freely, written to `activity_log` |
| `EXTERNAL` | send email, post anywhere | **Halts → Held** |
| `DESTRUCTIVE` | delete records, bulk edits | **Halts → Held** |

### Mechanics

Tools register through a decorator that records the risk level:

```python
@tool(risk=Risk.EXTERNAL)
def send_email(to: str, subject: str, body: str) -> str: ...
```

The graph node consults the registry **before** executing any tool. If the tool is gated, it calls LangGraph's `interrupt()` with a payload describing the intended action, the agent's rationale, and the full arguments, and writes an `approval_request` row with `state='held'`. The run resumes from the checkpoint when approved.

`approval_request` fields: `id`, `thread_id`, `checkpoint_id`, `tool_name`, `args` (jsonb), `rationale`, `risk`, `state` (`held` | `approved` | `rejected`), `payload_preview`, `created_at`, `resolved_at`.

### Naming

The paused state is called **"Held"** everywhere — in the database, the API, the UI, and the code. One word for one concept.

### Required tests

These must exist and pass. They are the Phase 2 gate.

1. `test_external_tool_halts` — invoking a gated tool halts the run and writes an `approval_request` with `state='held'`. The side effect does **not** occur.
2. `test_resume_preserves_context` — approving resumes from the checkpoint with the original conversation context and tool arguments intact, and the side effect then occurs exactly once.
3. `test_reject_aborts_cleanly` — rejecting ends the run without the side effect, leaves no partial writes, and records the outcome.
4. `test_unclassified_tool_defaults_to_gated` — a tool registered with **no** risk level is treated as gated. This is the test that keeps the gate from eroding six months from now.

---

## Phases

### Phase 0 — Scaffold and shell

Repo structure, `docker-compose.yml` with Postgres + pgvector, FastAPI skeleton, Alembic initialized, Vite/React/TypeScript app, design tokens, session auth, and the shell: nav, toggleable chat rail, ⌘K palette, splash.

**Gate:** `docker compose up` runs; the API serves `/health`; the web app boots; both themes render correctly; the shell navigates between placeholder screens at **1440px and 400px** with no horizontal scroll.

### Phase 1 — Data layer

Every table above. Alembic migration. A seed script with realistic content — plausible remote and Karachi SWE roles at real-sounding companies, Pakistani names in the people catalogue, plausible FAST-NUCES course names, PKR amounts, near-future dates. Realistic seed data is how layout and logic bugs become visible.

**Gate:** migration runs up and down cleanly; seed loads without error; `/health` reports the database reachable.

### Phase 2 — Agent core and approval gate

LangGraph graph with a Postgres checkpointer, the tool registry with risk classification, the `interrupt()` → Held → resume flow, and `activity_log` writes. Register two probe tools: one `SAFE`, one `EXTERNAL`.

**Gate — the critical one:** all four tests from *Required tests* above pass, run as automated tests. Not a manual click-through.

### Phase 3 — Memory

Three layers: structured (the tables), `memory_fact` rows for durable statements about the user, and pgvector semantic retrieval over `document_chunk`. Document ingestion with chunking and embedding. Retrieval is **scoped** — the Academics chat searches course documents, not finance.

**Gate:** a fact stated in one session is recalled in a fresh session and is traceable to a `memory_fact` row; a scoped retrieval query returns only in-scope chunks.

### Phase 4 — v1 screens, fully wired

Dashboard, Approvals, Tasks, People, Person, Jobs, Job detail, Log, Memory — all against real endpoints.

- **Dashboard** answers "what needs me today" in one glance without scrolling: daily brief, Held approvals, tasks due, people going cold, recent agent activity.
- **Approvals** shows each Held item's intended action, rationale, and full payload, with approve / edit / reject, and makes clear a larger task is mid-flight waiting on the user.
- **Memory** lets the user see and correct what Enola believes about them.

**Gate:** CRUD round-trips on every wired screen; the dashboard aggregates real rows; a Held item renders and resolves from the UI, resuming the underlying run.

### Phase 5 — Scheduler, outbox, reminders

Worker process with APScheduler. Scheduled jobs write to a `notification` outbox; delivery channels read from it. v1 channels: in-app badge and email-to-self. Build the outbox with **pluggable channels** so web push can be added later without a rewrite.

Three reminder kinds: task due dates, academic deadlines (via the `task` rows that `assessment` writes), and follow-up nudges for quiet recruiter threads and contacts going cold. Plus the daily brief.

**Gate:** a backdated task due date, a backdated contact cadence, and a due assessment each produce a notification that surfaces in the brief and the in-app badge.

### Phase 6 — Scaffold the remaining screens

Academics, Finance, Projects, Self-learning, Email — built as styled screens against mock data, each with TODO markers naming the endpoints it will need.

- **Academics** — course list, per-course materials and deadlines, FYP milestones, scoped chat. Georgia headings and `data-paper` warm mode.
- **Finance** — manual entry only, no bank connections ever. Accounts, transactions, tag categories (carpool, fuel, food), splits with people from the People catalogue, "who owes whom", monthly summary. PKR.
- **Projects** — registry of codebases: stack, surface-level structure summary, status, linked tasks. Deliberately shallow; this is "remind me what this repo was", not a code browser.
- **Self-learning** — learning goals, resources, progress, skill gaps from saved postings.
- **Email** — triage buckets, thread summaries, drafts. Draft-only; sending is gated.

**Gate:** each renders at 1440px and 400px, with TODO markers naming its endpoints.

---

## Out of scope — do not build these

- Auto-applying to jobs, or any autonomous sending
- Bank account connections or credential storage of any kind
- Deep code indexing or semantic search over full source
- Native mobile app, landing page, sign-up flow, pricing, sharing, team features, onboarding tour
- Self-hosted model inference

---

## When you finish a phase

State which gate you ran, the command you ran, and its result. If a gate fails, fix it before moving on — do not carry a failing gate forward and do not quietly downgrade it. If a gate cannot be met as written, stop and say so explicitly rather than redefining it.
