import { useMemo, useState, type FormEvent } from "react";
import { useMemory, useMemoryMutations, type MemoryFact } from "@/data";
import { cx } from "@/lib/cx";
import { useFinishBoot, useHeaderMeta, useShell } from "@/shell/ShellState";
import { Button, EmptyState, Field, Input, Mono, QueryState, ScreenHeader, Sheet } from "@/ui";
import { Screen } from "./Screen";
import styles from "./Memory.module.css";

function confidenceTone(fact: MemoryFact): "accent" | "soft" | "low" {
  return fact.confidence > 80 ? "accent" : fact.confidence > 60 ? "soft" : "low";
}

function FactRow({ fact }: { fact: MemoryFact }) {
  const mutations = useMemoryMutations();
  const { say } = useShell();
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(fact.statement);
  const forgotten = fact.state === "forgotten";

  const save = (event: FormEvent) => {
    event.preventDefault();
    if (!text.trim() || text.trim() === fact.statement) {
      setEditing(false);
      return;
    }
    mutations.update.mutate(
      { id: fact.id, body: { statement: text.trim() } },
      {
        onSuccess: () => {
          setEditing(false);
          say("Correction saved · Enola will use the new statement from now on");
        },
      },
    );
  };

  return (
    <div className={cx(styles["fact"], forgotten && styles["forgotten"])}>
      <div className={styles["factMain"]}>
        {editing ? (
          <form onSubmit={save} className={styles["editRow"]}>
            <Input value={text} onChange={(e) => setText(e.target.value)} autoFocus aria-label="Corrected statement" />
            <Button size="sm" variant="primary" type="submit" busy={mutations.update.isPending}>
              Save
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>
              Cancel
            </Button>
          </form>
        ) : (
          <span className={styles["statement"]}>{fact.statement}</span>
        )}
        <Mono>
          {fact.source === "rule" ? "standing rule · locked" : fact.source === "told" ? "you told me" : "inferred"}
          {fact.evidence ? ` · ${fact.evidence.replace(/^(you told me|inferred|standing rule)\s*·?\s*/i, "")}` : ""}
          {fact.corrected_at ? " · corrected" : ""}
        </Mono>
      </div>
      <div className={styles["confidence"]}>
        <span className={styles["bar"]}>
          <span className={cx(styles["fill"], styles[`fill-${confidenceTone(fact)}`])} style={{ ["--conf" as string]: `${fact.confidence}%` }} />
        </span>
        <Mono className={styles["pct"]}>{fact.confidence}%</Mono>
      </div>
      <div className={styles["actions"]}>
        {!fact.locked && !forgotten && (
          <Button variant="link" onClick={() => setEditing((v) => !v)}>
            Correct
          </Button>
        )}
        {fact.locked ? (
          <Mono>locked</Mono>
        ) : forgotten ? (
          <Button variant="link" onClick={() => mutations.restore.mutate(fact.id)}>
            Restore
          </Button>
        ) : (
          <button type="button" className={styles["forget"]} onClick={() => mutations.forget.mutate(fact.id, { onSuccess: () => say("Forgotten · Enola will not use it again") })}>
            Forget
          </button>
        )}
      </div>
    </div>
  );
}

export function Memory() {
  const memory = useMemory();
  const mutations = useMemoryMutations();
  const { say } = useShell();
  const [adding, setAdding] = useState(false);
  useFinishBoot();
  useHeaderMeta("what Enola believes");

  const groups = useMemo(() => {
    const active = new Map<string, MemoryFact[]>();
    const forgotten: MemoryFact[] = [];
    for (const fact of memory.data?.items ?? []) {
      if (fact.state === "forgotten") forgotten.push(fact);
      else active.set(fact.group, [...(active.get(fact.group) ?? []), fact]);
    }
    const out = [...active.entries()].map(([label, items]) => ({ label, items }));
    if (forgotten.length) out.push({ label: "Corrected by you", items: forgotten });
    return out;
  }, [memory.data]);

  return (
    <Screen narrow>
      <ScreenHeader
        title="Memory"
        subtitle="Everything Enola believes about you, with where it came from."
        actions={
          <Button size="sm" onClick={() => setAdding(true)}>
            Tell Enola something
          </Button>
        }
      />
      <QueryState status={memory.status} error={memory.error} data={memory.data} onRetry={() => void memory.refetch()} rows={6}>
        {(page) =>
          page.items.length === 0 ? (
            <EmptyState title="Enola believes nothing yet." hint="Facts arrive from conversation, or you can state one directly." action={<Button size="sm" onClick={() => setAdding(true)}>Tell Enola something</Button>} />
          ) : (
            groups.map((group) => (
              <section key={group.label} className={styles["group"]}>
                <Mono upper className={styles["groupLabel"]}>
                  {group.label}
                </Mono>
                <div className={styles["facts"]}>
                  {group.items.map((fact) => (
                    <FactRow key={fact.id} fact={fact} />
                  ))}
                </div>
              </section>
            ))
          )
        }
      </QueryState>
      <div className={styles["footnote"]}>Corrections are immediate: the next run reads the corrected statement. Forgotten beliefs stay visible, struck through, so you can see what changed. Low-confidence beliefs are never acted on without asking.</div>
      <AddFactSheet
        open={adding}
        onClose={() => setAdding(false)}
        busy={mutations.create.isPending}
        onSubmit={(statement, group) =>
          mutations.create.mutate(
            { statement, group, source: "told", evidence: "you told me", confidence: 100, locked: false },
            {
              onSuccess: () => {
                setAdding(false);
                say("Remembered");
              },
            },
          )
        }
      />
    </Screen>
  );
}

function AddFactSheet({ open, onClose, onSubmit, busy }: { open: boolean; onClose: () => void; onSubmit: (statement: string, group: string) => void; busy: boolean }) {
  const [statement, setStatement] = useState("");
  const [group, setGroup] = useState("About you");
  return (
    <Sheet
      open={open}
      onClose={onClose}
      title="Tell Enola something"
      footer={
        <>
          <Button variant="primary" type="submit" form="add-fact" busy={busy} disabled={!statement.trim()}>
            Remember
          </Button>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
        </>
      }
    >
      <form
        id="add-fact"
        className={styles["form"]}
        onSubmit={(e) => {
          e.preventDefault();
          if (statement.trim()) onSubmit(statement.trim(), group.trim() || "About you");
        }}
      >
        <Field label="Statement" hint="Present tense, about you. “I don’t need visa sponsorship for remote roles.”">
          {(id) => <Input id={id} value={statement} onChange={(e) => setStatement(e.target.value)} autoFocus />}
        </Field>
        <Field label="Group">{(id) => <Input id={id} value={group} onChange={(e) => setGroup(e.target.value)} placeholder="About the job hunt" />}</Field>
      </form>
    </Sheet>
  );
}
