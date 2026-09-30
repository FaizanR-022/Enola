# Enola — Iteration 2: move the agent to Gemini

One sitting. Adds Google Gemini as a model provider and makes it the default, keeping the Anthropic path intact behind a setting.

This document is both the plan and the build brief — it is small enough not to need two.

---

## Why

No Anthropic API credit right now. Gemini has a genuinely free tier with no card required, and its function calling is reliable enough for the approval gate (unlike the open-weight option considered earlier and dropped).

**Decision already taken, recorded here so it isn't rediscovered later:** the Gemini **free tier lets Google use prompts and responses to improve its products**, including human review and possible inclusion in training data. Enola's requests carry memory facts, retrieved document chunks, real contacts, job applications and finances. The owner has accepted this trade for now. The paid tier removes it; so does moving back to Anthropic. Treat it as a reversible choice, which is why the provider stays a setting.

---

## Model choice per role

**Corrected 2026-09-26 by measurement.** Google no longer publishes static free-tier
numbers — they are per-project and only visible at
[aistudio.google.com/rate-limit](https://aistudio.google.com/rate-limit), which is why
every third-party table disagrees. The figures below were measured against this project's
own key, not read off a blog.

| Role | Model | Measured | Why |
|---|---|---|---|
| `AGENT` | `gemini-3.5-flash-lite` | 14 requests in 11s, no limit hit | One chat turn spends 2–4 requests on tool calls, so RPM is the binding constraint. Bound all 22 of Enola's tools with no schema error and picked the right tool in 5 of 5 cases. |
| `UTILITY` | `gemini-3.5-flash-lite` | same | Briefs, classification, summaries. |

**Rejected: `gemini-3.5-flash` — 5 requests per minute on the free tier.** The API states
it outright (`GenerateRequestsPerMinutePerProjectPerModel-FreeTier, limit: 5`). At 2–4
requests per turn that is barely one usable turn a minute; the agent loop was rate-limited
almost immediately. Better reasoning, unusable throughput.

**Also note:** `gemini-2.5-flash` and `gemini-2.5-flash-lite` appear in the model list but
return `ModelNotFound` for this key. Any advice written about the 2.5 family does not apply.

If the agent loop ever needs more reasoning than flash-lite gives, raise `ENOLA_AGENT_MODEL`
alone and leave `UTILITY` where it is — that is what the role split is for.

## The design: one provider seam, two implementations

There are now genuinely two providers, so an abstraction is justified — this is the second repetition, not speculation.

Three things differ between providers and **nothing else should**:

1. **Which client class to construct** (`ChatAnthropic` vs `ChatGoogleGenerativeAI`)
2. **Which API key to read**, and what the "no key" message says
3. **How system content is shaped** — this is the one that will bite

On Anthropic, the system prompt is a list of content blocks, with `cache_control` on the stable prefix (`stable_block()` in `enola/agent/prompts/system.py`). **Gemini does not accept that shape.** It takes a plain string system instruction. So the provider must own the conversion:

- Keep `build_system_blocks()` returning the same neutral structure it does today.
- Add a provider-level `system_message(blocks)` that renders those blocks into either Anthropic's list-of-dicts-with-`cache_control`, or a single joined string for Gemini.
- Both `enola/agent/graph.py:108` and `enola/agent/utility.py:28` go through it. Neither may build `cache_control` itself any more.

`usage_of()` in `models.py` already reads LangChain's normalised `usage_metadata`, so it works for both — Gemini simply reports no cache fields and the function returns zeros. Leave it alone.

---

## Files that change

| File | Change |
|---|---|
| `enola/core/config.py` | `model_provider: Literal["anthropic","google"] = "google"`; `google_api_key` from `GOOGLE_API_KEY`; change `default_model` to a Gemini id |
| `enola/agent/models.py` | `make_chat_model` branches on provider; `model_available` checks the selected provider's key; `NO_KEY_MESSAGE` names the right variable |
| `enola/agent/prompts/system.py` | `stable_block()` stops embedding `cache_control`; add provider-aware rendering |
| `enola/agent/utility.py` | Use the shared renderer instead of hand-building `cache_control` |
| `enola/scripts/cache_check.py` | Anthropic-only — make it say so and exit cleanly when the provider is Google |
| `pyproject.toml` | add `langchain-google-genai` |
| `.env.example`, `README.md` | document `ENOLA_MODEL_PROVIDER`, `GOOGLE_API_KEY`, the new model ids |
| `tests/test_model_roles.py` | update the caching assertions to be provider-aware |

---

## Gotchas that will actually bite

These are the reason this takes a sitting rather than twenty minutes. Check the current `langchain-google-genai` docs for exact parameter names rather than guessing — they have changed across versions.

1. **Tool schemas are stricter.** The registry builds Pydantic models from function signatures (`_args_model_from_signature`). Gemini rejects some JSON Schema constructs that Anthropic accepts — notably `anyOf` shapes produced by `X | None` optional parameters, and certain default/`additionalProperties` combinations. **This is the highest-risk item, because tool calls are what the approval gate operates on.** Expect to flatten optional parameters or post-process the generated schema.

2. **Safety filters can return an empty response.** Gemini may block a response and return no content with a non-standard finish reason. An agent turn that gets nothing back must fail gracefully — the existing `agent_unavailable` path is the model to follow — never crash, and never silently look like a completed turn.

3. **429s are routine on 10 RPM.** A chat turn with several sequential tool calls, plus the worker's 15-minute reminder tick, can collide. Configure client retries with backoff, and surface a clear "rate limited, try again in a moment" rather than a stack trace.

4. **Thinking is on by default on 2.5 models** and costs tokens and latency. For the `UTILITY` role — brief prose, classification — turn the thinking budget down or off. Leave it on for `AGENT`.

5. **Your prompt-caching work goes inert.** The Phase 1 `cache_control` plumbing is Anthropic-specific. Gemini 2.5 does implicit caching automatically with no configuration, so do not build explicit context caching now — just make sure the Anthropic path still works when the provider is switched back.

---

## Steps and gates

**Step 1 — Provider seam.** Config, `make_chat_model`, and the system-content renderer. No behaviour change on Anthropic.

*Gate:* `ENOLA_MODEL_PROVIDER=anthropic` still passes `pytest tests` and `mypy enola` exactly as before. This proves the seam did not break the working path.

**Step 2 — Gemini live.** Dependency, key, model ids, the gotchas above.

*Gate:* with `ENOLA_MODEL_PROVIDER=google` and a real key:
- A plain chat turn answers.
- **A tool-calling turn produces a correct Held item** — the critical one. Use `send_probe` or ask Enola to email someone, and confirm `approval_request.state == 'held'` with sane arguments, and that approving it resumes and completes.
- `activity_log` shows `MODEL_CALL` rows naming a `gemini-*` model for both roles.

**Step 3 — Tests and docs.** Make the suite provider-aware and update `.env.example` and `README.md`.

*Gate:* `pytest tests` green and `mypy enola` clean under **both** provider settings. The four approval-gate tests use a scripted model, so they must pass regardless of provider — if they don't, the seam leaked into the graph.

---

## Rules that still bind

From `FABLE_PROMPT.md`, unchanged:

- Propose, never act unattended. No tool bypasses the registry.
- The four gate tests in `tests/test_approval_gate.py` must pass at the end of every step. If a change breaks one, the change is wrong.
- `mypy enola` clean, TypeScript strict, secrets from env only.
- Never edit an applied migration.

Nothing in this iteration should touch the front end, the schema, or the worker's logic.

---

## Note for the implementing session

This is being built by a chat session rather than the long-running agent that did the first two iterations. Two implications:

- **Do one step at a time and report the gate result** before starting the next. Don't attempt all three in one pass.
- If a gotcha above turns out to need a different fix than described, say so rather than working around it silently — particularly anything touching tool schemas, since that is where a quiet workaround could weaken the approval gate.
