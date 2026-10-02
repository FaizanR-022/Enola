/** Self-learning. Goals with progress and resources, seeded from gaps in saved postings.
 *  Skill gaps are derived on the client from the tags of saved postings; nothing is stored. */

import { useMemo, useState, type FormEvent } from "react";
import { useLearningGoals, useLearningMutations, usePostings, type LearningGoal, type LearningGoalCreate } from "@/data";
import type { Schemas } from "@/lib/api";
import { errorMessage } from "@/lib/api";
import { cx } from "@/lib/cx";
import { useFinishBoot, useHeaderMeta, useShell } from "@/shell/ShellState";
import { Badge, Button, Card, EmptyState, Field, Input, Mono, QueryState, ScreenHeader, Select, Sheet, TextArea } from "@/ui";
import { Grid, Screen } from "./Screen";
import styles from "./Learning.module.css";

type GoalState = Schemas["LearningGoalState"];
const STATES: GoalState[] = ["active", "paused", "done"];

export function Learning() {
  const [filter, setFilter] = useState<GoalState | undefined>("active");
  const [adding, setAdding] = useState<string | null>(null);
  const goals = useLearningGoals(filter);
  const saved = usePostings("saved");
  useFinishBoot();
  useHeaderMeta(goals.data ? `${goals.data.total} goals` : "");

  const gaps = useMemo(() => {
    const counts = new Map<string, number>();
    for (const posting of saved.data?.items ?? []) {
      for (const tag of posting.tags) counts.set(tag, (counts.get(tag) ?? 0) + 1);
    }
    return [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 8);
  }, [saved.data]);

  return (
    <Screen narrow>
      <ScreenHeader
        title="Self-learning"
        subtitle="Goals are seeded from gaps in the postings you save."
        actions={
          <Button size="sm" variant="primary" onClick={() => setAdding("")}>
            New goal
          </Button>
        }
      />
      <Card title="Skill gaps from saved postings" flush meta={<Mono>{saved.data ? `${saved.data.total} saved` : ""}</Mono>}>
        <QueryState status={saved.status} error={saved.error} data={saved.data} onRetry={() => void saved.refetch()} rows={1}>
          {() =>
            gaps.length === 0 ? (
              <EmptyState inline title="Save a posting in Jobs and its tags land here." />
            ) : (
              <div className={styles["gaps"]}>
                {gaps.map(([skill, postings]) => (
                  <button key={skill} type="button" className={styles["gapBtn"]} onClick={() => setAdding(skill)} title={`Start a goal for ${skill}`}>
                    <Badge tone="accent" pill>
                      {skill} · {postings}
                    </Badge>
                  </button>
                ))}
              </div>
            )
          }
        </QueryState>
      </Card>
      <div className={styles["toolbar"]}>
        {STATES.map((s) => (
          <Button key={s} size="sm" variant={filter === s ? "primary" : "ghost"} onClick={() => setFilter(s)}>
            {s}
          </Button>
        ))}
        <Button size="sm" variant={filter === undefined ? "primary" : "ghost"} onClick={() => setFilter(undefined)}>
          all
        </Button>
      </div>
      <QueryState status={goals.status} error={goals.error} data={goals.data} onRetry={() => void goals.refetch()} rows={4}>
        {(page) =>
          page.items.length === 0 ? (
            <EmptyState
              title={filter ? `No ${filter} goals.` : "No goals yet."}
              hint="Tap a skill gap above to start one, or write your own."
              action={
                <Button size="sm" onClick={() => setAdding("")}>
                  New goal
                </Button>
              }
            />
          ) : (
            <Grid min="330px">
              {page.items.map((g) => (
                <GoalCard key={g.id} goal={g} />
              ))}
            </Grid>
          )
        }
      </QueryState>
      {adding !== null && <GoalSheet seed={adding} onClose={() => setAdding(null)} />}
    </Screen>
  );
}

function GoalCard({ goal: g }: { goal: LearningGoal }) {
  const { update } = useLearningMutations();
  const { say } = useShell();
  const [pct, setPct] = useState(g.progress_pct);
  const [newResource, setNewResource] = useState("");
  const [adding, setAdding] = useState(false);
  const resourcesIn = () => g.resources.map((r) => ({ label: r.label, url: r.url, done: r.done }));
  const toggle = (id: number) => {
    const resources = g.resources.map((r) => ({ label: r.label, url: r.url, done: r.id === id ? !r.done : r.done }));
    update.mutate({ id: g.id, body: { resources } });
  };
  const addResource = (e: FormEvent) => {
    e.preventDefault();
    if (!newResource.trim()) return;
    update.mutate(
      { id: g.id, body: { resources: [...resourcesIn(), { label: newResource.trim(), url: "", done: false }] } },
      {
        onSuccess: () => {
          setNewResource("");
          setAdding(false);
        },
      },
    );
  };
  const commit = () => pct !== g.progress_pct && update.mutate({ id: g.id, body: { progress_pct: pct } });
  const done = g.resources.filter((r) => r.done).length;
  return (
    <Card>
      <div className={styles["head"]}>
        <span className={styles["title"]}>{g.title}</span>
        {g.seeded_from_postings && <Badge tone="accent">from postings</Badge>}
        <Select aria-label={`State of ${g.title}`} value={g.state} onChange={(e) => update.mutate({ id: g.id, body: { state: e.target.value as GoalState } }, { onSuccess: () => say(`${g.title} · ${e.target.value}`) })}>
          {STATES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </Select>
      </div>

      {/* Why the goal exists is the most useful line on the card, so it sits directly
          under the title rather than below the controls. */}
      {g.gap_note && <span className={styles["gap"]}>{g.gap_note}</span>}

      {/* One control, not two: this was a static bar and a slider stacked, showing the
          same number twice. The slider is the bar. */}
      <div className={styles["progress"]}>
        <input
          type="range"
          min={0}
          max={100}
          step={5}
          value={pct}
          aria-label={`Progress on ${g.title}`}
          className={cx(g.seeded_from_postings ? styles["rangeAccent"] : styles["rangeSoft"])}
          onChange={(e) => setPct(Number(e.target.value))}
          onPointerUp={commit}
          onKeyUp={commit}
        />
        <Mono size={11} tone="soft">
          {pct}%
        </Mono>
      </div>

      {g.resources.length > 0 && (
        <ul className={styles["resources"]}>
          {g.resources.map((r) => (
            <li key={r.id}>
              <button type="button" className={cx(styles["resource"], r.done && styles["resourceDone"])} onClick={() => toggle(r.id)} aria-pressed={r.done}>
                <span className={styles["box"]} aria-hidden>
                  {r.done ? "✓" : ""}
                </span>
                <span className={styles["resourceLabel"]}>{r.label}</span>
              </button>
            </li>
          ))}
        </ul>
      )}

      <div className={styles["resourceFoot"]}>
        {adding ? (
          <form className={styles["resourceForm"]} onSubmit={addResource}>
            <Input
              value={newResource}
              onChange={(e) => setNewResource(e.target.value)}
              placeholder="A doc, a course, a person"
              aria-label={`Add resource to ${g.title}`}
              autoFocus
              onBlur={() => !newResource.trim() && setAdding(false)}
            />
            <Button size="sm" type="submit" disabled={!newResource.trim()}>
              Add
            </Button>
          </form>
        ) : (
          <>
            <Button variant="link" onClick={() => setAdding(true)}>
              + resource
            </Button>
            {g.resources.length > 0 && (
              <Mono>
                {done} of {g.resources.length} done
              </Mono>
            )}
          </>
        )}
      </div>
    </Card>
  );
}

function GoalSheet({ seed, onClose }: { seed: string; onClose: () => void }) {
  const { create } = useLearningMutations();
  const { say } = useShell();
  const [title, setTitle] = useState(seed ? `${seed[0]?.toUpperCase() ?? ""}${seed.slice(1)}` : "");
  const [gap, setGap] = useState(seed ? `Surfaced from saved postings tagged “${seed}”.` : "");
  const [resources, setResources] = useState("");
  const [error, setError] = useState<string | null>(null);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return setError("Give the goal a title.");
    const body: LearningGoalCreate = {
      title: title.trim(),
      gap_note: gap.trim(),
      progress_pct: 0,
      state: "active",
      seeded_from_postings: seed !== "",
      resources: resources
        .split("\n")
        .map((r) => r.trim())
        .filter(Boolean)
        .map((label) => ({ label, url: "", done: false })),
    };
    try {
      await create.mutateAsync(body);
      say(`Started “${body.title}”`);
      onClose();
    } catch (err) {
      setError(errorMessage(err));
    }
  };
  return (
    <Sheet
      open
      onClose={onClose}
      title="New goal"
      footer={
        <>
          <Button variant="primary" type="submit" form="goal-form" busy={create.isPending}>
            Save
          </Button>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
        </>
      }
    >
      <form id="goal-form" className={styles["form"]} onSubmit={(e) => void submit(e)}>
        <Field label="Goal">{(id) => <Input id={id} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="System design for backend interviews" autoFocus />}</Field>
        <Field label="Why" hint="Which postings or courses asked for it.">{(id) => <TextArea id={id} rows={2} value={gap} onChange={(e) => setGap(e.target.value)} />}</Field>
        <Field label="Resources" hint="One per line.">{(id) => <TextArea id={id} rows={3} value={resources} onChange={(e) => setResources(e.target.value)} placeholder={"DDIA ch. 5–9\nmock with Bilal"} />}</Field>
        {error && <Mono tone="danger">{error}</Mono>}
      </form>
    </Sheet>
  );
}
