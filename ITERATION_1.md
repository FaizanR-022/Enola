# Enola — Iteration 1

Fixes and changes after the first real use of the Phase 0–6 build. Ordered by effort, not importance: Group A is an evening, Group C is the substantial one.

Each item leads with the finding rather than the request — several turned out to have a different cause than expected.

---

## Findings first

Three things worth knowing before the work list, because they change what the fixes are:

1. **The monotone problem is a missing value, not a missing system.** `tokens.css` already supports a per-screen `--accent` override via `[data-screen]`, and components already consume `var(--accent)`. Only one screen ever defines it (`academics` → `--paper-ink`). Every other screen inherits cyan. The mechanism is built; the palette was never filled in.

2. **Finance's data model is mostly fine; the screen is a mock.** `TransactionKind` already has `EXPENSE`, `INCOME`, `TRANSFER`, `SETTLEMENT`, and `Transaction.paid_by_me` exists. "Only lets me add a split bill" is a limitation of the mock screen, not the schema. The one genuine model gap is partial repayment (C1).

3. **Chat can't log expenses because no finance tools exist.** `enola/agent/tools/` has tools for people, tasks, jobs, memory and email — none for money. The agent isn't refusing; it has nothing to call.

---

## Group A — Corrections (one evening)

### A1. Splash: hold for a minimum duration
`web/src/shell/Splash.tsx` + `ShellState.tsx`. Currently there is deliberately no timer — it leaves the instant the dashboard resolves, which on localhost is ~200ms.

Add `VITE_SPLASH_MIN_MS` (default 3000). The splash leaves at `max(dataReady, minDuration)`, still click-to-skip. Keep the progress bar honest: it should reach full at data-ready and hold, not fake progress to fill the time.

### A2. Dashboard: stop showing cold contacts in Reminders
`enola/core/services/dashboard.py:94`. Reminders come from `unread_in_app()`, which includes `FOLLOWUP_NUDGE` — and that kind covers both quiet recruiter threads *and* cold contacts. The dashboard separately has its own `going_cold` field, so cold contacts currently appear twice.

Split `FOLLOWUP_NUDGE` into `THREAD_QUIET` and `CONTACT_COLD`, and exclude `CONTACT_COLD` from the dashboard reminder query. Cold contacts stay visible on People, where they belong.

### A3. Tasks: two-tap completion
`web/src/screens/Tasks.tsx`, `Dashboard.tsx`, `shared/TaskRow.tsx`.

Ticking a task **arms** it rather than completing it: the checkbox turns into a small green confirm button in the same row. A second tap completes. Tapping anywhere else, or a few seconds of inactivity, disarms it. No dialog, no modal, no layout shift.

Pair it with an undo toast on the completion that does go through ("Done · `<title>` · Undo", ~6s) — cheap, and it covers the case where the second tap was the mistake.

### A4. Login: an autologin flag for LAN
`enola/api/routers/auth.py`, `enola/core/config.py`.

The login screen exists because `FABLE_PROMPT.md` required real session auth from the start, on the reasoning that Enola would eventually be internet-reachable. Sessions already last 30 days (`session_ttl_hours: 720`), so you should not be seeing it daily — if you are, the cookie is being dropped, and that's a separate bug worth chasing.

Add `ENOLA_AUTOLOGIN=true` (default false), which mints an owner session automatically when the request comes from a loopback or private-range address. Keep the flag off the moment Enola is hosted. **Do not delete auth** — re-adding it later touches every route.

### A5. Escape `$` in `.env`
The scrypt hash makes `docker compose` print four interpolation warnings every run. Escape `$` as `$$` in `ENOLA_OWNER_PASSWORD_HASH`.

### A6. Sound effects
New `web/src/lib/sound.ts`.

Short cues on: task completed, Held item arriving, message sent, settlement recorded. Keep them quiet and under ~150ms.

**Synthesize with the Web Audio API rather than shipping audio files** — a couple of oscillator blips with a fast envelope. No asset pipeline, no loading, no licensing, and the pitch can carry meaning (rising for done, falling for dismissed, a soft two-note for a new Held item).

Add a mute toggle in Settings, persisted to `localStorage`, and never play a sound for something the user didn't trigger while the tab is backgrounded.

---

## Group B — Colour (half a day)

The goal is faster scanning, not decoration. Three layers, in strict priority:

### B1. Held ochre stays sacred
`--oc` means Held and nothing else, on any screen, forever. Everything below works around it.

### B2. Domain identity: fill in the per-screen accents
Define `[data-screen="…"] { --accent: … }` for every screen. Suggested assignments — each distinct from ochre, each defined in both themes:

| Screen | Accent |
|---|---|
| Dashboard, Chat | `--cy` cyan (Enola itself) |
| Jobs | cooler indigo |
| People | warm rose |
| Tasks | `--gr` green |
| Finance | teal |
| Academics | `--paper-ink` (already set) |
| Projects | muted violet |
| Self-learning | amber-brown, clearly not ochre |
| Memory, Log | `--tx2`, deliberately neutral — these screens are about other screens |

Add each as a real token with a light-theme counterpart; no per-component hex.

### B3. Urgency by intensity, not new hues
A separate urgency *hue* would collide with both the Held ochre and the domain accents. Use weight instead, which reads faster anyway:

- **Overdue** — filled `--rd` dot, red left edge on the row
- **Due today** — outlined `--rd` dot, no edge
- **This week** — `--tx2` dot
- **Later / no date** — `--tx3` dot, dimmed row

Apply consistently to tasks, deadlines, application next-actions and follow-ups.

### B4. Density
The "I'll miss something" feeling is partly colour and partly that every dashboard card carries equal visual weight. Give the dashboard one clear primary region (Held + overdue) at full contrast and demote the rest a step — smaller type, `--tx2`, tighter rows.

---

## Group C — Finance, rebuilt (the substantial one)

### C1. Model: real partial settlement
The only genuine schema gap. `TransactionSplit.settled_at` is a single nullable timestamp, so a share is either fully settled or not at all. "I owe 500, he paid back 300" has nowhere to live.

Add a `settlement` table:

```
settlement
  id, person_id, amount, direction (they_paid_me | i_paid_them),
  occurred_at, note, account_id (nullable)

settlement_allocation          # optional: ties a payment to specific splits
  settlement_id, transaction_split_id, amount
```

A person's balance becomes `sum(unsettled split shares) − sum(allocated settlements)`, computed in a service and never stored. This also handles repayments not tied to any single expense, which is how repayment actually works.

Replace `settled_at` with derived state in a **new** migration. Never edit an applied one.

### C2. Wire the screen, with all five entry paths
`web/src/screens/scaffold/Finance.tsx` moves out of `scaffold/` and onto the live endpoints (`/api/accounts`, `/api/categories`, `/api/transactions`). The screen needs:

- **Log expense** — amount, category, account, date, note. The common case; one tap from the header.
- **Log income** — same form, `kind=income`.
- **Transfer** — between two accounts.
- **Split** — an expense plus per-person shares (what the mock does today).
- **Settle up** — record a payment against a person's balance, full or partial.

Views: a transaction ledger, a per-category month summary, and a "who owes whom" panel showing net balance per person with a settle action.

### C3. Finance agent tools
New `enola/agent/tools/finance.py`:

| Tool | Risk |
|---|---|
| `log_expense`, `log_income`, `log_transfer` | `WRITE_LOCAL` |
| `record_settlement` | `WRITE_LOCAL` |
| `split_expense` | `WRITE_LOCAL` |
| `finance_summary`, `who_owes_me` | `SAFE` |

This is what makes "spent 450 on fuel" work in chat. Parse amount, category and person from natural language, and echo back what was recorded so a misparse is visible immediately.

---

## Group D — Wire Projects and Self-learning (half a day each)

Both are mocks with live endpoints already behind them (`/api/projects`, `/api/learning-goals`). Follow the `TODO(wire)` markers; the work is replacing mock constants with the `@/data` hooks and handling the empty, loading and error states the mock skips.

Projects stays a **registry**, per the original scope — stack, structure summary, status, linked tasks. Not a code browser.

---

## Group E — Chat full-screen (small)

`web/src/shell/ChatRail.tsx`. Add a third state to the existing rail toggle: `closed → rail → full`. Full-screen overlays the screen area, keeps the nav, and is `Esc`-dismissible back to rail. Persist the choice per session.

---

## Group F — Voice

**Yes, doable**, and cheaply for a first version.

### F1. v1: push-to-talk, and Enola talks back
- **Speech-to-text:** Web Speech API (`SpeechRecognition`). Works in Edge and Chrome, works on `localhost`, no key, no cost.
- **Text-to-speech — yes, this works.** `speechSynthesis` is built into the browser, free, and uses the OS voices, so it generally runs offline. Enola reads its replies aloud.
- **UI:** a mic button in the chat rail. Hold to talk, release to send. The transcript lands in the chat input so you can correct it before sending.
- **Speech settings:** an auto-speak toggle (off by default — you won't always want it talking), plus voice and rate pickers. Windows voices are serviceable; if the voice grates, ElevenLabs or OpenAI TTS sound far better but cost money and send your text off-machine.
- **Always allow interruption.** A stop-speaking control, and any new input cancels playback. An assistant you can't shut up mid-sentence is unusable.

A day's work, maybe two.

### F2. Two things to know before committing
- **Privacy:** Chrome's `SpeechRecognition` streams audio to Google's servers. For an assistant holding your job hunt, finances and contacts, decide whether that's acceptable. The private alternative is local `faster-whisper` behind a `/api/transcribe` endpoint — a few hours more work, no audio leaves the machine, needs a model download.
- **Mic needs HTTPS off localhost.** The moment you open Enola from your phone by IP, the mic stops working. This is the deferred hosting decision coming back.

### F3. Voice must not bypass the gate
A spoken "email Ayesha I'll send it tonight" still produces a Held item. The spoken reply must say so out loud — "Drafted. It's waiting for your approval" — or you'll assume it sent. This is the single most important rule in the voice work.

### F4. Wake word — defer
"Hey Enola" means an always-listening mic: a battery, privacy and false-trigger problem. Push-to-talk first; if it earns its place, add Porcupine later.

---

## Group G — Cost: model roles and prompt caching

Groq is dropped — Enola stays on Anthropic and credit gets added instead. **No provider abstraction**, then: one provider means an interface built for a single implementation, which is speculative structure rather than design. If a second provider ever becomes real, that is when to build it.

What remains is spend, and it matters more now that the tokens are paid for.

### G1. Per-call model roles
`agent_model` currently defaults to `claude-opus-5` for everything, including work needing no judgement. Split it:

- `AGENT` — the chat loop. `claude-haiku-4-5`.
- `UTILITY` — daily-brief prose, posting classification, match scoring, document summaries. `claude-haiku-4-5`.

Both on Haiku for now, on budget grounds. **Keep the roles separate regardless** — the seam is free today and turns a future upgrade of the agent loop into an env-var change.

A dict and a lookup, not a routing framework. Log which model served each call so spend is visible rather than assumed.

**What to watch for.** Haiku is the weakest of the current models at multi-step tool use, and the approval gate depends on well-formed tool calls. The gate itself holds — an unknown tool name is gated by design — but the symptom of Haiku struggling will be more Held items containing nonsense, and turns where Enola picks the wrong tool or calls one when it should have just answered. If that starts happening often enough to be annoying, flip `ENOLA_AGENT_MODEL` to `claude-sonnet-5` and leave `UTILITY` on Haiku; that lands near $12–15/month instead of ~$9.

### G2. What this costs

Current pricing, per million tokens:

| Model | Input | Output |
|---|---|---|
| Claude Haiku 4.5 | $1.00 | $5.00 |
| Claude Sonnet 5 | $2.00 | $10.00 |
| Claude Opus 5 | $5.00 | $25.00 |

Assumptions for Enola: ~30 chat turns a day; each turn averages two model calls (the agentic loop); ~6K input tokens per call (system prompt, ~11 tool schemas, memory facts, retrieved chunks, history) and ~300 output. That's roughly **10.8M input and 0.5M output a month**.

| Model | Without caching | With prompt caching |
|---|---|---|
| Haiku 4.5 | ~$13/mo | **~$9/mo** |
| Sonnet 5 | ~$27/mo | ~$18/mo |
| Opus 5 (current default) | ~$67/mo | ~$45/mo |

Lighter use — 10 turns a day — puts Haiku nearer **$3–5/month**.

All-Haiku with caching lands around **$9/month** at 30 turns a day, and nearer **$3–5** at ten turns a day — against ~$45 on the current all-Opus configuration. Raising just the agent loop to Sonnet later costs roughly $3–6/month more.

### G3. Prompt caching
The system prompt and tool schemas are byte-identical on every call, which is the ideal cache prefix; cache reads bill at roughly a tenth of input. Cache the stable prefix and keep volatile content — retrieved chunks, memory facts, history, timestamps — strictly after the last breakpoint.

The failure mode to watch for is silence: anything time-dependent or non-deterministic inside the cached prefix drops the hit rate to zero without raising an error. Verify with `cache_read_input_tokens`, don't assume.

### G4. How much credit to add
Given the numbers above, **$20 is comfortably two months or more** of all-Haiku use, even at the heavier end. Start there rather than larger — you'll have real usage data within a week, and the per-call logging from G1 will tell you exactly where the tokens went.

---

## Suggested order

1. **Group G** — model roles and caching first, so every later phase runs cheaper while it's being tested.
2. **Group A** — an evening, and it removes the daily irritations.
3. **Group B** — half a day, biggest perceived change for the effort.
4. **Group E** — chat full-screen; small, and it rides along with B.
5. **Group C** — Finance, the real work.
6. **Group D** — Projects and Self-learning.
7. **Group F** — voice, once the rest feels right.

G, A, B and E together would make Enola feel substantially different without touching the schema.
