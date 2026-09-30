import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { usePeople, usePeopleMutations, usePerson, usePersonInteractions, usePersonMoney, useTaskMutations, useTasks, type Person as PersonType } from "@/data";
import { errorMessage } from "@/lib/api";
import { cx } from "@/lib/cx";
import { InteractionKind } from "@/lib/enums.generated";
import { agoLabel, dateLabel, signedPkr } from "@/lib/format";
import { useFinishBoot, useHeaderMeta, useShell } from "@/shell/ShellState";
import { Avatar, Badge, Button, Card, CardRow, EmptyState, Field, Input, Mono, QueryState, Select, Sheet, TextArea } from "@/ui";
import { Grid, Screen } from "./Screen";
import { TaskRow } from "./shared/TaskRow";
import styles from "./Person.module.css";

export function Person() {
  const params = useParams();
  const id = Number(params["id"]);
  const person = usePerson(id);
  useFinishBoot();
  useHeaderMeta(person.data ? person.data.name : null);

  return (
    <Screen narrow>
      <Link to="/people" className={styles["back"]}>
        ← People
      </Link>
      <QueryState status={person.status} error={person.error} data={person.data} onRetry={() => void person.refetch()} rows={5}>
        {(p) => <PersonBody person={p} />}
      </QueryState>
    </Screen>
  );
}

function PersonBody({ person }: { person: PersonType }) {
  const navigate = useNavigate();
  const { say } = useShell();
  const mutations = usePeopleMutations();
  const interactions = usePersonInteractions(person.id);
  const money = usePersonMoney(person.id);
  const tasks = useTasks("open", { entity_type: "person", entity_id: person.id });
  const taskMutations = useTaskMutations();
  const [editing, setEditing] = useState(false);
  const [notes, setNotes] = useState(person.notes);
  const [summary, setSummary] = useState("");
  const [kind, setKind] = useState<string>(InteractionKind.NOTE);

  useEffect(() => setNotes(person.notes), [person.id, person.notes]);

  const saveNotes = () => {
    if (notes === person.notes) return;
    mutations.update.mutate({ id: person.id, body: { notes } }, { onSuccess: () => say("Notes saved") });
  };

  const addInteraction = (event: FormEvent) => {
    event.preventDefault();
    if (!summary.trim()) return;
    mutations.addInteraction.mutate(
      { person_id: person.id, kind: kind as PersonType extends never ? never : "call" | "email" | "message" | "meeting" | "note", summary: summary.trim(), occurred_at: new Date().toISOString(), source: "you" },
      {
        onSuccess: () => {
          setSummary("");
          say("Logged · last contact updated");
        },
      },
    );
  };

  const remove = () => {
    if (!window.confirm(`Delete ${person.name} from the catalogue? Interactions and splits go with them.`)) return;
    mutations.remove.mutate(person.id, {
      onSuccess: () => {
        say(`Deleted ${person.name}`);
        navigate("/people");
      },
    });
  };

  const lastTone = person.going_cold ? "danger" : "neutral";

  return (
    <>
      <div className={styles["header"]}>
        <Avatar name={person.name} size="lg" />
        <div className={styles["identity"]}>
          <h1 className={styles["name"]}>{person.name}</h1>
          <div className={styles["role"]}>{person.role || "No role recorded"}</div>
        </div>
        <Button size="sm" variant="ghost" onClick={() => setEditing(true)}>
          Edit
        </Button>
        <Badge tone={lastTone} pill>
          last contacted {agoLabel(person.last_contacted_at)}
        </Badge>
      </div>
      <div className={styles["tags"]}>
        {person.tags.map((tag) => (
          <Badge key={tag} tone="soft" pill>
            {tag}
          </Badge>
        ))}
        {person.can_refer && (
          <Badge tone="accent" pill>
            can refer
          </Badge>
        )}
        {person.cadence_days !== null && person.cadence_days !== undefined && <Mono>cadence {person.cadence_days}d</Mono>}
        {person.how_we_met && <Mono>met: {person.how_we_met}</Mono>}
      </div>

      <Grid min="280px">
        <Card title="Notes" meta={notes !== person.notes ? <Button variant="link" onClick={saveNotes}>Save</Button> : undefined}>
          <TextArea bare value={notes} onChange={(e) => setNotes(e.target.value)} onBlur={saveNotes} placeholder="What you know about them, in your words." rows={6} className={styles["notes"]} />
        </Card>
        <Card title="Interactions" flush>
          <form onSubmit={addInteraction} className={styles["addRow"]}>
            <Select value={kind} onChange={(e) => setKind(e.target.value)} aria-label="Kind" className={styles["kind"]}>
              {Object.values(InteractionKind).map((k) => (
                <option key={k} value={k}>
                  {k}
                </option>
              ))}
            </Select>
            <Input value={summary} onChange={(e) => setSummary(e.target.value)} placeholder="What happened" aria-label="Interaction summary" />
            <Button type="submit" size="sm" busy={mutations.addInteraction.isPending} disabled={!summary.trim()}>
              Log
            </Button>
          </form>
          <QueryState status={interactions.status} error={interactions.error} data={interactions.data} rows={3}>
            {(page) =>
              page.items.length === 0 ? (
                <EmptyState inline title="No touchpoints yet." />
              ) : (
                page.items.map((row) => (
                  <CardRow key={row.id} align="baseline">
                    <Mono className={styles["when"]}>{dateLabel(row.occurred_at)}</Mono>
                    <span className={styles["text"]}>
                      {row.summary}
                      {row.source === "enola" && <Mono tone="accent"> · enola</Mono>}
                    </span>
                    <Mono>{row.kind}</Mono>
                  </CardRow>
                ))
              )
            }
          </QueryState>
        </Card>
      </Grid>

      <Card title="Shared money" meta={<Mono tone={person.balance > 0 ? "ok" : person.balance < 0 ? "danger" : "muted"}>net {signedPkr(person.balance)}</Mono>} flush note="Settling only records it here. Enola never moves money.">
        <QueryState status={money.status} error={money.error} data={money.data} rows={2}>
          {(rows) =>
            rows.length === 0 ? (
              <EmptyState inline title="Nothing shared." hint="Splits from Finance show up here." />
            ) : (
              rows.map((row) => (
                <CardRow key={row.split_id}>
                  <Mono className={styles["when"]}>{dateLabel(row.occurred_at)}</Mono>
                  <span className={styles["text"]}>{row.title}</span>
                  <Mono size={12} tone={row.settled ? "muted" : row.amount > 0 ? "ok" : "danger"}>
                    {row.settled ? "settled" : Number(row.allocated) > 0 ? `${signedPkr(row.amount)} · ${signedPkr(Number(row.allocated) * Math.sign(-row.amount))} paid` : signedPkr(row.amount)}
                  </Mono>
                </CardRow>
              ))
            )
          }
        </QueryState>
      </Card>

      <Card title="Linked tasks" flush>
        <QueryState status={tasks.status} error={tasks.error} data={tasks.data} rows={2}>
          {(page) => (page.items.length === 0 ? <EmptyState inline title="No open tasks link here." /> : page.items.map((t) => <TaskRow key={t.id} task={t} onToggle={(task) => taskMutations.setState.mutate({ id: task.id, state: "done" })} compact />))}
        </QueryState>
      </Card>

      <div className={styles["danger"]}>
        <Button variant="danger" size="sm" onClick={remove} busy={mutations.remove.isPending}>
          Delete person
        </Button>
      </div>

      {editing && <PersonEditSheet person={person} onClose={() => setEditing(false)} />}
    </>
  );
}

/** Edit who someone is. Tags are free text with no registry — a tag exists because a
 *  person carries it — so every tag already in use is offered as a chip. Typing "uni"
 *  when "university" exists silently splits a filter in two, and nothing warns you. */
function PersonEditSheet({ person, onClose }: { person: PersonType; onClose: () => void }) {
  const mutations = usePeopleMutations();
  const { say } = useShell();
  const everyone = usePeople({});
  const [name, setName] = useState(person.name);
  const [role, setRole] = useState(person.role);
  const [tagText, setTagText] = useState(person.tags.join(", "));
  const [canRefer, setCanRefer] = useState(person.can_refer);
  const [cadence, setCadence] = useState(person.cadence_days === null || person.cadence_days === undefined ? "" : String(person.cadence_days));
  const [error, setError] = useState<string | null>(null);

  const chosen = useMemo(() => tagText.split(",").map((s) => s.trim()).filter(Boolean), [tagText]);

  const known = useMemo(() => {
    const all = new Set<string>();
    for (const p of everyone.data?.items ?? []) for (const tag of p.tags) all.add(tag);
    return [...all].sort();
  }, [everyone.data]);

  const toggleTag = (tag: string) => {
    const next = chosen.includes(tag) ? chosen.filter((t) => t !== tag) : [...chosen, tag];
    setTagText(next.join(", "));
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!name.trim()) return setError("A person needs a name.");
    try {
      await mutations.update.mutateAsync({
        id: person.id,
        body: {
          name: name.trim(),
          role: role.trim(),
          // Sent whole: the server reconciles the list, adding and removing to match.
          tags: chosen,
          can_refer: canRefer,
          cadence_days: cadence ? Number(cadence) : null,
        },
      });
      say(`Updated ${name.trim()}`);
      onClose();
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  return (
    <Sheet
      open
      onClose={onClose}
      title={`Edit ${person.name}`}
      footer={
        <>
          <Button variant="primary" type="submit" form="edit-person" busy={mutations.update.isPending} disabled={!name.trim()}>
            Save
          </Button>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
        </>
      }
    >
      <form id="edit-person" onSubmit={(e) => void submit(e)} className={styles["form"]}>
        <Field label="Name">{(id) => <Input id={id} value={name} onChange={(e) => setName(e.target.value)} autoFocus />}</Field>
        <Field label="Role">{(id) => <Input id={id} value={role} onChange={(e) => setRole(e.target.value)} placeholder="Technical recruiter · <company>" />}</Field>
        <Field label="Tags" hint="Comma-separated. Tap one below to add or remove it.">
          {(id) => <Input id={id} value={tagText} onChange={(e) => setTagText(e.target.value)} placeholder="recruiter, alumni, can refer" />}
        </Field>
        {known.length > 0 && (
          <div className={styles["tagPicker"]}>
            {known.map((tag) => (
              <button key={tag} type="button" onClick={() => toggleTag(tag)} className={cx(styles["tagChip"], chosen.includes(tag) && styles["tagChipOn"])}>
                {tag}
              </button>
            ))}
          </div>
        )}
        <Field label="Can refer" hint="Shows on the People screen as a filter.">
          {(id) => (
            <Select id={id} value={canRefer ? "yes" : "no"} onChange={(e) => setCanRefer(e.target.value === "yes")}>
              <option value="no">No</option>
              <option value="yes">Yes</option>
            </Select>
          )}
        </Field>
        <Field label="Cadence · days" hint="Empty means they never go cold and Enola will never nudge you about them.">
          {(id) => <Input id={id} type="number" min={1} max={365} mono value={cadence} onChange={(e) => setCadence(e.target.value)} />}
        </Field>
        {error && <Mono tone="danger">{error}</Mono>}
      </form>
    </Sheet>
  );
}
