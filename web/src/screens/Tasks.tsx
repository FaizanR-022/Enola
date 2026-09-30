import { useMemo, useState, type FormEvent, type KeyboardEvent } from "react";
import { useTaskMutations, useTasks, type Task } from "@/data";
import { cx } from "@/lib/cx";
import { dateLabel, fromDatetimeLocal, isoAt, parseDate } from "@/lib/format";
import { useShell, useFinishBoot, useHeaderMeta } from "@/shell/ShellState";
import { Card, EmptyState, Input, Mono, QueryState, ScreenHeader } from "@/ui";
import { Screen } from "./Screen";
import { TaskRow } from "./shared/TaskRow";
import { completeWithUndo } from "./shared/completeWithUndo";
import styles from "./Tasks.module.css";

type View = "daily" | "weekly";

interface Group {
  label: string;
  items: Task[];
}

const DAY_MS = 86_400_000;

function dayOffset(task: Task, now: Date): number | null {
  const date = parseDate(task.due_at);
  if (!date) return null;
  const a = new Date(now);
  a.setHours(0, 0, 0, 0);
  const b = new Date(date);
  b.setHours(0, 0, 0, 0);
  return Math.round((b.getTime() - a.getTime()) / DAY_MS);
}

function groupTasks(tasks: Task[], view: View, now = new Date()): Group[] {
  const overdue: Task[] = [];
  const today: Task[] = [];
  const week: Task[] = [];
  const later: Task[] = [];
  const undated: Task[] = [];
  const done: Task[] = [];
  for (const task of tasks) {
    if (task.state === "done") {
      done.push(task);
      continue;
    }
    const days = dayOffset(task, now);
    if (days === null) undated.push(task);
    else if (days < 0) overdue.push(task);
    else if (days === 0) today.push(task);
    else if (days < 7) week.push(task);
    else later.push(task);
  }
  const groups: Group[] = [
    { label: "Overdue", items: overdue },
    { label: "Today", items: today },
    { label: "This week", items: week },
  ];
  if (view === "weekly") groups.push({ label: "Later", items: later }, { label: "No date", items: undated });
  else groups.push({ label: "No date", items: undated });
  // Newest completion first, so the task you just ticked is the one you see.
  done.sort((a, b) => (b.completed_at ?? "").localeCompare(a.completed_at ?? ""));
  groups.push({ label: "Done", items: done.slice(0, view === "weekly" ? 20 : 5) });
  return groups.filter((g) => g.items.length > 0);
}

/** A date at the end of a quick-add line sets the due date.
 *
 *  Forward: "today", "tomorrow", "in 3 days", "friday", "next friday".
 *  Backward: "yesterday", "3 days ago", "last friday" — a real backlog is mostly
 *  past tense, and without these everything you enter lands on today.
 */
function parseQuickAdd(raw: string): { title: string; due_at: string | null } {
  const text = raw.trim();
  const lower = text.toLowerCase();
  const NAMES = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"];

  const weekdayBack = (name: string): number => {
    const target = NAMES.indexOf(name);
    const diff = (new Date().getDay() - target + 7) % 7;
    return -(diff === 0 ? 7 : diff);
  };
  const weekdayForward = (name: string): number => {
    const target = NAMES.indexOf(name);
    const diff = (target - new Date().getDay() + 7) % 7;
    return diff === 0 ? 7 : diff;
  };

  // Order matters: "last friday" must be tested before the bare weekday rule, which
  // would otherwise match "friday" and push it into next week.
  const rules: Array<[RegExp, (m: RegExpMatchArray) => number]> = [
    [/\blast (monday|tuesday|wednesday|thursday|friday|saturday|sunday)$/, (m) => weekdayBack(m[1] ?? "")],
    [/\b(\d+) days? ago$/, (m) => -Number(m[1])],
    [/\byesterday$/, () => -1],
    [/\btoday$/, () => 0],
    [/\btomorrow$/, () => 1],
    [/\bin (\d+) days?$/, (m) => Number(m[1])],
    [/\b(next )?(monday|tuesday|wednesday|thursday|friday|saturday|sunday)$/, (m) => weekdayForward(m[2] ?? "")],
  ];
  for (const [pattern, days] of rules) {
    const match = lower.match(pattern);
    if (match) {
      const title = text.slice(0, text.length - match[0].length).replace(/[\s,–-]+$/, "").trim();
      return { title: title || text, due_at: isoAt(days(match)) };
    }
  }
  return { title: text, due_at: null };
}

export function Tasks() {
  const [view, setView] = useState<View>("daily");
  const [draft, setDraft] = useState("");
  // For dates the sentence cannot express. Explicit beats inferred, so when this is
  // set it overrides whatever the line ends with.
  const [when, setWhen] = useState("");
  const tasks = useTasks();
  const mutations = useTaskMutations();
  const { say } = useShell();
  useFinishBoot();
  useHeaderMeta(view);

  const groups = useMemo(() => groupTasks(tasks.data?.items ?? [], view), [tasks.data, view]);

  const submit = (event: FormEvent | KeyboardEvent) => {
    event.preventDefault();
    if (!draft.trim()) return;
    const parsed = parseQuickAdd(draft);
    const picked = fromDatetimeLocal(when);
    const due = picked ?? parsed.due_at;
    mutations.create.mutate(
      { title: parsed.title, due_at: due, links: [] },
      {
        onSuccess: () => {
          setDraft("");
          setWhen("");
          say(due ? `Added · due ${dateLabel(due)}` : "Added, no date");
        },
      },
    );
  };

  const toggle = (task: Task) => completeWithUndo(task, mutations.setState.mutate, say);

  return (
    <Screen narrow>
      <ScreenHeader
        title="Tasks"
        actions={
          <div className={styles["toggle"]} role="tablist">
            {(["daily", "weekly"] as const).map((v) => (
              <button key={v} type="button" role="tab" aria-selected={view === v} className={cx(styles["tab"], view === v && styles["tabOn"])} onClick={() => setView(v)}>
                {v === "daily" ? "Daily" : "Weekly"}
              </button>
            ))}
          </div>
        }
      />
      <form className={styles["quick"]} onSubmit={submit}>
        <Mono>＋</Mono>
        <Input
          bare
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="“submit the lab report yesterday” · “chase the referral friday”"
          aria-label="Add a task"
          className={styles["quickInput"]}
          disabled={mutations.create.isPending}
        />
        <Input
          type="datetime-local"
          mono
          bare
          value={when}
          onChange={(e) => setWhen(e.target.value)}
          aria-label="Due date"
          title="Optional. Overrides a date written in the line."
          className={cx(styles["quickDate"], when && styles["quickDateSet"])}
          disabled={mutations.create.isPending}
        />
        <Mono className={styles["enter"]}>↵</Mono>
      </form>
      <QueryState status={tasks.status} error={tasks.error} data={tasks.data} onRetry={() => void tasks.refetch()} rows={6}>
        {(page) =>
          page.items.length === 0 ? (
            <EmptyState title="No tasks yet." hint="Type one above. Assessments you add in Academics land here on their own." />
          ) : (
            groups.map((group) => (
              <section key={group.label} className={styles["group"]}>
                <Mono upper className={styles["groupLabel"]}>
                  {group.label} · {group.items.length}
                </Mono>
                <Card flush>
                  {group.items.map((task) => (
                    <TaskRow key={task.id} task={task} onToggle={toggle} busy={mutations.setState.isPending} />
                  ))}
                </Card>
              </section>
            ))
          )
        }
      </QueryState>
    </Screen>
  );
}
