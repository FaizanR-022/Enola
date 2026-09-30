/** Projects. "Remind me what this repo was." A registry, deliberately shallow:
 *  stack, a surface-level structure summary, status, linked tasks. Never a code browser. */

import { useState, type FormEvent } from "react";
import { useProjectMutations, useProjects, useTasks, type Project, type ProjectCreate } from "@/data";
import type { Schemas } from "@/lib/api";
import { errorMessage } from "@/lib/api";
import { agoLabel, dateLabel } from "@/lib/format";
import { useFinishBoot, useHeaderMeta, useShell } from "@/shell/ShellState";
import { Badge, Button, Card, Dot, EmptyState, Field, Input, Mono, QueryState, ScreenHeader, Select, Sheet, TextArea } from "@/ui";
import { Grid, Screen } from "./Screen";
import styles from "./Projects.module.css";

type Status = Schemas["ProjectStatus"];
const STATUSES: Status[] = ["active", "coursework", "shelved", "archived"];

function statusTone(status: Status): "ok" | "accent" | "muted" {
  return status === "active" ? "ok" : status === "coursework" ? "accent" : "muted";
}

export function Projects() {
  const [filter, setFilter] = useState<Status | undefined>(undefined);
  const [adding, setAdding] = useState(false);
  const projects = useProjects(filter);
  useFinishBoot();
  useHeaderMeta(projects.data ? `${projects.data.total} repos` : "");
  return (
    <Screen>
      <ScreenHeader
        title="Projects"
        subtitle="“Remind me what this repo was.” Deliberately shallow."
        actions={
          <Button size="sm" variant="primary" onClick={() => setAdding(true)}>
            Add project
          </Button>
        }
      />
      <div className={styles["toolbar"]}>
        <Button size="sm" variant={filter === undefined ? "primary" : "ghost"} onClick={() => setFilter(undefined)}>
          All
        </Button>
        {STATUSES.map((s) => (
          <Button key={s} size="sm" variant={filter === s ? "primary" : "ghost"} onClick={() => setFilter(s)}>
            {s}
          </Button>
        ))}
      </div>
      <QueryState status={projects.status} error={projects.error} data={projects.data} onRetry={() => void projects.refetch()} rows={4}>
        {(page) =>
          page.items.length === 0 ? (
            <EmptyState
              title={filter ? `No ${filter} projects.` : "No projects registered."}
              hint="Add a repo with its stack and a one-line summary. Enola uses this to answer “what was that repo?”, nothing more."
              action={
                <Button size="sm" onClick={() => setAdding(true)}>
                  Add project
                </Button>
              }
            />
          ) : (
            <Grid min="288px">
              {page.items.map((p) => (
                <ProjectCard key={p.id} project={p} />
              ))}
            </Grid>
          )
        }
      </QueryState>
      {adding && <ProjectSheet onClose={() => setAdding(false)} />}
    </Screen>
  );
}

function ProjectCard({ project: p }: { project: Project }) {
  const { update } = useProjectMutations();
  const { say } = useShell();
  const [showTasks, setShowTasks] = useState(false);
  return (
    <Card>
      <div className={styles["head"]}>
        <Dot size={6} tone={statusTone(p.status)} />
        <Mono size={12} tone="text">
          {p.name}
        </Mono>
        <span className={styles["spacer"]} />
        <Select
          aria-label={`Status of ${p.name}`}
          className={styles["status"]}
          value={p.status}
          onChange={(e) => update.mutate({ id: p.id, body: { status: e.target.value as Status } }, { onSuccess: () => say(`${p.name} · ${e.target.value}`) })}
        >
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </Select>
      </div>
      <p className={styles["summary"]}>{p.summary || "No summary yet."}</p>
      {p.structure_summary && <pre className={styles["structure"]}>{p.structure_summary}</pre>}
      {p.stack.length > 0 && (
        <div className={styles["stack"]}>
          {p.stack.map((s) => (
            <Badge key={s} tone="soft">
              {s}
            </Badge>
          ))}
        </div>
      )}
      {p.repo_url && (
        <a className={styles["link"]} href={p.repo_url} target="_blank" rel="noreferrer">
          {p.repo_url}
        </a>
      )}
      <div className={styles["foot"]}>
        <Button variant="link" onClick={() => setShowTasks((v) => !v)} disabled={p.linked_task_count === 0} aria-expanded={showTasks}>
          {p.linked_task_count} linked {p.linked_task_count === 1 ? "task" : "tasks"}
        </Button>
        <Mono>{p.last_touched_at ? `touched ${agoLabel(p.last_touched_at)}` : "never touched"}</Mono>
      </div>
      {showTasks && <LinkedTasks projectId={p.id} />}
    </Card>
  );
}

function LinkedTasks({ projectId }: { projectId: number }) {
  const tasks = useTasks(undefined, { entity_type: "project", entity_id: projectId });
  return (
    <QueryState status={tasks.status} error={tasks.error} data={tasks.data} onRetry={() => void tasks.refetch()} rows={2}>
      {(page) =>
        page.items.length === 0 ? (
          <EmptyState inline title="No open tasks linked." />
        ) : (
          <ul className={styles["tasks"]}>
            {page.items.map((t) => (
              <li key={t.id} className={styles["task"]}>
                <span className={styles["taskTitle"]}>{t.title}</span>
                <Mono tone={t.state === "done" ? "muted" : "soft"}>{t.state === "done" ? "done" : t.due_at ? dateLabel(t.due_at) : "no date"}</Mono>
              </li>
            ))}
          </ul>
        )
      }
    </QueryState>
  );
}

function ProjectSheet({ onClose }: { onClose: () => void }) {
  const { create } = useProjectMutations();
  const { say } = useShell();
  const [name, setName] = useState("");
  const [repo, setRepo] = useState("");
  const [status, setStatus] = useState<Status>("active");
  const [stack, setStack] = useState("");
  const [summary, setSummary] = useState("");
  const [error, setError] = useState<string | null>(null);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return setError("Give it a name, usually owner/repo.");
    const body: ProjectCreate = {
      name: name.trim(),
      repo_url: repo.trim(),
      local_path: "",
      status,
      summary: summary.trim(),
      stack: stack
        .split(",")
        .map((s) => s.trim().toLowerCase())
        .filter(Boolean),
      structure_summary: "",
      last_touched_at: new Date().toISOString(),
    };
    try {
      await create.mutateAsync(body);
      say(`Added ${body.name}`);
      onClose();
    } catch (err) {
      setError(errorMessage(err));
    }
  };
  return (
    <Sheet
      open
      onClose={onClose}
      title="Add project"
      footer={
        <>
          <Button variant="primary" type="submit" form="project-form" busy={create.isPending}>
            Save
          </Button>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
        </>
      }
    >
      <form id="project-form" className={styles["form"]} onSubmit={(e) => void submit(e)}>
        <Field label="Name">{(id) => <Input id={id} mono value={name} onChange={(e) => setName(e.target.value)} placeholder="faizan/raft-lite" autoFocus />}</Field>
        <Field label="Repo URL" hint="Optional.">{(id) => <Input id={id} mono value={repo} onChange={(e) => setRepo(e.target.value)} placeholder="https://github.com/…" />}</Field>
        <Field label="Status">
          {(id) => (
            <Select id={id} value={status} onChange={(e) => setStatus(e.target.value as Status)}>
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Stack" hint="Comma-separated.">{(id) => <Input id={id} value={stack} onChange={(e) => setStack(e.target.value)} placeholder="go, grpc" />}</Field>
        <Field label="Summary" hint="One or two lines: what it is and what state it's in.">{(id) => <TextArea id={id} rows={3} value={summary} onChange={(e) => setSummary(e.target.value)} />}</Field>
        {error && <Mono tone="danger">{error}</Mono>}
      </form>
    </Sheet>
  );
}
