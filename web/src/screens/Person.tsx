import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { usePeopleMutations, usePerson, usePersonInteractions, usePersonMoney, useTaskMutations, useTasks, type Person as PersonType } from "@/data";
import { InteractionKind } from "@/lib/enums.generated";
import { agoLabel, dateLabel, signedPkr } from "@/lib/format";
import { useFinishBoot, useHeaderMeta, useShell } from "@/shell/ShellState";
import { Avatar, Badge, Button, Card, CardRow, EmptyState, Input, Mono, QueryState, Select, TextArea } from "@/ui";
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

  const lastTone = person.going_cold ? "held" : "neutral";

  return (
    <>
      <div className={styles["header"]}>
        <Avatar name={person.name} size="lg" />
        <div className={styles["identity"]}>
          <h1 className={styles["name"]}>{person.name}</h1>
          <div className={styles["role"]}>{person.role || "No role recorded"}</div>
        </div>
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
                  <Mono size={12} tone={row.settled_at ? "muted" : row.amount > 0 ? "ok" : "danger"}>
                    {row.settled_at ? "settled" : signedPkr(row.amount)}
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
    </>
  );
}
