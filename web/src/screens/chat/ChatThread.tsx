import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent, type PointerEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useChatHistory, useClearChat, useDecideApproval, useSendChat, type ChatMessage } from "@/data";
import { ApiError, errorMessage, type Schemas } from "@/lib/api";
import { cx } from "@/lib/cx";
import { useSetting } from "@/lib/settings";
import { play } from "@/lib/sound";
import { groupThread, summarise, type ActivityStep } from "./activity";
import { listen, recognitionStatus, speak, stopSpeaking, useSpeaking } from "@/lib/speech";
import { useShell } from "@/shell/ShellState";
import { Avatar, Button, Dot, Input, Mono } from "@/ui";
import styles from "./ChatThread.module.css";

const THREAD = "main";

const CHIPS = ["What needs me today?", "Who can advise me on distributed systems?", "What did you do overnight?"];

/** The single conversation with Enola. The Chat tab and the rail both render this. */
export function ChatThread({ scope, compact = false, initialAsk }: { scope: string; compact?: boolean | undefined; initialAsk?: string | undefined }) {
  const history = useChatHistory(THREAD);
  const send = useSendChat(THREAD);
  const clear = useClearChat(THREAD);
  // Two taps, like completing a task: clearing cannot be undone, and the transcript is
  // the only copy of the conversation.
  const [armedClear, setArmedClear] = useState(false);
  const decide = useDecideApproval();
  const navigate = useNavigate();
  const { say } = useShell();
  const [draft, setDraft] = useState("");
  // What was just sent, shown immediately. Waiting for the server means your own words
  // only appear alongside the reply, which makes a slow turn feel like nothing happened.
  const [pending, setPending] = useState<string | null>(null);
  const sentAtLength = useRef(0);
  const [heldId, setHeldId] = useState<number | null>(null);
  const [unavailable, setUnavailable] = useState<string | null>(null);
  const bottom = useRef<HTMLDivElement>(null);
  const asked = useRef<string | null>(null);
  const [autoSpeak] = useSetting("autoSpeak");
  const speaking = useSpeaking();
  // Where the current draft came from. A transcript sets it to voice; typing sets it back.
  const source = useRef<Schemas["ChatSource"]>("text");
  const inputRef = useRef<HTMLInputElement>(null);

  const submit = (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || send.isPending) return;
    const from = source.current;
    source.current = "text";
    setDraft("");
    sentAtLength.current = (history.data ?? []).length;
    setPending(trimmed);
    stopSpeaking();
    play("sent");
    send.mutate(
      { text: trimmed, scope, source: from },
      {
        onSuccess: (run) => {
          setHeldId(run.held_approval_id);
          if (run.held_approval_id) {
            play("held");
            say("Held · waiting in Approvals");
          } else if (!run.aborted) {
            play("reply");
          }
          // Spoken asks are answered aloud; typed ones only when auto-speak is on. The
          // server composes spoken_text, so a Held reply always says so first.
          if (from === "voice" || autoSpeak) speak(run.spoken_text);
        },
        onError: (error) => {
          // Put the text back in the box rather than losing it to a failed turn.
          setPending(null);
          setDraft(trimmed);
          if (error instanceof ApiError && error.code === "agent_unavailable") setUnavailable(error.message);
          else say(errorMessage(error));
        },
      },
    );
  };

  useEffect(() => {
    if (initialAsk && asked.current !== initialAsk) {
      asked.current = initialAsk;
      submit(initialAsk);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialAsk]);

  useEffect(() => {
    bottom.current?.scrollIntoView({ block: "end" });
  }, [history.data, send.isPending]);

  const server = history.data ?? [];
  // Show the echo until the server's history has grown past where it was when we sent.
  // Comparing lengths rather than text matters: sending "ok" twice would otherwise see
  // the first copy already in history and suppress the second echo immediately.
  const showEcho = pending !== null && server.length <= sentAtLength.current;
  const messages: ChatMessage[] = showEcho
    ? [...server, { role: "you", text: pending, tool_name: null, tool_calls: [] }]
    : server;
  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    submit(draft);
  };
  const onType = (value: string) => {
    stopSpeaking();
    source.current = "text";
    setDraft(value);
  };
  const onTranscript = (text: string) => {
    if (!text) return;
    source.current = "voice";
    setDraft(text);
    inputRef.current?.focus();
  };

  return (
    <div className={cx(styles["thread"], compact && styles["compact"])}>
      <div className={styles["messages"]}>
        {!compact && (
          <div className={styles["scopeLine"]}>
            <Mono upper>One thread · scope: {scope}</Mono>
            {messages.length > 0 && (
              <Button
                variant="link"
                onClick={() => {
                  if (!armedClear) return setArmedClear(true);
                  clear.mutate(undefined, {
                    onSuccess: () => {
                      setArmedClear(false);
                      say("Chat cleared");
                    },
                    onError: (error) => {
                      setArmedClear(false);
                      say(errorMessage(error));
                    },
                  });
                }}
                onBlur={() => setArmedClear(false)}
                busy={clear.isPending}
              >
                {armedClear ? "Clear? tap again" : "Clear chat"}
              </Button>
            )}
          </div>
        )}
        {messages.length === 0 && !send.isPending && (
          <p className={styles["empty"]}>{compact ? "Ask about this screen." : "Nothing said yet. Enola can read everything and write to tasks, notes and records."}</p>
        )}
        {groupThread(messages).map((item, i) =>
          item.kind === "activity" ? (
            <Activity key={i} steps={item.steps} />
          ) : (
            <Bubble key={i} message={item.message} compact={compact} />
          ),
        )}
        {send.isPending && (
          <div className={styles["thinking"]}>
            <Dot tone="accent" size={6} pulse />
            <Mono>Enola is working…</Mono>
          </div>
        )}
        {heldId !== null && (
          <div className={styles["held"]}>
            <div className={styles["heldHead"]}>
              <Dot tone="held" size={6} pulse />
              <Mono upper tone="held" bold>
                Held · needs a decision
              </Mono>
            </div>
            <div className={styles["heldText"]}>The rest of the job stays parked. Nothing runs while this sits here.</div>
            <div className={styles["heldActions"]}>
              <Button size="sm" variant="primary" onClick={() => navigate("/approvals")}>
                Review in Approvals
              </Button>
              <Button
                size="sm"
                variant="danger"
                busy={decide.isPending}
                onClick={() =>
                  decide.mutate(
                    { id: heldId, approve: false, note: "Rejected from chat" },
                    {
                      onSuccess: () => {
                        setHeldId(null);
                        say("Rejected · job stopped");
                      },
                    },
                  )
                }
              >
                Reject
              </Button>
            </div>
          </div>
        )}
        {unavailable && (
          <div className={styles["unavailable"]}>
            <Mono upper tone="danger">
              Agent unavailable
            </Mono>
            <span>{unavailable}</span>
          </div>
        )}
        <div ref={bottom} />
      </div>
      <div className={styles["composer"]}>
        {!compact && messages.length === 0 && (
          <div className={styles["chips"]}>
            {CHIPS.map((chip) => (
              <button key={chip} type="button" className={styles["chip"]} onClick={() => submit(chip)}>
                {chip}
              </button>
            ))}
          </div>
        )}
        <form className={styles["box"]} onSubmit={onSubmit}>
          <Input ref={inputRef} bare value={draft} onChange={(e) => onType(e.target.value)} placeholder={compact ? "Ask about this screen…" : "Ask, or tell Enola to do something"} aria-label="Message Enola" disabled={send.isPending} />
          {speaking && (
            <button type="button" className={styles["stop"]} onClick={stopSpeaking} aria-label="Stop speaking" title="Stop speaking">
              ■
            </button>
          )}
          <MicButton disabled={send.isPending} onTranscript={onTranscript} onError={(m) => say(m)} />
          <Button size="sm" variant="primary" type="submit" disabled={!draft.trim()} busy={send.isPending}>
            Send
          </Button>
        </form>
        {!compact && <p className={styles["hint"]}>Enola can read everything and write to tasks, notes and records. Anything outbound or destructive stops for approval.</p>}
      </div>
    </div>
  );
}

/** Push-to-talk. Hold (pointer or Space/Enter) to listen, release to stop. The
 *  transcript goes to the input through onTranscript; this never sends. Hidden, with the
 *  reason on hover, where recognition is unavailable. */
function MicButton({ disabled, onTranscript, onError }: { disabled: boolean; onTranscript: (text: string) => void; onError: (message: string) => void }) {
  const [status] = useState(() => recognitionStatus());
  const [listening, setListening] = useState(false);
  const handle = useRef<{ stop: () => void } | null>(null);
  const latest = useRef("");

  const start = () => {
    if (disabled || handle.current) return;
    stopSpeaking();
    latest.current = "";
    handle.current = listen({
      onTranscript: (text) => {
        latest.current = text;
        onTranscript(text);
      },
      onEnd: () => {
        handle.current = null;
        setListening(false);
      },
      onError: (message) => {
        onError(message);
      },
    });
    setListening(handle.current !== null);
  };
  const stop = () => {
    handle.current?.stop();
  };

  useEffect(() => () => handle.current?.stop(), []);

  if (!status.ok) {
    return (
      <span className={styles["noMic"]} title={status.reason} aria-label={status.reason} data-reason={status.reason}>
        <Mono>no mic</Mono>
      </span>
    );
  }
  const onKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    if ((event.key === " " || event.key === "Enter") && !event.repeat) {
      event.preventDefault();
      start();
    }
  };
  const onKeyUp = (event: KeyboardEvent<HTMLButtonElement>) => {
    if (event.key === " " || event.key === "Enter") {
      event.preventDefault();
      stop();
    }
  };
  const onPointerDown = (event: PointerEvent<HTMLButtonElement>) => {
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    start();
  };
  return (
    <button
      type="button"
      className={cx(styles["mic"], listening && styles["listening"])}
      disabled={disabled}
      aria-label={listening ? "Listening, release to stop" : "Hold to talk"}
      aria-pressed={listening}
      title="Hold to talk. Release to stop; the words land in the box."
      onPointerDown={onPointerDown}
      onPointerUp={stop}
      onPointerCancel={stop}
      onKeyDown={onKeyDown}
      onKeyUp={onKeyUp}
      onContextMenu={(e) => e.preventDefault()}
    >
      {listening ? "●" : "🎙"}
    </button>
  );
}

/** What Enola did, in one line. Expandable, because when an answer looks wrong the raw
 *  output is the only way to tell whether the tool or the model was at fault. */
function Activity({ steps }: { steps: ActivityStep[] }) {
  const [open, setOpen] = useState(false);
  return (
    <div className={styles["activity"]}>
      <button type="button" className={styles["activityLine"]} onClick={() => setOpen(!open)} aria-expanded={open}>
        <span className={styles["activityDot"]} />
        <span className={styles["activityText"]}>{summarise(steps)}</span>
        <Mono>{open ? "hide" : "details"}</Mono>
      </button>
      {open && (
        <div className={styles["activityDetail"]}>
          {steps.map((step, i) => (
            <div key={i}>
              <Mono tone="accent">{step.tool}</Mono>
              <pre className={styles["activityOutput"]}>{step.output}</pre>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function Bubble({ message, compact }: { message: ChatMessage; compact: boolean }) {
  const mine = message.role === "you";
  if (compact) {
    return (
      <div className={styles["compactMsg"]}>
        <Mono upper tone={mine ? "muted" : "accent"}>
          {mine ? "you" : "enola"}
        </Mono>
        <span className={styles["compactText"]}>{message.text}</span>
      </div>
    );
  }
  return (
    <div className={cx(styles["bubbleRow"], mine && styles["mine"])}>
      <Avatar name={mine ? "You" : "Enola"} size="sm" enola={!mine} />
      <div className={cx(styles["bubble"], mine && styles["bubbleMine"])}>
        {message.text}
      </div>
    </div>
  );
}
