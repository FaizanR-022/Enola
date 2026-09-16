import { useState } from "react";
import { useApprovals, useDecideApproval, type Approval } from "@/data";
import { errorMessage } from "@/lib/api";
import { cx } from "@/lib/cx";
import { heldAge } from "@/lib/format";
import { useShell, useFinishBoot, useHeaderMeta } from "@/shell/ShellState";
import { Button, Card, Dot, EmptyState, Mono, QueryState, TextArea } from "@/ui";
import { Screen } from "./Screen";
import { StepRail, type RailState } from "./shared/StepRail";
import styles from "./Approvals.module.css";

function railState(state: Approval["state"]): RailState {
  return state === "held" ? "held" : state === "approved" ? "approved" : "rejected";
}

function stateLabel(a: Approval): string {
  return a.state === "held" ? "Held · waiting on you" : a.state === "approved" ? "Approved" : "Rejected";
}

function ageLabel(a: Approval): string {
  if (a.state === "held") return `held ${heldAge(a.created_at)}`;
  return a.resolved_at ? `closed ${heldAge(a.resolved_at)} ago` : "closed";
}

function approveLabel(a: Approval): string {
  if (a.tool_name === "send_email" || a.tool_name === "send_probe") return "Approve & send";
  if (a.risk === "destructive") return `Approve ${a.tool_name.startsWith("delete") ? "delete" : "change"}`;
  return "Approve & run";
}

function resumeNote(a: Approval): string {
  if (a.state === "approved") return `Job finished. Payload kept so you can see exactly what went out.${a.resolution_note ? ` Note: ${a.resolution_note}` : ""}`;
  if (a.state === "rejected") return `Job stopped.${a.resolution_note ? ` Your reason: “${a.resolution_note}”.` : " Enola recorded the rejection."}`;
  return `Approving resumes the job at step ${a.step_index + 1} and logs the result to the activity log.`;
}

function isEmail(a: Approval): boolean {
  return a.tool_name === "send_email";
}

interface EditState {
  text: string;
  error: string | null;
}

function ApprovalCard({ approval, open, onToggle }: { approval: Approval; open: boolean; onToggle: () => void }) {
  const decide = useDecideApproval();
  const { say } = useShell();
  const [edit, setEdit] = useState<EditState | null>(null);
  const [rejectNote, setRejectNote] = useState<string | null>(null);
  const held = approval.state === "held";
  const email = isEmail(approval);
  const body = typeof approval.args["body"] === "string" ? approval.args["body"] : "";

  const currentArgs = (): Record<string, unknown> | undefined => {
    if (!edit) return undefined;
    if (email) return { ...approval.args, body: edit.text };
    try {
      return JSON.parse(edit.text) as Record<string, unknown>;
    } catch {
      return undefined;
    }
  };

  const approve = () => {
    const args = currentArgs();
    if (edit && args === undefined) {
      setEdit({ ...edit, error: "That is not valid JSON." });
      return;
    }
    decide.mutate(
      { id: approval.id, approve: true, args },
      {
        onSuccess: (run) => {
          say(run.held_approval_id ? "Resumed · the job is Held again at its next step" : "Approved · job resumed and finished");
          setEdit(null);
        },
        onError: (error) => say(errorMessage(error)),
      },
    );
  };

  const reject = () => {
    decide.mutate(
      { id: approval.id, approve: false, note: rejectNote ?? "" },
      {
        onSuccess: () => {
          say("Rejected · Enola recorded the reason and stopped the job");
          setRejectNote(null);
        },
        onError: (error) => say(errorMessage(error)),
      },
    );
  };

  const stateTone = approval.state === "held" ? "held" : approval.state === "approved" ? "ok" : "danger";

  return (
    <Card edge={approval.state === "held" ? "held" : approval.state === "approved" ? "ok" : "danger"} tone={held ? "raised" : "flat"} flush className={styles["card"]}>
      <button type="button" className={styles["head"]} onClick={onToggle} aria-expanded={open}>
        <Dot tone={stateTone} size={7} pulse={held} className={styles["headDot"]} />
        <span className={styles["headMain"]}>
          <span className={styles["headMeta"]}>
            <Mono upper tone={stateTone} bold>
              {stateLabel(approval)}
            </Mono>
            <Mono>{approval.job_label.replace(/^chat · /, "")}</Mono>
            <Mono>{ageLabel(approval)}</Mono>
            <Mono>{approval.risk}</Mono>
          </span>
          <span className={styles["title"]}>{titleFor(approval)}</span>
          {approval.rationale && <span className={styles["why"]}>{approval.rationale}</span>}
          <StepRail steps={approval.step_labels} index={approval.step_index} state={railState(approval.state)} label={approval.job_label.split(" · ")[0]} />
        </span>
        <Mono className={styles["chevron"]}>{open ? "—" : "+"}</Mono>
      </button>

      {open && (
        <div className={styles["body"]}>
          <Mono upper>{email ? "Exact payload · nothing has been sent" : "Exact payload · nothing has been written"}</Mono>

          {email ? (
            <div className={styles["mail"]}>
              <div className={styles["mailHead"]}>
                <span>
                  <Mono>to&nbsp;&nbsp;</Mono>
                  {String(approval.args["to"] ?? "")}
                </span>
                <span>
                  <Mono>re&nbsp;&nbsp;</Mono>
                  {String(approval.args["subject"] ?? "")}
                </span>
              </div>
              {edit ? (
                <TextArea bare value={edit.text} onChange={(e) => setEdit({ text: e.target.value, error: null })} className={styles["mailEditor"]} spellCheck={false} />
              ) : (
                <pre className={styles["mailBody"]}>{body}</pre>
              )}
              <div className={styles["mailFoot"]}>
                <Mono>{(edit ? edit.text : body).trim().split(/\s+/).filter(Boolean).length} words</Mono>
                <Mono tone={held ? "held" : "muted"}>{held ? "not sent" : approval.state}</Mono>
              </div>
            </div>
          ) : edit ? (
            <TextArea value={edit.text} onChange={(e) => setEdit({ text: e.target.value, error: null })} className={styles["jsonEditor"]} spellCheck={false} />
          ) : (
            <div className={styles["fields"]}>
              {Object.entries(approval.args).map(([key, value]) => (
                <div key={key} className={styles["field"]}>
                  <span className={styles["fieldKey"]}>{key}</span>
                  <span className={styles["fieldValue"]}>{typeof value === "string" ? value : JSON.stringify(value)}</span>
                </div>
              ))}
              {Object.keys(approval.args).length === 0 && <div className={styles["field"]}>(no arguments)</div>}
            </div>
          )}
          {edit?.error && <Mono tone="danger">{edit.error}</Mono>}

          {rejectNote !== null && held && (
            <TextArea value={rejectNote} onChange={(e) => setRejectNote(e.target.value)} placeholder="Why not? Enola keeps this as a correction." rows={2} />
          )}

          <div className={styles["actions"]}>
            {held ? (
              <>
                <Button variant="primary" onClick={approve} busy={decide.isPending}>
                  {approveLabel(approval)}
                </Button>
                <Button onClick={() => setEdit(edit ? null : { text: email ? body : JSON.stringify(approval.args, null, 2), error: null })} disabled={decide.isPending}>
                  {edit ? "Discard edit" : "Edit"}
                </Button>
                {rejectNote === null ? (
                  <Button variant="danger" onClick={() => setRejectNote("")} disabled={decide.isPending}>
                    Reject
                  </Button>
                ) : (
                  <Button variant="danger" onClick={reject} busy={decide.isPending}>
                    Confirm reject
                  </Button>
                )}
              </>
            ) : (
              <Button disabled>{approval.state === "approved" ? "Approved" : "Rejected"}</Button>
            )}
            <span className={styles["spacer"]} />
            <span className={cx(styles["resumeNote"])}>{resumeNote(approval)}</span>
          </div>
        </div>
      )}
    </Card>
  );
}

function titleFor(a: Approval): string {
  const to = typeof a.args["to"] === "string" ? a.args["to"] : null;
  if (a.tool_name === "send_email") return `Send email to ${to ?? "someone"}${typeof a.args["subject"] === "string" ? ` — ${a.args["subject"]}` : ""}`;
  if (a.tool_name === "send_probe") return `Send probe message to ${to ?? "?"}`;
  if (a.tool_name === "delete_person") return `Delete person #${String(a.args["person_id"] ?? "?")}`;
  return `${a.tool_name.replace(/_/g, " ")}`;
}

export function Approvals() {
  const approvals = useApprovals();
  const [openId, setOpenId] = useState<number | null>(null);
  useFinishBoot();
  useHeaderMeta(approvals.data ? `${approvals.data.items.filter((a) => a.state === "held").length} held` : null);

  return (
    <Screen>
      <div className={styles["heading"]}>
        <h1 className={styles["h1"]}>Approvals</h1>
        <span className={styles["sub"]}>Background jobs paused until you decide. Enola drafts; you send.</span>
      </div>
      <QueryState status={approvals.status} error={approvals.error} data={approvals.data} onRetry={() => void approvals.refetch()} rows={4}>
        {(page) => {
          const heldFirst = page.items;
          const firstHeld = heldFirst.find((a) => a.state === "held");
          const effectiveOpen = openId ?? firstHeld?.id ?? null;
          if (heldFirst.length === 0) {
            return <EmptyState title="Nothing is waiting on you." hint="When Enola wants to send, post or delete something, it stops here first. Ask it to do something outbound from Chat to see one." />;
          }
          return (
            <>
              {heldFirst.map((a) => (
                <ApprovalCard key={a.id} approval={a} open={effectiveOpen === a.id} onToggle={() => setOpenId(effectiveOpen === a.id ? -1 : a.id)} />
              ))}
              <div className={styles["footnote"]}>Approved items keep their payload so you can see exactly what went out. Rejections are fed back as a correction: Enola records why and adjusts.</div>
            </>
          );
        }}
      </QueryState>
    </Screen>
  );
}
