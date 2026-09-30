# Enola — Iteration 1

You are extending an existing codebase, not starting one. Enola is a personal agent for a single user: a Python/FastAPI backend with a LangGraph agent core, Postgres + pgvector, an APScheduler worker, and a React/Vite/TypeScript front end. Phases 0–6 of `FABLE_PROMPT.md` are built and working.

This document is the work list for iteration 1, written after the owner used the app for real. `ITERATION_1.md` in the repo root carries the reasoning behind each item — read it for context, but **this document is authoritative for what to build.**

Work through the phases in order. **Each phase has a gate. Do not start the next phase until the current gate demonstrably passes** — a command that runs and a result you can point at, not "the code looks right."

---

## Read first

- `README.md` — how to run, and where things live
- `ITERATION_1.md` — the reasoning behind every item below
- `FABLE_PROMPT.md` — the original brief; its rules still bind
- `enola/agent/registry.py` and `tests/test_approval_gate.py` — understand the approval gate before touching anything near it

---

## Standing rules — carried forward, non-negotiable

These held through the first build. They must not erode during an iteration, which is exactly when rules like these usually do.

1. **Propose, never act unattended.** Anything that writes outside Enola's own database halts and waits for a human click. No autonomous-send path, not behind a flag, not for voice.
2. **No tool may bypass the registry.** Risk classification lives in `enola/agent/registry.py`. A tool registered without an explicit risk level is `UNCLASSIFIED`, which is gated.
3. **The four mandatory gate tests in `tests/test_approval_gate.py` must pass at the end of every phase.** If a change breaks one, the change is wrong, not the test.
4. **No hardcoded `localhost`; all secrets from env.**
5. **Typed end to end.** `mypy enola` clean, TypeScript `strict`. No `any`.
6. **Tokens only in the front end.** No hex values, no magic pixel numbers, no inline `style` except CSS-custom-property injection for genuinely dynamic values (the existing seven uses are the correct pattern).
7. **Thin routers, logic in services, one CRUD pattern.** Extend `enola/api/crud.py` and `enola/core/repository.py`; do not hand-roll a parallel router.
8. **Never edit an applied migration.** Add a new one.
9. **Abstract on the second or third repetition, not the first.** Do not invent a framework mid-iteration.

---

## Phase 1 — Cost: model roles and prompt caching

Enola stays on Anthropic. **Do not add a provider abstraction** — there is exactly one provider, and an interface built for one implementation is speculative structure, not design.

This phase is about spend. The owner pays per token, and the current configuration is the most expensive possible: `agent_model` defaults to `claude-opus-5` for everything, including work that needs no judgement at all.

### 1.1 Per-call model roles
Make the model a per-call choice rather than one global setting. A small `ModelRole` notion:

- `AGENT` — the chat loop. Default `claude-haiku-4-5`.
- `UTILITY` — daily-brief prose, posting classification, match scoring, document summarisation. Default `claude-haiku-4-5`.

Both roles point at Haiku for now: the owner is on a tight budget. **Keep the two roles separate anyway** — the seam costs nothing today and means raising the agent loop to a stronger model later is one environment variable rather than a refactor.

Each resolves to its own configured model id (`ENOLA_AGENT_MODEL`, `ENOLA_UTILITY_MODEL`), each falling back to a single configured default when unset. A dict and a lookup is enough — do not build a routing framework.

Log the model actually used on every call, so the split is visible in `activity_log` rather than assumed.

### 1.2 Prompt caching
The system prompt and tool schemas are byte-identical on every call, which makes them an ideal cache prefix, and cache reads bill at roughly a tenth of input. Cache the stable prefix — system prompt first, then tool definitions — and keep volatile content (retrieved chunks, memory facts, history, timestamps) strictly after the last breakpoint.

Watch for silent invalidators: anything time-dependent, a non-deterministic tool ordering, or a per-request id inside the cached prefix will drop the hit rate to zero without erroring.

**Gate:**
- `pytest tests` green, `mypy enola` clean.
- A second chat turn on the same thread reports `cache_read_input_tokens > 0`. **Log this number somewhere visible.** If it reads zero, something is invalidating the prefix and this work is not done — caching that looks implemented but never hits is the expected failure mode here.
- `activity_log` records the model id used on every call, and both roles resolve independently — setting `ENOLA_AGENT_MODEL` alone must change the chat loop without touching utility calls.

---

## Phase 2 — Corrections

### 2.1 Splash minimum duration
`web/src/shell/Splash.tsx`, `ShellState.tsx`. There is deliberately no timer today; it leaves the instant the dashboard resolves (~200ms on localhost). Add `VITE_SPLASH_MIN_MS`, default `3000`. The splash leaves at `max(dataReady, minDuration)` and stays click-to-skip. The progress bar must stay honest — reach full when data is ready and hold, not fake progress to fill time.

### 2.2 Cold contacts out of dashboard reminders
`enola/core/services/dashboard.py:94`. Reminders come from `unread_in_app()`, which includes `FOLLOWUP_NUDGE` — a kind that covers both quiet recruiter threads and contacts going cold. The dashboard already has a separate `going_cold` field, so cold contacts currently appear twice.

Split `NotificationKind.FOLLOWUP_NUDGE` into `THREAD_QUIET` and `CONTACT_COLD`. Migrate existing rows. Exclude `CONTACT_COLD` from the dashboard reminder query; it stays visible on People.

### 2.3 Two-tap task completion
`web/src/screens/Tasks.tsx`, `Dashboard.tsx`, `shared/TaskRow.tsx`.

The first tap **arms** rather than completes: the checkbox becomes a small green confirm button in the same row. A second tap completes. Tapping elsewhere, or a few seconds idle, disarms. No dialog, no modal, **no layout shift** — the row must not resize, or the list jumps under the finger.

Also show an undo toast on the completion that goes through ("Done · `<title>` · Undo", ~6s) using the existing `say` toast, reverting the mutation on click.

### 2.4 Sound cues
New `web/src/lib/sound.ts`. Short cues (under ~150ms) on: task completed, Held item arriving, message sent.

**Synthesize with the Web Audio API — do not ship audio files.** Oscillator plus a fast gain envelope. Pitch carries meaning: rising for done, falling for dismissed, a soft two-note for a new Held item.

Requirements: a mute toggle in Settings persisted to `localStorage`; silence when the tab is backgrounded; never play a sound for something the user did not trigger; construct the `AudioContext` lazily on first user gesture (browsers block it otherwise).

### 2.5 LAN autologin
`enola/api/routers/auth.py`, `enola/core/config.py`. Add `ENOLA_AUTOLOGIN`, default `false`. When true **and** the request originates from a loopback or private-range address, mint an owner session automatically.

**Do not remove or weaken the auth system** — it stays intact and the flag goes off the moment Enola is hosted. Reject the flag's effect for any non-private remote address even when it is set.

### 2.6 Escape `$` in `.env`
The scrypt password hash makes `docker compose` emit interpolation warnings on every command. Escape `$` as `$$` in `ENOLA_OWNER_PASSWORD_HASH`, and note the requirement in `.env.example`.

**Gate:**
- Splash visibly holds ~3s on a warm load and still skips on click.
- A cold contact appears on People but not in dashboard Reminders; a quiet recruiter thread still appears in Reminders.
- One tap arms a task and does not complete it; a second completes it; tapping elsewhere disarms; the row does not change height in any state.
- Sounds play, the mute toggle persists across reload, and no sound fires with the tab hidden.
- `ENOLA_AUTOLOGIN=true` skips login from localhost; unset or from a public address, login is required.
- `docker compose ps` prints no interpolation warnings.

---

## Phase 3 — Colour, density, and chat full-screen

### 3.1 Held ochre is sacred
`--oc` means Held and nothing else, anywhere, forever. Everything below works around that constraint.

### 3.2 Fill in the per-screen accents
`web/src/theme/tokens.css` already supports `[data-screen="…"] { --accent: … }` and components already consume `var(--accent)` — but only `academics` ever defines it, so every other screen silently inherits cyan. **This is the whole monotone problem.** Define an accent for every screen:

| Screen | Accent |
|---|---|
| Dashboard, Chat | `--cy` cyan (Enola itself) |
| Jobs | cooler indigo |
| People | warm rose |
| Tasks | `--gr` green |
| Finance | teal |
| Academics | `--paper-ink` (already set) |
| Projects | muted violet |
| Self-learning | amber-brown, clearly distinct from ochre |
| Memory, Log | `--tx2`, deliberately neutral |

Each becomes a real token with a light-theme counterpart. Every accent must pass contrast against `--bg` and `--s1` in **both** themes, and none may be mistakable for `--oc` at a glance.

### 3.3 Urgency by intensity, not new hues
A separate urgency hue would collide with both Held ochre and the domain accents. Use weight:

- **Overdue** — filled `--rd` dot, red left edge on the row
- **Due today** — outlined `--rd` dot, no edge
- **This week** — `--tx2` dot
- **Later / no date** — `--tx3` dot, dimmed row

Apply consistently to tasks, academic deadlines, application next-actions and follow-ups. Build it once as a shared component or hook; do not reimplement the tiering per screen.

### 3.4 Dashboard density
Every dashboard card currently carries equal visual weight, which is why it reads as a wall. Give it one primary region — Held plus overdue — at full contrast, and demote everything else a step: smaller type, `--tx2`, tighter rows.

### 3.5 Chat full-screen
`web/src/shell/ChatRail.tsx`. Extend the existing toggle to three states: `closed → rail → full`. Full-screen overlays the screen area, keeps the nav, and `Esc` returns to rail. Persist the choice for the session.

**Gate:**
- Every screen shows a distinct accent, verified in both light and dark.
- `grep` confirms `--oc` is used only for Held.
- A task list shows all four urgency tiers and they are distinguishable at a glance.
- The chat rail cycles through all three states, `Esc` works, and full-screen is usable at 400px.

---

## Phase 4 — Finance, rebuilt

The schema is mostly right already: `TransactionKind` has `EXPENSE`, `INCOME`, `TRANSFER`, `SETTLEMENT`, and `Transaction.paid_by_me` exists. The screen is a mock, there are no finance tools, and partial settlement has nowhere to live.

### 4.1 Partial settlement
`TransactionSplit.settled_at` is a single nullable timestamp, so a share is all-or-nothing. "I owe 500, he paid back 300" cannot be recorded. Add:

```
settlement
  id, person_id, amount, direction (they_paid_me | i_paid_them),
  occurred_at, note, account_id (nullable)

settlement_allocation
  settlement_id, transaction_split_id, amount
```

A person's balance is **derived, never stored**: `sum(unsettled split shares) − sum(allocated settlements)`, computed in a service. This also supports repayments not tied to any single expense, which is how repayment actually works.

Replace `settled_at` with derived state in a **new** migration, backfilling existing settled splits as full settlements.

### 4.2 Wire the screen
Move `web/src/screens/scaffold/Finance.tsx` out of `scaffold/` onto the live endpoints. Five entry paths, all reachable without hunting:

- **Log expense** — amount, category, account, date, note. The common case; one tap from the header.
- **Log income** — same form, `kind=income`.
- **Transfer** — between two accounts.
- **Split** — an expense plus per-person shares (what the mock does today).
- **Settle up** — record a payment against a person's balance, full or partial.

Views: a transaction ledger, a per-category month summary, and a "who owes whom" panel showing net balance per person with a settle action. Amounts in PKR.

### 4.3 Finance agent tools
New `enola/agent/tools/finance.py`:

| Tool | Risk |
|---|---|
| `log_expense`, `log_income`, `log_transfer` | `WRITE_LOCAL` |
| `record_settlement` | `WRITE_LOCAL` |
| `split_expense` | `WRITE_LOCAL` |
| `finance_summary`, `who_owes_me` | `SAFE` |

This is what makes "spent 450 on fuel" work in chat. Parse amount, category and person from natural language, and **echo back what was recorded** so a misparse is visible immediately.

**Gate:**
- Migration runs up and down cleanly; existing settled splits survive the backfill.
- An automated test covers the balance math: owe 500, receive 300, balance reads 200; receive 200 more, balance reads 0; an unallocated repayment still reduces the net.
- All five entry paths work from the UI and appear in the ledger.
- "I spent 450 on fuel" in chat creates the transaction and echoes it back.
- `pytest tests` green, `mypy enola` clean.

---

## Phase 5 — Projects and Self-learning

Both are mocks with live endpoints already behind them (`/api/projects`, `/api/learning-goals`). Follow the `TODO(wire)` markers: replace mock constants with the `@/data` hooks and handle the empty, loading and error states the mocks skip.

**Projects stays a registry** — stack, surface-level structure summary, status, linked tasks. Not a code browser.

**Gate:** both screens render live data; no imports from `scaffold/mock.ts` remain in either; empty, loading and error states all reachable and correct; both work at 400px.

---

## Phase 6 — Voice

### 6.1 Push-to-talk
Mic button in the chat rail, using the Web Speech API (`SpeechRecognition`). Hold to talk, release to send. The transcript lands in the chat input so it can be corrected before sending — never auto-send a transcript.

### 6.2 Enola speaks
`speechSynthesis` for replies. Settings: auto-speak toggle (**default off**), voice picker, rate. **Any new input cancels playback**, plus an explicit stop control. An assistant that cannot be interrupted mid-sentence is unusable.

### 6.3 Voice must not bypass the gate
A spoken "email Ayesha I'll send it tonight" produces a Held item exactly as the typed equivalent does. **The spoken reply must say so aloud** — "Drafted. It's waiting for your approval" — or the owner will walk away believing it sent. This is the most important rule in the voice work.

### 6.4 Degrade honestly
Where `SpeechRecognition` is unavailable (Firefox, Safari, non-HTTPS origins other than localhost), hide the mic and say why on hover rather than showing a button that silently fails.

Do **not** build a wake word.

**Gate:**
- Push-to-talk produces a transcript in the input, not an auto-sent message.
- Enola speaks a reply, and both a new input and the stop control cut it off mid-sentence.
- **An automated test asserts that a voice-initiated `EXTERNAL` tool call produces a Held `approval_request`**, and the spoken response text contains the approval notice.
- On a browser without `SpeechRecognition`, the mic is absent and explained.

---

## Out of scope

Do not build: wake-word detection, cloud TTS providers, bank connections, auto-apply, deep code indexing, mobile push, CI/CD, or any autonomous-send path.

---

## When you finish a phase

State which gate you ran, the command, and its result. If a gate fails, fix it before moving on — do not carry a failing gate forward and do not quietly redefine it. If a gate cannot be met as written, stop and say so explicitly.
