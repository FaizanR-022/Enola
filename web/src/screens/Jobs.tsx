import { useMemo, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useApplications, useJobMutations, usePostings, type Application, type Posting } from "@/data";
import { errorMessage } from "@/lib/api";
import { cx } from "@/lib/cx";
import { ApplicationStage } from "@/lib/enums.generated";
import { dueLabel, dueTone } from "@/lib/format";
import { useFinishBoot, useHeaderMeta, useShell } from "@/shell/ShellState";
import { Badge, Button, Card, Dot, EmptyState, Field, Input, Mono, QueryState, ScreenHeader, Sheet } from "@/ui";
import { Screen } from "./Screen";
import styles from "./Jobs.module.css";

const COLUMNS: ReadonlyArray<{ stage: Application["stage"]; label: string; dot: "muted" | "soft" | "accent" | "ok" | "danger" | "held" }> = [
  { stage: ApplicationStage.SAVED, label: "Saved", dot: "muted" },
  { stage: ApplicationStage.APPLIED, label: "Applied", dot: "soft" },
  { stage: ApplicationStage.SCREENING, label: "Screening", dot: "accent" },
  { stage: ApplicationStage.INTERVIEW, label: "Interview", dot: "ok" },
  { stage: ApplicationStage.OFFER, label: "Offer", dot: "held" },
  { stage: ApplicationStage.CLOSED, label: "Closed", dot: "danger" },
];

function nextLine(app: Application): { text: string; tone: "accent" | "held" | "danger" | "muted" | "ok" } {
  if (app.stage === "closed") return { text: app.closed_reason || "Closed", tone: "muted" };
  if (app.next_action) {
    const tone = app.next_action_at ? (dueTone(app.next_action_at) === "danger" ? "danger" : dueTone(app.next_action_at) === "held" ? "held" : "accent") : "accent";
    return { text: `${app.next_action}${app.next_action_at ? ` · ${dueLabel(app.next_action_at)}` : ""}`, tone };
  }
  if (app.days_quiet !== null && app.days_quiet !== undefined && app.days_quiet >= 5) return { text: `No reply · ${app.days_quiet} days`, tone: "muted" };
  return { text: app.applied_at ? `Applied ${dueLabel(app.applied_at)}` : "Not applied yet", tone: "muted" };
}

function JobCard({ app }: { app: Application }) {
  const navigate = useNavigate();
  const next = nextLine(app);
  return (
    <button type="button" className={styles["card"]} onClick={() => navigate(`/jobs/${app.id}`)}>
      <span className={styles["cardRole"]}>{app.role_title}</span>
      <span className={styles["cardCompany"]}>{app.company_name}</span>
      <span className={styles["cardTags"]}>
        {app.location_label && <Badge>{app.location_label}</Badge>}
        {app.referral_person_name && <Badge tone="accent">ref · {app.referral_person_name.split(" ")[0]}</Badge>}
      </span>
      <Mono size={11} tone={next.tone === "accent" ? "accent" : next.tone === "held" ? "held" : next.tone === "danger" ? "danger" : next.tone === "ok" ? "ok" : "muted"} className={styles["cardNext"]}>
        {next.text}
      </Mono>
    </button>
  );
}

function scoreTone(score: number | null | undefined): "ok" | "accent" | "soft" {
  if (score === null || score === undefined) return "soft";
  return score > 80 ? "ok" : score > 70 ? "accent" : "soft";
}

function DiscoveryRow({ posting }: { posting: Posting }) {
  const mutations = useJobMutations();
  const { say } = useShell();
  const navigate = useNavigate();
  const pull = () =>
    mutations.pullPosting.mutate(posting.id, {
      onSuccess: (app) => {
        say(`Added to pipeline as saved · ${app.company_name}`);
        navigate(`/jobs/${app.id}`);
      },
      onError: (e) => say(errorMessage(e)),
    });
  const dismiss = () => mutations.updatePosting.mutate({ id: posting.id, body: { status: "dismissed" } }, { onSuccess: () => say("Dismissed · Enola will stop surfacing this shape of role") });
  return (
    <div className={styles["discovery"]}>
      <div className={styles["score"]}>
        <Mono size={12} bold tone={scoreTone(posting.match_score)} className={styles["scoreValue"]}>
          {posting.match_score ?? "—"}
        </Mono>
        <Mono upper>match</Mono>
      </div>
      <div className={styles["discoveryMain"]}>
        <span className={styles["discoveryRole"]}>{posting.role_title}</span>
        <span className={styles["discoveryMeta"]}>
          {posting.company_name}
          {posting.location_label ? ` · ${posting.location_label}` : ""}
          {posting.pay_label ? ` · ${posting.pay_label}` : ""}
        </span>
        {posting.match_reason && <span className={styles["discoveryReason"]}>{posting.match_reason}</span>}
      </div>
      <div className={styles["discoveryActions"]}>
        <Button size="sm" onClick={pull} busy={mutations.pullPosting.isPending}>
          Pull in
        </Button>
        <Button size="sm" variant="danger" onClick={dismiss} busy={mutations.updatePosting.isPending}>
          Dismiss
        </Button>
      </div>
    </div>
  );
}

export function Jobs() {
  const applications = useApplications();
  const postings = usePostings("discovered");
  const mutations = useJobMutations();
  const { say } = useShell();
  const navigate = useNavigate();
  const [adding, setAdding] = useState(false);
  const [phoneStage, setPhoneStage] = useState<Application["stage"]>(ApplicationStage.SCREENING);
  useFinishBoot();

  const byStage = useMemo(() => {
    const map = new Map<Application["stage"], Application[]>();
    for (const c of COLUMNS) map.set(c.stage, []);
    for (const app of applications.data?.items ?? []) map.get(app.stage)?.push(app);
    return map;
  }, [applications.data]);
  const total = applications.data?.total ?? 0;
  const live = (applications.data?.items ?? []).filter((a) => a.stage === "screening" || a.stage === "interview").length;
  useHeaderMeta(applications.data ? `${total} applications` : null);

  return (
    <Screen>
      <ScreenHeader title="Jobs" subtitle={`${total} applications · ${live} live conversations`} />

      <form
        className={styles["paste"]}
        onSubmit={(e) => {
          e.preventDefault();
          setAdding(true);
        }}
      >
        <Mono upper>Add a posting</Mono>
        <span className={styles["pasteHint"]}>Company and role go straight into Saved. Paste the URL and Enola keeps it with the application.</span>
        <Button size="sm" variant="primary" type="submit">
          Add
        </Button>
      </form>

      <QueryState status={applications.status} error={applications.error} data={applications.data} onRetry={() => void applications.refetch()} rows={5}>
        {() => (
          <>
            <div className={styles["phoneStages"]}>
              {COLUMNS.map((c) => (
                <button key={c.stage} type="button" className={cx(styles["stageChip"], phoneStage === c.stage && styles["stageChipOn"])} onClick={() => setPhoneStage(c.stage)}>
                  {c.label} <Mono>{byStage.get(c.stage)?.length ?? 0}</Mono>
                </button>
              ))}
            </div>
            <div className={styles["board"]}>
              {COLUMNS.map((c) => {
                const items = byStage.get(c.stage) ?? [];
                return (
                  <div key={c.stage} className={cx(styles["column"], phoneStage !== c.stage && styles["columnHidden"])}>
                    <div className={styles["columnHead"]}>
                      <Dot tone={c.dot} />
                      <Mono upper tone="soft">
                        {c.label}
                      </Mono>
                      <Mono className={styles["columnCount"]}>{items.length}</Mono>
                    </div>
                    {items.map((app) => (
                      <JobCard key={app.id} app={app} />
                    ))}
                    {items.length === 0 && <div className={styles["columnEmpty"]}>—</div>}
                  </div>
                );
              })}
            </div>
          </>
        )}
      </QueryState>

      <section className={styles["discoverySection"]}>
        <div className={styles["discoveryHead"]}>
          <span className={styles["discoveryTitle"]}>Discovery</span>
          <span className={styles["discoverySub"]}>Found overnight. Match score is against your saved postings and skill gaps, not a job board's.</span>
        </div>
        <QueryState status={postings.status} error={postings.error} data={postings.data} rows={3}>
          {(page) =>
            page.items.length === 0 ? (
              <EmptyState title="Nothing new in discovery." hint="Postings Enola finds, or ones you add without pulling them in, wait here." />
            ) : (
              <Card flush>
                {page.items.map((posting) => (
                  <DiscoveryRow key={posting.id} posting={posting} />
                ))}
              </Card>
            )
          }
        </QueryState>
      </section>

      <AddPostingSheet
        open={adding}
        onClose={() => setAdding(false)}
        busy={mutations.createPosting.isPending || mutations.pullPosting.isPending}
        onSubmit={(body) =>
          mutations.createPosting.mutate(body, {
            onSuccess: (posting) =>
              mutations.pullPosting.mutate(posting.id, {
                onSuccess: (app) => {
                  setAdding(false);
                  say(`Saved · ${app.company_name} · ${app.role_title}`);
                  navigate(`/jobs/${app.id}`);
                },
              }),
            onError: (e) => say(errorMessage(e)),
          })
        }
      />
    </Screen>
  );
}

function AddPostingSheet({ open, onClose, onSubmit, busy }: { open: boolean; onClose: () => void; onSubmit: (body: { company_name: string; role_title: string; url: string; location_label: string; pay_label: string; status: "saved" }) => void; busy: boolean }) {
  const [company, setCompany] = useState("");
  const [role, setRole] = useState("");
  const [url, setUrl] = useState("");
  const [location, setLocation] = useState("");
  const [pay, setPay] = useState("");
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!company.trim() || !role.trim()) return;
    onSubmit({ company_name: company.trim(), role_title: role.trim(), url: url.trim(), location_label: location.trim(), pay_label: pay.trim(), status: "saved" });
  };
  return (
    <Sheet
      open={open}
      onClose={onClose}
      title="Add a posting"
      footer={
        <>
          <Button variant="primary" type="submit" form="add-posting" busy={busy} disabled={!company.trim() || !role.trim()}>
            Save to pipeline
          </Button>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
        </>
      }
    >
      <form id="add-posting" onSubmit={submit} className={styles["form"]}>
        <Field label="Company">{(id) => <Input id={id} value={company} onChange={(e) => setCompany(e.target.value)} autoFocus />}</Field>
        <Field label="Role">{(id) => <Input id={id} value={role} onChange={(e) => setRole(e.target.value)} placeholder="Backend Engineer (Python)" />}</Field>
        <Field label="URL">{(id) => <Input id={id} value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://…" mono />}</Field>
        <div className={styles["formRow"]}>
          <Field label="Location">{(id) => <Input id={id} value={location} onChange={(e) => setLocation(e.target.value)} placeholder="Remote · global" />}</Field>
          <Field label="Pay">{(id) => <Input id={id} value={pay} onChange={(e) => setPay(e.target.value)} placeholder="$52–68k" />}</Field>
        </div>
      </form>
    </Sheet>
  );
}
