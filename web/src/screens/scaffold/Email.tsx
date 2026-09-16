/** Email scaffold. Triage buckets, thread summaries, drafts. Draft-only: sending is Held.
 *
 *  TODO(wire): there is no mail backend yet. It will need
 *    - GET /api/email/threads?bucket=needs_you|ongoing|worth_knowing   → MAIL_GROUPS
 *    - GET /api/email/threads/{id}                                    → MAIL_DETAILS (summary + messages)
 *    - POST /api/email/threads/{id}/draft  → runs the agent; the send_email tool is
 *      EXTERNAL, so the draft lands in Approvals as Held. Never a direct send path.
 *  Ingestion (IMAP read-only, triage classification) is a worker job that writes
 *  thread summaries; it must not store credentials outside the environment.
 */

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { cx } from "@/lib/cx";
import { useFinishBoot, useHeaderMeta, useShell } from "@/shell/ShellState";
import { Avatar, Badge, Button, Card, Dot, Mono } from "@/ui";
import { Screen } from "../Screen";
import { MAIL_DETAILS, MAIL_FILED, MAIL_GROUPS } from "./mock";
import styles from "./Email.module.css";

export function Email() {
  const [selected, setSelected] = useState("m1");
  const [listOpen, setListOpen] = useState(true);
  const navigate = useNavigate();
  const { say } = useShell();
  useFinishBoot();
  useHeaderMeta(`3 need you · ${MAIL_FILED} filed`);
  const detail = MAIL_DETAILS[selected] ?? MAIL_DETAILS["m1"]!;

  return (
    <Screen fill>
      <div className={styles["split"]}>
        <aside className={cx(styles["list"], !listOpen && styles["listHidden"])}>
          <div className={styles["listHead"]}>
            <Mono upper>Triaged</Mono>
            <span className={styles["spacer"]} />
            <Mono>gmail · you@</Mono>
          </div>
          <div className={styles["listBody"]}>
            {MAIL_GROUPS.map((group) => (
              <div key={group.label}>
                <div className={styles["groupHead"]}>
                  <Dot tone={group.tone} />
                  <Mono upper tone={group.tone === "held" ? "held" : "soft"}>
                    {group.label}
                  </Mono>
                  <span className={styles["spacer"]} />
                  <Mono>{group.items.length}</Mono>
                </div>
                {group.items.map((m) => (
                  <button
                    key={m.id}
                    type="button"
                    className={cx(styles["item"], selected === m.id && styles["itemOn"])}
                    onClick={() => {
                      setSelected(m.id);
                      setListOpen(false);
                    }}
                  >
                    <span className={styles["itemTop"]}>
                      <span className={cx(styles["from"], m.unread && styles["unread"])}>{m.from}</span>
                      <Mono>{m.when}</Mono>
                    </span>
                    <span className={cx(styles["subject"], m.unread && styles["subjectUnread"])}>{m.subject}</span>
                    <span className={styles["itemTags"]}>
                      {m.thread && <Badge>{m.thread}</Badge>}
                      {m.tie && <Mono tone="accent">{m.tie}</Mono>}
                    </span>
                  </button>
                ))}
              </div>
            ))}
            <div className={styles["filed"]}>{MAIL_FILED} more arrived today: newsletters, job alerts and receipts. Enola filed them and will not mention them again.</div>
          </div>
        </aside>

        <section className={cx(styles["detail"], listOpen && styles["detailHidden"])}>
          <button type="button" className={styles["backToList"]} onClick={() => setListOpen(true)}>
            ← Triaged
          </button>
          <div className={styles["detailInner"]}>
            <div>
              <div className={styles["stateRow"]}>
                <Mono upper tone={detail.stateTone}>
                  {detail.state}
                </Mono>
                <Mono>{detail.thread}</Mono>
              </div>
              <h1 className={styles["subjectTitle"]}>{detail.subject}</h1>
              <div className={styles["parties"]}>{detail.parties}</div>
            </div>
            <Card edge="accent">
              <Mono upper tone="accent" bold>
                Where this stands
              </Mono>
              <p className={styles["summary"]}>{detail.summary}</p>
              <p className={styles["ask"]}>{detail.ask}</p>
            </Card>
            <Card title="Thread · newest first" flush>
              {detail.messages.map((m, i) => (
                <div key={i} className={styles["message"]}>
                  <Avatar name={m.who === "You" ? "You" : m.who} size="sm" />
                  <span className={styles["messageMain"]}>
                    <span className={styles["messageHead"]}>
                      <span className={styles["who"]}>{m.who}</span>
                      <Mono>{m.when}</Mono>
                    </span>
                    <span className={styles["body"]}>{m.body}</span>
                  </span>
                </div>
              ))}
            </Card>
            <Card>
              <div className={styles["replyRow"]}>
                <span className={styles["replyNote"]}>{detail.replyNote}</span>
                <Button variant="primary" size="sm" onClick={() => say("Draft written · Held in Approvals, nothing sent")}>
                  Draft a reply
                </Button>
                <Button size="sm" onClick={() => navigate("/approvals")}>
                  Open approvals
                </Button>
              </div>
            </Card>
          </div>
        </section>
      </div>
    </Screen>
  );
}
