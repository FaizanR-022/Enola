import { useNavigate } from "react-router-dom";
import { useDashboard, useNotificationMutations, useTaskMutations, type Task } from "@/data";
import { useShell, useFinishBoot, useHeaderMeta } from "@/shell/ShellState";
import { Button, Card, CardRow, Dot, EmptyState, Mono, QueryState } from "@/ui";
import { timeLabel } from "@/lib/format";
import { Grid, Screen } from "./Screen";
import { HeldBanner } from "./shared/HeldBanner";
import { PersonRow } from "./shared/PersonRow";
import { TaskRow } from "./shared/TaskRow";
import styles from "./Dashboard.module.css";

function activityTone(kind: string): "accent" | "ok" | "held" | "danger" | "muted" {
  switch (kind) {
    case "approved":
      return "ok";
    case "held":
      return "held";
    case "rejected":
      return "danger";
    case "memory":
      return "muted";
    default:
      return "accent";
  }
}

export function Dashboard() {
  const dashboard = useDashboard();
  const navigate = useNavigate();
  const { say } = useShell();
  const tasks = useTaskMutations();
  const notifications = useNotificationMutations();
  useFinishBoot(!dashboard.isPending);
  useHeaderMeta(dashboard.data ? dashboard.data.date_label : null);

  const toggle = (task: Task) => {
    tasks.setState.mutate({ id: task.id, state: task.state === "done" ? "open" : "done" }, { onSuccess: () => say(task.state === "done" ? "Reopened" : `Done · ${task.title}`) });
  };

  return (
    <Screen>
      <QueryState status={dashboard.status} error={dashboard.error} data={dashboard.data} onRetry={() => void dashboard.refetch()} rows={5}>
        {(d) => (
          <>
            <div className={styles["heading"]}>
              <h1 className={styles["date"]}>{d.date_label}</h1>
              <span className={styles["headline"]}>{d.headline}</span>
            </div>

            {d.held.count > 0 && <HeldBanner summary={d.held.summary} />}

            {(d.brief || d.reminders.length > 0) && (
              <Grid min="320px">
                {d.brief && (
                  <Card title="Daily brief" meta={<Mono>{timeLabel(d.brief.scheduled_for)}</Mono>} edge="accent">
                    <div className={styles["brief"]}>{d.brief.body}</div>
                  </Card>
                )}
                {d.reminders.length > 0 && (
                  <Card
                    title="Reminders"
                    meta={
                      <Button variant="link" onClick={() => notifications.markAllRead.mutate()}>
                        Clear all
                      </Button>
                    }
                    flush
                    note="Due dates, deadlines and quiet threads. The worker queues these; nothing here is urgent enough to interrupt."
                  >
                    {d.reminders.map((r) => (
                      <CardRow key={r.id} align="start" interactive onClick={() => navigate(r.entity_type === "application" && r.entity_id ? `/jobs/${r.entity_id}` : r.entity_type === "person" && r.entity_id ? `/people/${r.entity_id}` : "/tasks")}>
                        <Dot tone={r.kind === "academic_deadline" ? "paper" : r.kind === "followup_nudge" ? "soft" : "muted"} className={styles["activityDot"]} />
                        <span className={styles["eventMain"]}>
                          <span className={styles["eventTitle"]}>{r.title}</span>
                          <span className={styles["eventSub"]}>{r.body}</span>
                        </span>
                        <button
                          type="button"
                          className={styles["dismiss"]}
                          aria-label="Mark read"
                          onClick={(event) => {
                            event.stopPropagation();
                            notifications.markRead.mutate(r.id);
                          }}
                        >
                          ✕
                        </button>
                      </CardRow>
                    ))}
                  </Card>
                )}
              </Grid>
            )}

            <Grid min="280px">
              <Card title="Today" meta={<Mono>{d.today.length === 1 ? "1 event" : `${d.today.length} events`}</Mono>} flush note={d.today.length ? "Nothing else scheduled." : undefined}>
                {d.today.length === 0 ? (
                  <EmptyState inline title="Nothing on the calendar today." hint="Assessments due today and interview slots land here." />
                ) : (
                  d.today.map((item) => (
                    <CardRow key={`${item.path}-${item.when}`} align="baseline" interactive onClick={() => navigate(item.path)}>
                      <Mono size={11} tone="soft" className={styles["time"]}>
                        {item.time_label}
                      </Mono>
                      <span className={styles["eventMain"]}>
                        <span className={styles["eventTitle"]}>{item.title}</span>
                        <span className={styles["eventSub"]}>{item.sub}</span>
                      </span>
                    </CardRow>
                  ))
                )}
              </Card>

              <Card
                title="Due"
                meta={
                  <Button variant="link" onClick={() => navigate("/tasks")}>
                    All tasks
                  </Button>
                }
                flush
              >
                {d.due.length === 0 ? <EmptyState inline title="Nothing due this week." /> : d.due.map((task) => <TaskRow key={task.id} task={task} onToggle={toggle} compact busy={tasks.setState.isPending} />)}
              </Card>

              <Card
                title="Going cold"
                meta={
                  <Button variant="link" onClick={() => navigate("/people")}>
                    Catalogue
                  </Button>
                }
                flush
              >
                {d.going_cold.length === 0 ? <EmptyState inline title="Nobody is going cold." hint="People with a cadence show up here once it lapses." /> : d.going_cold.map((person) => <PersonRow key={person.id} person={person} compact />)}
              </Card>

              <Card title="Enola did" meta={<Mono>last 12h</Mono>} flush note="Enola never notifies for these. They collect here; only Held actions reach you.">
                {d.activity.length === 0 ? (
                  <EmptyState inline title="Quiet for the last 12 hours." />
                ) : (
                  d.activity.map((row) => (
                    <CardRow key={row.id} align="baseline">
                      <Dot tone={activityTone(row.kind)} className={styles["activityDot"]} />
                      <span className={styles["activityText"]}>{row.summary}</span>
                      <Mono size={10}>{timeLabel(row.created_at)}</Mono>
                    </CardRow>
                  ))
                )}
              </Card>
            </Grid>
          </>
        )}
      </QueryState>
    </Screen>
  );
}
