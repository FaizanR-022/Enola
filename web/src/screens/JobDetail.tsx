import { useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { useApplication, useApplicationEvents, useJobMutations, type Application, type ApplicationEvent } from "@/data";
import { ApplicationEventKind, ApplicationStage } from "@/lib/enums.generated";
import { dateLabel, dueLabel, fromDatetimeLocal, toDatetimeLocal } from "@/lib/format";
import { useFinishBoot, useHeaderMeta, useShell } from "@/shell/ShellState";
import { Avatar, Badge, Button, Card, Dot, EmptyState, Field, Input, Mono, QueryState, Select } from "@/ui";
import { Grid, Screen, Stack } from "./Screen";
import styles from "./JobDetail.module.css";

const STAGE_LABEL: Record<Application["stage"], string> = { saved: "Saved", applied: "Applied", screening: "Screening", interview: "Interview", offer: "Offer", closed: "Closed" };

function eventTone(event: ApplicationEvent): "accent" | "held" | "ok" | "danger" | "line" {
  switch (event.kind) {
    case "held":
      return "held";
    case "rejected":
      return "danger";
    case "offer":
      return "ok";
    default:
      return "accent";
  }
}

export function JobDetail() {
  const params = useParams();
  const id = Number(params["id"]);
  const app = useApplication(id);
  useFinishBoot();
  useHeaderMeta(app.data ? app.data.company_name : null);
  return (
    <Screen>
      <Link to="/jobs" className={styles["back"]}>
        ← Pipeline
      </Link>
      <QueryState status={app.status} error={app.error} data={app.data} onRetry={() => void app.refetch()} rows={6}>
        {(a) => <Body app={a} />}
      </QueryState>
    </Screen>
  );
}

function Body({ app }: { app: Application }) {
  const events = useApplicationEvents(app.id);
  const mutations = useJobMutations();
  const { say } = useShell();
  const [note, setNote] = useState("");
  const [editingNext, setEditingNext] = useState(false);
  const [nextAction, setNextAction] = useState(app.next_action);
  const [nextAt, setNextAt] = useState(toDatetimeLocal(app.next_action_at));

  const setStage = (stage: Application["stage"]) => mutations.updateApplication.mutate({ id: app.id, body: { stage } }, { onSuccess: () => say(`Moved to ${STAGE_LABEL[stage]}`) });

  const saveNext = (event: FormEvent) => {
    event.preventDefault();
    mutations.updateApplication.mutate(
      { id: app.id, body: { next_action: nextAction.trim(), next_action_at: fromDatetimeLocal(nextAt) } },
      {
        onSuccess: () => {
          setEditingNext(false);
          say("Next action saved");
        },
      },
    );
  };

  const addNote = (event: FormEvent) => {
    event.preventDefault();
    if (!note.trim()) return;
    mutations.addEvent.mutate({ application_id: app.id, kind: ApplicationEventKind.NOTE, summary: note.trim(), occurred_at: new Date().toISOString(), source: "you" }, { onSuccess: () => setNote("") });
  };

  return (
    <>
      <div className={styles["header"]}>
        <div className={styles["identity"]}>
          <h1 className={styles["title"]}>{app.role_title}</h1>
          <div className={styles["sub"]}>
            {app.company_name}
            {app.location_label ? ` · ${app.location_label}` : ""}
            {app.pay_label ? ` · ${app.pay_label}` : ""}
          </div>
        </div>
        <label className={styles["stage"]}>
          <Dot tone={app.stage === "screening" ? "held" : app.stage === "interview" ? "ok" : app.stage === "closed" ? "danger" : "muted"} size={6} />
          <Select value={app.stage} onChange={(e) => setStage(e.target.value as Application["stage"])} aria-label="Stage" className={styles["stageSelect"]} disabled={mutations.updateApplication.isPending}>
            {Object.values(ApplicationStage).map((s) => (
              <option key={s} value={s}>
                {STAGE_LABEL[s]}
              </option>
            ))}
          </Select>
        </label>
      </div>

      {editingNext ? (
        <form className={styles["next"]} onSubmit={saveNext}>
          <Mono upper tone="accent" bold>
            Next action
          </Mono>
          <Input value={nextAction} onChange={(e) => setNextAction(e.target.value)} placeholder="Screening call with Ayesha" className={styles["nextInput"]} autoFocus />
          <Input type="datetime-local" value={nextAt} onChange={(e) => setNextAt(e.target.value)} mono className={styles["nextWhen"]} />
          <Button size="sm" variant="primary" type="submit" busy={mutations.updateApplication.isPending}>
            Save
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setEditingNext(false)}>
            Cancel
          </Button>
        </form>
      ) : (
        <button type="button" className={styles["next"]} onClick={() => setEditingNext(true)}>
          <Mono upper tone="accent" bold>
            Next action
          </Mono>
          <span className={styles["nextText"]}>{app.next_action || "Nothing planned. Click to set one."}</span>
          {app.next_action_at && (
            <Mono size={11} tone="soft">
              {dueLabel(app.next_action_at)}
            </Mono>
          )}
        </button>
      )}

      <Grid min="300px">
        <Stack>
          <Card title="The posting">
            {app.posting_summary ? <p className={styles["posting"]}>{app.posting_summary}</p> : <EmptyState inline title="No summary saved." hint="Paste the posting's key lines here from the pipeline sheet, or ask Enola to structure the URL." />}
            {app.posting_url && (
              <a href={app.posting_url} target="_blank" rel="noreferrer" className={styles["url"]}>
                <Mono tone="accent">{app.posting_url}</Mono>
              </a>
            )}
            {app.tags.length > 0 && (
              <div className={styles["tags"]}>
                {app.tags.map((tag) => (
                  <Badge key={tag} tone="soft">
                    {tag}
                  </Badge>
                ))}
              </div>
            )}
          </Card>
          <Card title="Referral">
            {app.referral_person_name && app.referral_person_id ? (
              <div className={styles["referral"]}>
                <Avatar name={app.referral_person_name} />
                <span className={styles["referralMain"]}>
                  <span>{app.referral_person_name}</span>
                </span>
                <Link to={`/people/${app.referral_person_id}`}>Open</Link>
              </div>
            ) : (
              <EmptyState inline title="No referral linked." hint="Link someone from the People catalogue who can vouch for you here." />
            )}
          </Card>
          <Card title="Resume version sent">
            {app.resume_version ? (
              <div className={styles["resume"]}>
                <span className={styles["resumeIcon"]} aria-hidden />
                <span className={styles["resumeMain"]}>
                  <Mono size={12} tone="text">
                    {app.resume_version}
                  </Mono>
                  {app.resume_note && <span className={styles["resumeNote"]}>{app.resume_note}</span>}
                </span>
              </div>
            ) : (
              <EmptyState inline title="Not recorded." />
            )}
          </Card>
        </Stack>
        <Card title="Timeline" flush>
          <form onSubmit={addNote} className={styles["noteRow"]}>
            <Input value={note} onChange={(e) => setNote(e.target.value)} placeholder="Add a note to the timeline" aria-label="Timeline note" />
            <Button size="sm" type="submit" disabled={!note.trim()} busy={mutations.addEvent.isPending}>
              Add
            </Button>
          </form>
          <QueryState status={events.status} error={events.error} data={events.data} rows={4}>
            {(page) =>
              page.items.length === 0 ? (
                <EmptyState inline title="Nothing yet." />
              ) : (
                <div className={styles["timeline"]}>
                  {page.items.map((event, i) => (
                    <div key={event.id} className={styles["event"]}>
                      <span className={styles["eventRail"]}>
                        <Dot tone={eventTone(event)} size={7} hollow={i === 0 && event.kind === "interview"} />
                        {i < page.items.length - 1 && <span className={styles["eventLine"]} aria-hidden />}
                      </span>
                      <span className={styles["eventMain"]}>
                        <span className={styles["eventText"]}>
                          {event.summary}
                          {event.source === "enola" && <Mono tone="accent"> · enola</Mono>}
                        </span>
                        <Mono>{dateLabel(event.occurred_at)}</Mono>
                      </span>
                    </div>
                  ))}
                </div>
              )
            }
          </QueryState>
        </Card>
      </Grid>
      <Field label="Closed reason" hint="Only used once the stage is Closed.">
        {(id) => (
          <Input
            id={id}
            defaultValue={app.closed_reason}
            onBlur={(e) => {
              if (e.target.value !== app.closed_reason) mutations.updateApplication.mutate({ id: app.id, body: { closed_reason: e.target.value } });
            }}
            placeholder="Rejected 4 Sep · no reason given"
          />
        )}
      </Field>
    </>
  );
}
