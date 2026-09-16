import { useMemo, useState, type FormEvent } from "react";
import { useLogCandidates, useLogEntries, useLogMutations, type LogEntry } from "@/data";
import { cx } from "@/lib/cx";
import { dayHeading, parseDate, timeLabel } from "@/lib/format";
import { useFinishBoot, useHeaderMeta, useShell } from "@/shell/ShellState";
import { Badge, Button, Card, CardRow, EmptyState, Input, Mono, QueryState, ScreenHeader, TextArea } from "@/ui";
import { Grid, Screen, Stack } from "./Screen";
import styles from "./Log.module.css";

const DEFAULT_TAGS = ["#code", "#study", "#jobs", "#fyp", "#admin", "#read"];

function groupByDay(entries: LogEntry[]): Array<{ day: string; items: LogEntry[] }> {
  const groups = new Map<string, LogEntry[]>();
  for (const entry of entries) {
    const key = (parseDate(entry.occurred_at) ?? new Date()).toDateString();
    const list = groups.get(key) ?? [];
    list.push(entry);
    groups.set(key, list);
  }
  return [...groups.entries()].map(([, items]) => ({ day: items[0]?.occurred_at ?? "", items }));
}

function weekBars(entries: LogEntry[]): Array<{ label: string; count: number; today: boolean }> {
  const now = new Date();
  const monday = new Date(now);
  monday.setHours(0, 0, 0, 0);
  monday.setDate(now.getDate() - ((now.getDay() + 6) % 7));
  return Array.from({ length: 7 }, (_, i) => {
    const day = new Date(monday);
    day.setDate(monday.getDate() + i);
    const count = entries.filter((e) => (parseDate(e.occurred_at) ?? new Date(0)).toDateString() === day.toDateString()).length;
    return { label: day.toLocaleDateString(undefined, { weekday: "narrow" }), count, today: day.toDateString() === now.toDateString() };
  });
}

export function Log() {
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [newTags, setNewTags] = useState<string[]>([]);
  const [search, setSearch] = useState("");
  const [filterTag, setFilterTag] = useState<string | null>(null);
  const { say } = useShell();
  const all = useLogEntries({});
  const entries = useLogEntries({ ...(filterTag ? { tag: filterTag } : {}), ...(search.trim() ? { q: search.trim() } : {}) });
  const candidates = useLogCandidates();
  const mutations = useLogMutations();
  const [taken, setTaken] = useState<Set<string>>(new Set());
  useFinishBoot();
  useHeaderMeta(all.data ? `${all.data.total} ${all.data.total === 1 ? "entry" : "entries"}` : null);

  const tags = useMemo(() => {
    const seen = new Set(DEFAULT_TAGS);
    for (const e of all.data?.items ?? []) for (const t of e.tags) seen.add(t);
    return [...seen];
  }, [all.data]);

  const add = (event: FormEvent) => {
    event.preventDefault();
    const t = title.trim();
    const b = body.trim();
    if (!t && !b) return;
    mutations.create.mutate(
      { title: t || b.split(". ")[0] || b, body: t ? b : "", tags: newTags, occurred_at: new Date().toISOString(), source: "you", source_label: "you" },
      {
        onSuccess: () => {
          setTitle("");
          setBody("");
          setNewTags([]);
          say(`Logged · ${timeLabel(new Date().toISOString())}${newTags.length ? ` · ${newTags.join(" ")}` : ""}`);
        },
      },
    );
  };

  const accept = (key: string, text: string, tagsFor: string[], occurredAt: string, sourceLabel: string) => {
    mutations.create.mutate(
      { title: text, body: "", tags: tagsFor, occurred_at: occurredAt, source: "enola", source_label: sourceLabel },
      { onSuccess: () => setTaken((s) => new Set(s).add(key)) },
    );
  };

  const toggleTag = (tag: string) => setNewTags((current) => (current.includes(tag) ? current.filter((t) => t !== tag) : [...current, tag]));

  return (
    <Screen narrow>
      <ScreenHeader title="Log" subtitle="What actually happened today. Tasks are what you meant to do; this is the record." />

      <form className={styles["composer"]} onSubmit={add}>
        <Input bare value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Title — “Raft election finally stable”" className={styles["composerTitle"]} aria-label="Entry title" />
        <TextArea bare value={body} onChange={(e) => setBody(e.target.value)} placeholder="What happened, in as many words as it deserves. Empty is fine; a title alone is a valid entry." className={styles["composerBody"]} rows={2} aria-label="Entry body" />
        <div className={styles["composerFoot"]}>
          <Mono upper>Tags</Mono>
          <div className={styles["tagRow"]}>
            {tags.map((tag) => (
              <button key={tag} type="button" className={cx(styles["tag"], newTags.includes(tag) && styles["tagOn"])} onClick={() => toggleTag(tag)} aria-pressed={newTags.includes(tag)}>
                {tag}
              </button>
            ))}
          </div>
          <Button size="sm" variant="primary" type="submit" busy={mutations.create.isPending} disabled={!title.trim() && !body.trim()}>
            Add entry
          </Button>
        </div>
      </form>

      <Grid min="300px">
        <Card flush note="Your entries carry a cyan source tag, accepted suggestions a grey one. Enola never writes here on its own.">
          <div className={styles["searchRow"]}>
            <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search the log — text or #tag" aria-label="Search log" />
            <Mono>{entries.data && all.data ? (entries.data.total === all.data.total ? `${all.data.total} entries` : `${entries.data.total} of ${all.data.total}`) : ""}</Mono>
          </div>
          <div className={styles["filterRow"]}>
            {[null, ...tags].map((tag) => (
              <button key={tag ?? "all"} type="button" className={cx(styles["tag"], filterTag === tag && styles["tagOn"])} onClick={() => setFilterTag(tag)} aria-pressed={filterTag === tag}>
                {tag ?? "all"}
              </button>
            ))}
          </div>
          <QueryState status={entries.status} error={entries.error} data={entries.data} onRetry={() => void entries.refetch()} rows={5}>
            {(page) =>
              page.items.length === 0 ? (
                <EmptyState inline title="Nothing matches." hint="Tags come from what you have used before. Enola does not invent new ones." />
              ) : (
                groupByDay(page.items).map((group) => (
                  <div key={group.day}>
                    <div className={styles["dayHead"]}>
                      <Mono upper>{dayHeading(group.day)}</Mono>
                    </div>
                    {group.items.map((entry) => (
                      <CardRow key={entry.id} align="start">
                        <Mono className={styles["time"]}>{timeLabel(entry.occurred_at)}</Mono>
                        <span className={styles["entryMain"]}>
                          <span className={styles["entryTitle"]}>{entry.title}</span>
                          {entry.body && <span className={styles["entryBody"]}>{entry.body}</span>}
                          <span className={styles["entryTags"]}>
                            <Badge tone={entry.source === "you" ? "accent" : "neutral"}>{entry.source_label}</Badge>
                            {entry.tags.map((t) => (
                              <Badge key={t} tone="soft">
                                {t}
                              </Badge>
                            ))}
                          </span>
                        </span>
                        <button type="button" className={styles["remove"]} onClick={() => mutations.remove.mutate(entry.id)} aria-label="Delete entry">
                          ✕
                        </button>
                      </CardRow>
                    ))}
                  </div>
                ))
              )
            }
          </QueryState>
        </Card>

        <Stack>
          <Card title="Enola noticed" flush note="Drawn from finished tasks and approved actions. Suggestions only; the log is yours to write.">
            <QueryState status={candidates.status} error={candidates.error} data={candidates.data} rows={3}>
              {(rows) =>
                rows.length === 0 ? (
                  <EmptyState inline title="Nothing noticed in the last day." />
                ) : (
                  rows.map((c) => (
                    <CardRow key={c.key} muted={taken.has(c.key)}>
                      <span className={styles["candMain"]}>
                        <span className={styles["candText"]}>{c.text}</span>
                        <Mono>
                          {c.source_label} · {timeLabel(c.occurred_at)}
                        </Mono>
                      </span>
                      <Button size="sm" onClick={() => accept(c.key, c.text, c.tags, c.occurred_at, c.source_label)} disabled={taken.has(c.key)}>
                        {taken.has(c.key) ? "Added" : "Add"}
                      </Button>
                    </CardRow>
                  ))
                )
              }
            </QueryState>
          </Card>
          <Card title="This week" meta={<Mono>Mon–Sun</Mono>}>
            <div className={styles["bars"]}>
              {weekBars(all.data?.items ?? []).map((bar, i) => (
                <div key={i} className={styles["bar"]}>
                  <div className={cx(styles["barFill"], bar.today && styles["barToday"], bar.count === 0 && styles["barEmpty"])} style={{ ["--bar-h" as string]: `${Math.max(3, bar.count * 12)}px` }} />
                  <Mono tone={bar.today ? "text" : "muted"}>{bar.label}</Mono>
                </div>
              ))}
            </div>
            <div className={styles["weekNote"]}>{weekNote(weekBars(all.data?.items ?? []))}</div>
          </Card>
        </Stack>
      </Grid>
    </Screen>
  );
}

function weekNote(bars: Array<{ count: number; today: boolean }>): string {
  const past = bars.filter((_, i) => i <= bars.findIndex((x) => x.today));
  const blank = past.filter((b) => b.count === 0).length;
  if (blank === 0) return "Something logged every day so far this week.";
  return `${blank === 1 ? "One day" : `${blank} days`} with nothing logged. Enola does not fill them in; a blank day is information too.`;
}
