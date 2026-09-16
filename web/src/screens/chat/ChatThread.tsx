import { useEffect, useRef, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useChatHistory, useDecideApproval, useSendChat, type ChatMessage } from "@/data";
import { ApiError, errorMessage } from "@/lib/api";
import { cx } from "@/lib/cx";
import { useShell } from "@/shell/ShellState";
import { Avatar, Button, Dot, Input, Mono } from "@/ui";
import styles from "./ChatThread.module.css";

const THREAD = "main";

const CHIPS = ["What needs me today?", "Who can advise me on distributed systems?", "What did you do overnight?"];

/** The single conversation with Enola. The Chat tab and the rail both render this. */
export function ChatThread({ scope, compact = false, initialAsk }: { scope: string; compact?: boolean | undefined; initialAsk?: string | undefined }) {
  const history = useChatHistory(THREAD);
  const send = useSendChat(THREAD);
  const decide = useDecideApproval();
  const navigate = useNavigate();
  const { say } = useShell();
  const [draft, setDraft] = useState("");
  const [heldId, setHeldId] = useState<number | null>(null);
  const [unavailable, setUnavailable] = useState<string | null>(null);
  const bottom = useRef<HTMLDivElement>(null);
  const asked = useRef<string | null>(null);

  const submit = (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || send.isPending) return;
    setDraft("");
    send.mutate(
      { text: trimmed, scope },
      {
        onSuccess: (run) => {
          setHeldId(run.held_approval_id);
          if (run.held_approval_id) say("Held · waiting in Approvals");
        },
        onError: (error) => {
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

  const messages = history.data ?? [];
  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    submit(draft);
  };

  return (
    <div className={cx(styles["thread"], compact && styles["compact"])}>
      <div className={styles["messages"]}>
        {!compact && (
          <Mono upper className={styles["scopeLine"]}>
            One thread · scope: {scope}
          </Mono>
        )}
        {messages.length === 0 && !send.isPending && (
          <p className={styles["empty"]}>{compact ? "Ask about this screen." : "Nothing said yet. Enola can read everything and write to tasks, notes and records."}</p>
        )}
        {messages.map((message, i) => (
          <Bubble key={i} message={message} compact={compact} />
        ))}
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
          <Input bare value={draft} onChange={(e) => setDraft(e.target.value)} placeholder={compact ? "Ask about this screen…" : "Ask, or tell Enola to do something"} aria-label="Message Enola" disabled={send.isPending} />
          <Button size="sm" variant="primary" type="submit" disabled={!draft.trim()} busy={send.isPending}>
            Send
          </Button>
        </form>
        {!compact && <p className={styles["hint"]}>Enola can read everything and write to tasks, notes and records. Anything outbound or destructive stops for approval.</p>}
      </div>
    </div>
  );
}

function Bubble({ message, compact }: { message: ChatMessage; compact: boolean }) {
  if (message.role === "tool") {
    return (
      <div className={styles["tool"]}>
        <Mono>{message.tool_name ?? "tool"}</Mono>
        <span className={styles["toolText"]}>{message.text.length > 400 ? `${message.text.slice(0, 400)}…` : message.text}</span>
      </div>
    );
  }
  const mine = message.role === "you";
  if (compact) {
    return (
      <div className={styles["compactMsg"]}>
        <Mono upper tone={mine ? "muted" : "accent"}>
          {mine ? "you" : "enola"}
        </Mono>
        <span className={styles["compactText"]}>{message.text || (message.tool_calls.length ? `→ ${message.tool_calls.map((c) => c["name"] as string).join(", ")}` : "")}</span>
      </div>
    );
  }
  return (
    <div className={cx(styles["bubbleRow"], mine && styles["mine"])}>
      <Avatar name={mine ? "You" : "Enola"} size="sm" enola={!mine} />
      <div className={cx(styles["bubble"], mine && styles["bubbleMine"])}>
        {message.text}
        {message.tool_calls.length > 0 && (
          <span className={styles["calls"]}>
            {message.tool_calls.map((call, i) => (
              <Mono key={i} tone="accent">
                → {String(call["name"])}
              </Mono>
            ))}
          </span>
        )}
      </div>
    </div>
  );
}
