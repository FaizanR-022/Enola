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
docker compose up -d                       # Postgres + pgvector on the port in .env (5433)

python -m venv .venv && .venv/Scripts/pip install -e ".[dev]"     # Windows
python -m enola.core.auth hash "your password"                     # paste into .env
alembic upgrade head
python -m enola.scripts.seed --reset       # realistic sample data, dates relative to today

.venv/Scripts/python -m uvicorn enola.api.main:app --reload       # API on ENOLA_API_PORT
.venv/Scripts/python -m enola.workers.scheduler                   # worker, separate process
cd web && npm install && npm run dev                              # web on 5173
```

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
  screens/      one folder per screen; scaffold/ holds the Phase 6 mock-data screens
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
