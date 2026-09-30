# enola

A personal agent for one person, on one machine. It holds your context (people, tasks,
job applications, coursework, finances, projects) and acts on it. It proposes; it never
acts unattended. Anything that leaves the system or destroys a record is **Held** until
you click.

The design brief is `FABLE_PROMPT.md`. The visual prototype is in `design/`.

## Run it

Prerequisites: Docker Desktop, Python 3.12+, Node 20+.

```bash
cp .env.example .env                       # then set ENOLA_OWNER_PASSWORD_HASH (below)
python -m venv .venv && .venv/Scripts/pip install -e ".[dev]"     # Windows
python -m enola.core.auth hash "your password"                     # paste into .env
python -m enola.scripts.seed --reset       # realistic sample data, dates relative to today
                                           # (or --wipe to start from an empty database)
```

Then, every time, one command:

```bash
./enola.sh               # Git Bash / WSL
enola.cmd                # PowerShell, cmd, or double-click from Explorer
enola                    # any shell, once the venv is activated
```

That is `python -m enola.scripts.dev`: it starts the database, waits for it, applies
migrations, then runs the API, the worker and the web dev server in one terminal with
prefixed output, and opens the browser. Ctrl+C stops all of them.

Flags: `--no-web`, `--no-worker`, `--no-reload`, `--no-open`, `--no-db`.

<details><summary>Running the pieces separately</summary>

```bash
docker compose up -d                                              # Postgres + pgvector
alembic upgrade head
.venv/Scripts/python -m uvicorn enola.api.main:app --reload       # API on ENOLA_API_PORT
.venv/Scripts/python -m enola.workers.scheduler                   # worker, separate process
cd web && npm run dev                                             # web on 5173
```

</details>

`ANTHROPIC_API_KEY` makes the agent think. Without it the app still runs: every screen
works, the worker runs, and Held items can be approved or rejected, but new chat turns
are refused with `agent_unavailable`. To see the approval flow without a key:

```bash
python -m enola.scripts.demo_held          # drafts a recruiter follow-up and Holds it
```

Embeddings default to a deterministic local hash (`ENOLA_EMBEDDER=hash`); set it to
`voyage` with `VOYAGE_API_KEY` for real semantic retrieval. The email-to-self channel
needs the `ENOLA_SMTP_*` variables; until then those notifications wait in the outbox.

## Check it

```bash
.venv/Scripts/mypy enola                   # strict, must be clean
.venv/Scripts/pytest tests                 # needs the compose database (enola_test)
cd web && npm run typecheck && npm run build
```

`tests/test_approval_gate.py` holds the four mandatory gate tests. They run the real
LangGraph graph against the real Postgres checkpointer with a scripted model.

## Where things are

```
enola/
  api/          FastAPI: main.py (app factory, error shape), deps.py, routers/, crud.py (the one router pattern)
  core/         config (env only), db, enums (shared with web), models/, schemas/, services/, repository.py, storage.py
  agent/        registry.py (risk classification = the gate), graph.py (LangGraph + interrupt), service.py, tools/, memory/, prompts/
  workers/      scheduler.py (APScheduler), jobs/ (reminders, follow-up nudges, daily brief), outbox.py (channels)
  ingest/       embeddings.py, documents.py (chunk + embed)
  scripts/      seed, demo_held, export_openapi, export_enums
web/src/
  theme/        tokens.css (every colour, space, radius), base.css
  ui/           primitives: Button, Card, Field, Table, Sheet, Badge, EmptyState, …
  shell/        nav, header, chat rail, ⌘K palette, splash, phone tabs
  data/         the one server-state layer (TanStack Query over the generated client)
  screens/      one screen per file; scaffold/ holds the two still-mock screens (Academics, Email)
  lib/          api.ts (openapi-fetch), api-types.generated.ts, enums.generated.ts
alembic/        migrations; never edit one after it has been applied
tests/          gate tests, router smoke tests, scheduling and memory tests
```

Regenerate the web types after changing any Pydantic schema:

```bash
python -m enola.scripts.export_openapi web/openapi.json && (cd web && npm run gen:api)
python -m enola.scripts.export_enums web/src/lib/enums.generated.ts
```

## The gate, in one paragraph

Tools register through `@tool(risk=Risk.X)` in `enola/agent/registry.py`. The graph's
`gate` node looks the tool up **before** executing it. `SAFE` and `WRITE_LOCAL` run
(the latter is logged to `activity_log`). `EXTERNAL`, `DESTRUCTIVE`, and anything
registered without a risk (`UNCLASSIFIED`) write an `approval_request` row with
`state='held'` and call LangGraph's `interrupt()`. The run resumes from its Postgres
checkpoint when you approve (optionally with edited arguments) and ends when you reject.
The word for that paused state is **Held**, everywhere.

## Iteration 1 (2026-09-17)

Built from `FABLE_PROMPT_ITERATION_1.md` after first real use.

- **Cost.** Two model roles, `ENOLA_AGENT_MODEL` for the chat loop and `ENOLA_UTILITY_MODEL`
  for summaries and classification, both falling back to `ENOLA_DEFAULT_MODEL`
  (`claude-haiku-4-5`). Every call is logged to `activity_log` as `model_call` with the
  model id and token usage. The system prompt is a stable manual block marked for prompt
  caching plus a small volatile block; `python -m enola.scripts.cache_check` shows the
  cache-read tokens on a second turn.
- **Corrections.** Splash holds for `VITE_SPLASH_MIN_MS`; the old follow-up nudge is split
  into `thread_quiet` (a reminder) and `contact_cold` (never a reminder); tasks complete
  with two taps plus an undo toast; short Web Audio cues with a mute in Settings;
  `ENOLA_AUTOLOGIN=true` skips the password for loopback and private-LAN callers only;
  `$` in `.env` values is written as `$$`.
- **Colour and density.** Ochre means Held and nothing else. Each screen has its own accent.
  Urgency is one shared component: overdue (red dot and edge), today, this week, later.
  The chat rail cycles closed → rail → full screen; Esc returns to the rail.
- **Finance.** Real screen with five entry paths (expense, income, transfer, split, settle
  up), a ledger, category spend, and who-owes-whom. Settlements are rows in `settlement`
  with allocations to split shares; balances are always derived, never stored. The agent
  has `log_expense`, `log_income`, `log_transfer`, `split_expense`, `record_settlement`
  (all local writes) and `finance_summary`, `who_owes_me` (reads).
- **Projects and Self-learning** are wired to `/api/projects` and `/api/learning-goals`.
- **Voice.** Hold the mic in chat to talk; the transcript lands in the input and never
  sends by itself. Replies can be read aloud (`speechSynthesis`; auto-speak is off by
  default, voice and rate in Settings; any new input or the stop control cuts playback).
  The server composes the spoken text, so a Held reply always starts with the approval
  notice. `tests/test_voice.py` asserts a voice-initiated external action is Held.
