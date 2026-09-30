/** Email. Read and triage only.
 *
 *  There is no send button and no draft endpoint. "Draft a reply" asks the agent, whose
 *  send_email tool is EXTERNAL — so the draft lands in Approvals as Held and nothing
 *  leaves the machine without a click. That is the whole point of the screen.
 */

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useEmailThread, useInbox, useRefreshInbox, useSendChat, type MailThread } from "@/data";
import { errorMessage } from "@/lib/api";
import { cx } from "@/lib/cx";
import { agoLabel } from "@/lib/format";
import { useFinishBoot, useHeaderMeta, useShell } from "@/shell/ShellState";
import { Avatar, Badge, Button, Card, Dot, EmptyState, Mono, QueryState } from "@/ui";
import { Screen } from "./Screen";
import styles from "./Email.module.css";

const TONES = { needs_you: "danger", ongoing: "accent", worth_knowing: "muted" } as const;

type Bucket = keyof typeof TONES;

function ThreadDetail({ id, onBack }: { id: string; onBack: () => void }) {
  const thread = useEmailThread(id);
  const navigate = useNavigate();
  const { say } = useShell();
  // One agent thread per email thread, so asking twice continues rather than restarts.
  const send = useSendChat(`email:${id}`);

  const draft = () => {
    const subject = thread.data?.subject ?? "";
    send.mutate(
      {
        text: `Read the email thread "${subject}" and draft a reply for me. Do not send it.`,
        scope: "email",
        source: "text",
      },
      {
        onSuccess: (run) =>
          say(run.held_approval_id ? "Draft written · Held in Approvals, nothing sent" : "Enola replied in chat"),
        onError: (error) => say(errorMessage(error)),
      },
    );
  };

  return (
    <>
      <button type="button" className={styles["backToList"]} onClick={onBack}>
        ← Triaged
      </button>
      <div className={styles["detailInner"]}>
        <QueryState status={thread.status} error={thread.error} data={thread.data} onRetry={() => void thread.refetch()} rows={4}>
          {(d) => (
            <>
              <div>
                <div className={styles["stateRow"]}>
                  <Mono upper tone={d.bucket === "needs_you" ? "danger" : d.bucket === "ongoing" ? "accent" : "muted"}>
                    {d.reason}
                  </Mono>
                  <Mono>
                    {d.message_count} message{d.message_count === 1 ? "" : "s"}
                  </Mono>
                </div>
                <h1 className={styles["subjectTitle"]}>{d.subject}</h1>
                <div className={styles["parties"]}>{d.parties}</div>
              </div>

              {d.summary && (
                <Card edge="accent">
                  <Mono upper tone="accent" bold>
                    Where this stands
                  </Mono>
                  <p className={styles["summary"]}>{d.summary}</p>
                </Card>
              )}

              <Card title="Thread · newest first" flush>
                {d.messages.map((m) => (
                  <div key={m.uid} className={styles["message"]}>
                    <Avatar name={m.who} size="sm" />
                    <span className={styles["messageMain"]}>
                      <span className={styles["messageHead"]}>
                        <span className={styles["who"]}>{m.who}</span>
                        <Mono>{new Date(m.when).toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}</Mono>
                      </span>
                      <span className={styles["body"]}>{m.body || "(no text body)"}</span>
                    </span>
                  </div>
                ))}
              </Card>

              <Card>
                <div className={styles["replyRow"]}>
                  <span className={styles["replyNote"]}>
                    Enola drafts; it never sends. A reply goes to Approvals and waits for you there.
                  </span>
                  <Button variant="primary" size="sm" onClick={draft} busy={send.isPending}>
                    Draft a reply
                  </Button>
                  <Button size="sm" onClick={() => navigate("/approvals")}>
                    Open approvals
                  </Button>
                </div>
                {send.isError && <Mono tone="danger">{errorMessage(send.error)}</Mono>}
              </Card>
            </>
          )}
        </QueryState>
      </div>
    </>
  );
}

export function Email() {
  const inbox = useInbox();
  const refresh = useRefreshInbox();
  const [selected, setSelected] = useState<string | null>(null);
  const [listOpen, setListOpen] = useState(true);
  useFinishBoot(!inbox.isPending);

  const data = inbox.data;
  const needs = data?.groups.find((g) => g.bucket === "needs_you")?.threads.length ?? 0;
  const filed = data?.groups.find((g) => g.bucket === "worth_knowing")?.threads.length ?? 0;
  useHeaderMeta(data?.enabled ? `${needs} need you · ${filed} filed` : null);

  // Open the first thread that wants attention, so the screen is never blank on
  // arrival. Derived rather than set in an effect: no second render, and no window
  // where `selected` is stale against a refreshed inbox.
  const active = selected ?? data?.groups.flatMap((g) => g.threads)[0]?.id ?? null;

  if (data && !data.enabled) {
    return (
      <Screen>
        <EmptyState
          title="Email isn't connected"
          hint={data.disabled_reason}
          action={
            <Button variant="ghost" onClick={() => void inbox.refetch()}>
              Try again
            </Button>
          }
        />
      </Screen>
    );
  }

  return (
    <Screen fill>
      <div className={styles["split"]}>
        <aside className={cx(styles["list"], !listOpen && styles["listHidden"])}>
          <div className={styles["listHead"]}>
            <Mono upper>Triaged</Mono>
            <span className={styles["spacer"]} />
            <Button variant="link" onClick={() => refresh.mutate()} busy={refresh.isPending}>
              Refresh
            </Button>
          </div>
          <div className={styles["listBody"]}>
            <QueryState status={inbox.status} error={inbox.error} data={inbox.data} onRetry={() => void inbox.refetch()} rows={6}>
              {(d) =>
                d.total_threads === 0 ? (
                  <EmptyState inline title="Nothing recent" hint="No mail in the last sixty messages." />
                ) : (
                  <>
                    {d.groups
                      .filter((g) => g.threads.length > 0)
                      .map((group) => (
                        <div key={group.bucket}>
                          <div className={styles["groupHead"]}>
                            <Dot tone={TONES[group.bucket as Bucket]} />
                            <Mono upper tone={group.bucket === "needs_you" ? "danger" : "soft"}>
                              {group.label}
                            </Mono>
                            <span className={styles["spacer"]} />
                            <Mono>{group.threads.length}</Mono>
                          </div>
                          {group.threads.map((m: MailThread) => (
                            <button
                              key={m.id}
                              type="button"
                              className={cx(styles["item"], active === m.id && styles["itemOn"])}
                              onClick={() => {
                                setSelected(m.id);
                                setListOpen(false);
                              }}
                            >
                              <span className={styles["itemTop"]}>
                                <span className={cx(styles["from"], m.unread && styles["unread"])}>{m.from_name}</span>
                                <Mono>{agoLabel(m.when)}</Mono>
                              </span>
                              <span className={cx(styles["subject"], m.unread && styles["subjectUnread"])}>{m.subject}</span>
                              <span className={styles["itemTags"]}>
                                {m.message_count > 1 && <Badge>{m.message_count} messages</Badge>}
                                <Mono tone="accent">{m.reason}</Mono>
                              </span>
                            </button>
                          ))}
                        </div>
                      ))}
                    <div className={styles["filed"]}>
                      Read from {d.account}, newest sixty messages. Enola never marks anything read, moves it, or
                      deletes it.
                    </div>
                  </>
                )
              }
            </QueryState>
          </div>
        </aside>

        <section className={cx(styles["detail"], listOpen && styles["detailHidden"])}>
          {active ? (
            <ThreadDetail id={active} onBack={() => setListOpen(true)} />
          ) : (
            <div className={styles["detailInner"]}>
              <EmptyState title="Nothing selected" hint="Pick a thread from the list." />
            </div>
          )}
        </section>
      </div>
    </Screen>
  );
}
