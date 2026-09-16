import { useMemo, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { usePeople, usePeopleMutations } from "@/data";
import { cx } from "@/lib/cx";
import { useFinishBoot, useHeaderMeta, useShell } from "@/shell/ShellState";
import { Button, Card, EmptyState, Field, Input, QueryState, ScreenHeader, Sheet } from "@/ui";
import { Screen } from "./Screen";
import { PersonRow } from "./shared/PersonRow";
import styles from "./People.module.css";

type Filter = { kind: "all" } | { kind: "tag"; tag: string } | { kind: "cold" } | { kind: "refer" };

export function People() {
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState<Filter>({ kind: "all" });
  const [adding, setAdding] = useState(false);
  const navigate = useNavigate();
  const { say } = useShell();
  const all = usePeople({});
  const params = {
    ...(q.trim() ? { q: q.trim() } : {}),
    ...(filter.kind === "tag" ? { tag: filter.tag } : {}),
    ...(filter.kind === "cold" ? { going_cold: true } : {}),
    ...(filter.kind === "refer" ? { can_refer: true } : {}),
  };
  const people = usePeople(params);
  const mutations = usePeopleMutations();
  useFinishBoot();
  useHeaderMeta(all.data ? `${all.data.total} contacts` : null);

  const chips = useMemo(() => {
    const items = all.data?.items ?? [];
    const counts = new Map<string, number>();
    for (const p of items) for (const t of p.tags) counts.set(t, (counts.get(t) ?? 0) + 1);
    const top = [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 6);
    return {
      total: items.length,
      cold: items.filter((p) => p.going_cold).length,
      refer: items.filter((p) => p.can_refer).length,
      tags: top,
    };
  }, [all.data]);

  const isOn = (f: Filter) => JSON.stringify(f) === JSON.stringify(filter);

  return (
    <Screen>
      <ScreenHeader
        title="People"
        subtitle={`${chips.total} contacts. Search by what you need, not by name.`}
        actions={
          <Button onClick={() => setAdding(true)} size="sm">
            Add person
          </Button>
        }
      />
      <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="who do I know that could advise me on distributed systems?" aria-label="Search people" />
      <div className={styles["chips"]}>
        <Chip on={isOn({ kind: "all" })} onClick={() => setFilter({ kind: "all" })}>
          all {chips.total}
        </Chip>
        {chips.tags.map(([tag, n]) => (
          <Chip key={tag} on={isOn({ kind: "tag", tag })} onClick={() => setFilter({ kind: "tag", tag })}>
            {tag} {n}
          </Chip>
        ))}
        <Chip on={isOn({ kind: "cold" })} onClick={() => setFilter({ kind: "cold" })}>
          going cold {chips.cold}
        </Chip>
        <Chip on={isOn({ kind: "refer" })} onClick={() => setFilter({ kind: "refer" })}>
          can refer {chips.refer}
        </Chip>
      </div>
      <QueryState status={people.status} error={people.error} data={people.data} onRetry={() => void people.refetch()} rows={7}>
        {(page) =>
          page.items.length === 0 ? (
            <EmptyState title={q ? "Nobody matches that." : "No contacts yet."} hint="Search matches names, roles, notes and how you met." action={<Button size="sm" onClick={() => setAdding(true)}>Add person</Button>} />
          ) : (
            <Card flush>
              {page.items.map((person) => (
                <PersonRow key={person.id} person={person} />
              ))}
            </Card>
          )
        }
      </QueryState>
      <AddPersonSheet
        open={adding}
        onClose={() => setAdding(false)}
        busy={mutations.create.isPending}
        onSubmit={(body) =>
          mutations.create.mutate(body, {
            onSuccess: (person) => {
              setAdding(false);
              say(`Added ${person.name}`);
              navigate(`/people/${person.id}`);
            },
          })
        }
      />
    </Screen>
  );
}

function Chip({ on, onClick, children }: { on: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button type="button" className={cx(styles["chip"], on && styles["chipOn"])} onClick={onClick} aria-pressed={on}>
      {children}
    </button>
  );
}

function AddPersonSheet({ open, onClose, onSubmit, busy }: { open: boolean; onClose: () => void; onSubmit: (body: { name: string; role: string; tags: string[]; cadence_days: number | null; how_we_met: string }) => void; busy: boolean }) {
  const [name, setName] = useState("");
  const [role, setRole] = useState("");
  const [tags, setTags] = useState("");
  const [met, setMet] = useState("");
  const [cadence, setCadence] = useState("");
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!name.trim()) return;
    onSubmit({
      name: name.trim(),
      role: role.trim(),
      tags: tags.split(",").map((t) => t.trim()).filter(Boolean),
      cadence_days: cadence ? Number(cadence) : null,
      how_we_met: met.trim(),
    });
  };
  return (
    <Sheet
      open={open}
      onClose={onClose}
      title="Add a person"
      footer={
        <>
          <Button variant="primary" type="submit" form="add-person" busy={busy} disabled={!name.trim()}>
            Save
          </Button>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
        </>
      }
    >
      <form id="add-person" onSubmit={submit} className={styles["form"]}>
        <Field label="Name">{(id) => <Input id={id} value={name} onChange={(e) => setName(e.target.value)} autoFocus />}</Field>
        <Field label="Role">{(id) => <Input id={id} value={role} onChange={(e) => setRole(e.target.value)} placeholder="Technical recruiter · Kestrel Labs" />}</Field>
        <Field label="Tags" hint="Comma-separated. Reuse what you already have.">
          {(id) => <Input id={id} value={tags} onChange={(e) => setTags(e.target.value)} placeholder="recruiter, kestrel, can refer" />}
        </Field>
        <Field label="How you met">{(id) => <Input id={id} value={met} onChange={(e) => setMet(e.target.value)} />}</Field>
        <Field label="Cadence · days" hint="Leave empty for no reminder. Otherwise Enola flags them when it lapses.">
          {(id) => <Input id={id} type="number" min={1} max={365} value={cadence} onChange={(e) => setCadence(e.target.value)} mono />}
        </Field>
      </form>
    </Sheet>
  );
}
