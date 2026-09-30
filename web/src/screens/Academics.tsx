/** Academics. Courses, their materials and deadlines, the FYP, and a chat scoped to
 *  one course's documents. The only screen that uses the warm `paper` mode. */

import { useRef, useState, type FormEvent } from "react";
import {
  courseScope,
  useAcademicsMutations,
  useAssessments,
  useChatHistory,
  useCourses,
  useDocumentMutations,
  useDocuments,
  useFypMilestones,
  useSendChat,
  type Course,
} from "@/data";
import { cx } from "@/lib/cx";
import { errorMessage } from "@/lib/api";
import { useFinishBoot, useHeaderMeta, useShell } from "@/shell/ShellState";
import { Badge, Button, Card, CardRow, Dot, EmptyState, Field, Input, Mono, QueryState, ScreenHeader, Select, Sheet, TextArea } from "@/ui";
import { Grid, Screen, Stack } from "./Screen";
import { UrgencyDot, urgencyMono } from "./shared/UrgencyDot";
import { urgencyOf } from "./shared/urgency";
import styles from "./Academics.module.css";

type Tab = "courses" | "fyp" | "prep";

const KINDS = ["assignment", "quiz", "exam", "lab", "project", "report"] as const;

/** A datetime-local value for an <input>, defaulting to a sensible near-future slot. */
function localInput(date: Date): string {
  const offset = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
}

const DATE = { day: "numeric", month: "short" } as const;

function extOf(filename: string): string {
  const dot = filename.lastIndexOf(".");
  return dot > 0 ? filename.slice(dot + 1).toUpperCase().slice(0, 4) : "FILE";
}

function dueLabel(due: string | null): string {
  if (!due) return "—";
  return new Date(due).toLocaleString(undefined, { ...DATE, hour: "2-digit", minute: "2-digit" });
}

/** Deadlines, materials and the scoped chat for one course. */
function CourseDetail({ course, onBack }: { course: Course; onBack: () => void }) {
  const scope = courseScope(course.id);
  const assessments = useAssessments(course.id);
  const documents = useDocuments(scope);
  const docs = useDocumentMutations();
  const history = useChatHistory(scope);
  const send = useSendChat(scope);
  const { say } = useShell();
  const fileInput = useRef<HTMLInputElement>(null);
  const [draft, setDraft] = useState("");
  const [addingDeadline, setAddingDeadline] = useState(false);

  const ask = (event: FormEvent) => {
    event.preventDefault();
    const text = draft.trim();
    if (!text || send.isPending) return;
    setDraft("");
    send.mutate({ text, scope, source: "text" });
  };

  const pick = (file: File | undefined) => {
    if (!file) return;
    docs.upload.mutate(
      { file, entityId: course.id },
      {
        onSuccess: () => say(`Added ${file.name} to ${course.code}`),
        onError: (error) => say(errorMessage(error)),
      },
    );
  };

  return (
    <Stack>
      <Button variant="link" onClick={onBack}>
        ← All courses
      </Button>
      <div>
        <Mono size={10}>{course.code}</Mono>
        <h2 className={styles["courseTitle"]}>{course.name}</h2>
        <div className={styles["courseSub"]}>{[course.instructor, course.room, course.schedule].filter(Boolean).join(" · ") || "No schedule recorded"}</div>
      </div>

      <div className={styles["detail"]}>
        <Stack>
          <Card
            title="Deadlines"
            flush
            note="Assignments, quizzes and exams. Each one also becomes a task, so it shows up in your daily brief."
            meta={
              <Button variant="link" onClick={() => setAddingDeadline(true)}>
                Add
              </Button>
            }
          >
            <QueryState status={assessments.status} error={assessments.error} data={assessments.data} onRetry={() => void assessments.refetch()} rows={3}>
              {(page) =>
                page.items.length === 0 ? (
                  <EmptyState inline title="No deadlines yet" hint="Add one from the syllabus, or ask Enola in the chat beside this." />
                ) : (
                  <>
                    {page.items.map((a) => {
                      const tier = urgencyOf(a.due_at);
                      return (
                        <CardRow key={a.id} className={cx(tier === "overdue" && styles["overdueRow"])}>
                          <UrgencyDot urgency={tier} />
                          <Mono upper className={styles["kind"]}>
                            {a.kind}
                          </Mono>
                          <span className={styles["deadlineTitle"]}>{a.title}</span>
                          <Mono size={11} tone={urgencyMono(tier)}>
                            {dueLabel(a.due_at)}
                          </Mono>
                        </CardRow>
                      );
                    })}
                  </>
                )
              }
            </QueryState>
          </Card>

          <Card
            title="Materials"
            meta={
              <Button variant="link" onClick={() => fileInput.current?.click()} disabled={docs.upload.isPending}>
                {docs.upload.isPending ? "Uploading…" : "Upload"}
              </Button>
            }
          >
            <input
              ref={fileInput}
              type="file"
              hidden
              onChange={(e) => {
                pick(e.target.files?.[0]);
                e.target.value = "";
              }}
            />
            <QueryState status={documents.status} error={documents.error} data={documents.data} onRetry={() => void documents.refetch()} rows={2}>
              {(page) =>
                page.items.length === 0 ? (
                  <EmptyState inline title="Nothing uploaded" hint="Slides and PDFs added here are what the chat beside this can read." />
                ) : (
                  <div className={styles["files"]}>
                    {page.items.map((f) => (
                      <a key={f.id} href={`/api/documents/${f.id}/file`} target="_blank" rel="noreferrer" className={styles["file"]} title={f.filename}>
                        <span className={styles["fileThumb"]}>
                          <Mono className={styles["fileExt"]}>{extOf(f.filename)}</Mono>
                        </span>
                        <Mono size={10} tone="soft" className={styles["fileName"]}>
                          {f.title || f.filename}
                        </Mono>
                      </a>
                    ))}
                  </div>
                )
              }
            </QueryState>
          </Card>
        </Stack>

        <Card title="Chat" meta={<Badge tone="neutral" pill>scoped: {course.code} only</Badge>} flush className={styles["chat"]}>
          <div className={styles["chatBody"]}>
            <QueryState status={history.status} error={history.error} data={history.data} onRetry={() => void history.refetch()} rows={2}>
              {(messages) =>
                messages.length === 0 ? (
                  <EmptyState inline title="Nothing asked yet" hint={`Retrieval here only reaches ${course.code}'s materials — not your other courses, and not the rest of Enola.`} />
                ) : (
                  <>
                    {messages.map((m, i) => (
                      <div key={i} className={styles["msg"]}>
                        <Mono upper tone={m.role === "enola" ? "accent" : "muted"}>
                          {m.role}
                        </Mono>
                        <span className={styles["msgText"]}>{m.text}</span>
                      </div>
                    ))}
                  </>
                )
              }
            </QueryState>
            {send.isPending && <Mono tone="soft">thinking…</Mono>}
            {send.isError && <Mono tone="danger">{errorMessage(send.error)}</Mono>}
          </div>
          <form onSubmit={ask}>
            <input
              className={styles["chatBox"]}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder={`Ask about ${course.document_count} document${course.document_count === 1 ? "" : "s"}…`}
              aria-label={`Ask about ${course.code}`}
            />
          </form>
        </Card>
      </div>
      {addingDeadline && <AssessmentSheet course={course} onClose={() => setAddingDeadline(false)} />}
    </Stack>
  );
}

function Fyp({ course }: { course: Course | undefined }) {
  const milestones = useFypMilestones(course?.id);
  const notes = useDocuments(course ? courseScope(course.id) : undefined);

  if (!course) {
    return <EmptyState title="No FYP recorded" hint="Mark one of your courses as the final year project and its milestones will live here." />;
  }

  return (
    <Grid min="290px">
      <Stack>
        <div>
          <Mono size={10}>FYP · {course.code}</Mono>
          <h2 className={styles["fypTitle"]}>{course.fyp_title || course.name}</h2>
          {course.fyp_note && <p className={styles["fypNote"]}>{course.fyp_note}</p>}
        </div>
        <Card title="Milestones" flush>
          <QueryState status={milestones.status} error={milestones.error} data={milestones.data} onRetry={() => void milestones.refetch()} rows={3}>
            {(page) =>
              page.items.length === 0 ? (
                <EmptyState inline title="No milestones yet" />
              ) : (
                <>
                  {page.items.map((m) => (
                    <CardRow key={m.id} align="start">
                      <Dot size={9} tone={m.state === "done" ? "accent" : m.state === "current" ? "danger" : "line"} hollow={m.state !== "done"} className={styles["milestoneDot"]} />
                      <span className={styles["milestoneMain"]}>
                        <span className={cx(styles["milestoneTitle"], m.state === "upcoming" && styles["muted"])}>{m.title}</span>
                        {m.note && <span className={styles["milestoneNote"]}>{m.note}</span>}
                      </span>
                      <Mono>{m.due_at ? new Date(m.due_at).toLocaleDateString(undefined, DATE) : "—"}</Mono>
                    </CardRow>
                  ))}
                </>
              )
            }
          </QueryState>
        </Card>
      </Stack>
      <Card title="Research notes" flush note="Documents attached to the FYP.">
        <QueryState status={notes.status} error={notes.error} data={notes.data} onRetry={() => void notes.refetch()} rows={2}>
          {(page) =>
            page.items.length === 0 ? (
              <EmptyState inline title="Nothing attached" hint="Upload papers and drafts from the course view." />
            ) : (
              <>
                {page.items.map((n) => (
                  <CardRow key={n.id} align="start" className={styles["note"]}>
                    <span className={styles["noteMain"]}>
                      <span className={styles["noteTitle"]}>{n.title || n.filename}</span>
                      <Mono>{extOf(n.filename)}</Mono>
                    </span>
                  </CardRow>
                ))}
              </>
            )
          }
        </QueryState>
      </Card>
    </Grid>
  );
}


function CourseSheet({ onClose }: { onClose: () => void }) {
  const { createCourse } = useAcademicsMutations();
  const { say } = useShell();
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [instructor, setInstructor] = useState("");
  const [schedule, setSchedule] = useState("");
  const [isFyp, setIsFyp] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!code.trim() || !name.trim()) return setError("A course needs a code and a name.");
    try {
      await createCourse.mutateAsync({ code: code.trim(), name: name.trim(), instructor: instructor.trim(), schedule: schedule.trim(), room: "", term: "", is_fyp: isFyp, fyp_title: "", fyp_note: "" });
      say(`Added ${code.trim()}`);
      onClose();
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  return (
    <Sheet
      open
      onClose={onClose}
      title="Add course"
      footer={
        <>
          <Button variant="primary" type="submit" form="course-form" busy={createCourse.isPending}>
            Save
          </Button>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
        </>
      }
    >
      <form id="course-form" className={styles["form"]} onSubmit={(e) => void submit(e)}>
        <Field label="Code">{(id) => <Input id={id} mono value={code} onChange={(e) => setCode(e.target.value)} placeholder="CS3006" autoFocus />}</Field>
        <Field label="Name">{(id) => <Input id={id} value={name} onChange={(e) => setName(e.target.value)} placeholder="Parallel and Distributed Computing" />}</Field>
        <Field label="Instructor" hint="Optional.">{(id) => <Input id={id} value={instructor} onChange={(e) => setInstructor(e.target.value)} />}</Field>
        <Field label="Schedule" hint="Optional. Free text, e.g. Mon/Wed 11:00.">{(id) => <Input id={id} value={schedule} onChange={(e) => setSchedule(e.target.value)} />}</Field>
        <Field label="Final year project" hint="Marks this course as the FYP. Only one should be.">
          {(id) => (
            <Select id={id} value={isFyp ? "yes" : "no"} onChange={(e) => setIsFyp(e.target.value === "yes")}>
              <option value="no">No</option>
              <option value="yes">Yes</option>
            </Select>
          )}
        </Field>
        {error && <Mono tone="danger">{error}</Mono>}
      </form>
    </Sheet>
  );
}

function AssessmentSheet({ course, onClose }: { course: Course; onClose: () => void }) {
  const { createAssessment } = useAcademicsMutations();
  const { say } = useShell();
  const [kind, setKind] = useState<(typeof KINDS)[number]>("assignment");
  const [title, setTitle] = useState("");
  const [due, setDue] = useState(() => localInput(new Date(Date.now() + 7 * 24 * 3600_000)));
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return setError("Give the deadline a title.");
    if (!due) return setError("Pick a due date.");
    try {
      await createAssessment.mutateAsync({ course_id: course.id, kind, title: title.trim(), due_at: new Date(due).toISOString(), weight_pct: null, source_note: note.trim() });
      say(`${course.code} · ${title.trim()} added to tasks`);
      onClose();
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  return (
    <Sheet
      open
      onClose={onClose}
      title={`Add deadline · ${course.code}`}
      footer={
        <>
          <Button variant="primary" type="submit" form="assessment-form" busy={createAssessment.isPending}>
            Save
          </Button>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
        </>
      }
    >
      <form id="assessment-form" className={styles["form"]} onSubmit={(e) => void submit(e)}>
        <Field label="Kind">
          {(id) => (
            <Select id={id} value={kind} onChange={(e) => setKind(e.target.value as (typeof KINDS)[number])}>
              {KINDS.map((k) => (
                <option key={k} value={k}>
                  {k}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Title">{(id) => <Input id={id} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Quiz 2 — trees and bagging" autoFocus />}</Field>
        <Field label="Due">{(id) => <Input id={id} type="datetime-local" value={due} onChange={(e) => setDue(e.target.value)} />}</Field>
        <Field label="Where this came from" hint="Optional. The syllabus, a slide, an announcement.">{(id) => <TextArea id={id} rows={2} value={note} onChange={(e) => setNote(e.target.value)} />}</Field>
        <Mono tone="soft">This also becomes a task, so it shows up in your daily brief.</Mono>
        {error && <Mono tone="danger">{error}</Mono>}
      </form>
    </Sheet>
  );
}

export function Academics() {
  const [tab, setTab] = useState<Tab>("courses");
  const [courseId, setCourseId] = useState<number | null>(null);
  const [addingCourse, setAddingCourse] = useState(false);
  const courses = useCourses();
  useFinishBoot(!courses.isPending);

  const all = courses.data?.items ?? [];
  const taught = all.filter((c) => !c.is_fyp);
  const fyp = all.find((c) => c.is_fyp);
  const course = all.find((c) => c.id === courseId) ?? null;
  useHeaderMeta(taught.length ? `${taught.length} course${taught.length === 1 ? "" : "s"}` : null);

  return (
    <Screen paper>
      <ScreenHeader
        serif
        title="Academics"
        subtitle="Courses, deadlines and the final year project"
        actions={
          <div className={styles["actions"]}>
            {tab === "courses" && !courseId && (
              <Button size="sm" variant="primary" onClick={() => setAddingCourse(true)}>
                Add course
              </Button>
            )}
            <div className={styles["tabs"]} role="tablist">
              {(["courses", "fyp", "prep"] as const).map((t) => (
                <button
                  key={t}
                  type="button"
                  role="tab"
                  aria-selected={tab === t}
                  className={cx(styles["tab"], tab === t && styles["tabOn"])}
                  onClick={() => {
                    setTab(t);
                    setCourseId(null);
                  }}
                >
                  {t === "courses" ? "Courses" : t === "fyp" ? "FYP" : "Test prep"}
                </button>
              ))}
            </div>
          </div>
        }
      />

      {tab === "courses" && (
        <QueryState status={courses.status} error={courses.error} data={courses.data} onRetry={() => void courses.refetch()} rows={4}>
          {() =>
            course ? (
              <CourseDetail course={course} onBack={() => setCourseId(null)} />
            ) : taught.length === 0 ? (
              <EmptyState title="No courses yet" hint="Add a course and its deadlines will flow into your tasks and daily brief." />
            ) : (
              <Grid min="252px">
                {taught.map((c) => {
                  const tier = urgencyOf(c.next_due_at);
                  return (
                    <button key={c.id} type="button" className={styles["course"]} onClick={() => setCourseId(c.id)}>
                      <span className={styles["courseTop"]}>
                        <Mono size={10}>{c.code}</Mono>
                        <Mono tone={c.next_due_at ? urgencyMono(tier) : "muted"}>{c.next_due_label || "nothing due"}</Mono>
                      </span>
                      <span className={styles["courseName"]}>{c.name}</span>
                      <span className={styles["courseMeta"]}>{c.instructor || "—"}</span>
                      <span className={styles["courseCounts"]}>
                        <Mono>{c.document_count} docs</Mono>
                        <Mono>{c.assessment_count} deadlines</Mono>
                      </span>
                    </button>
                  );
                })}
              </Grid>
            )
          }
        </QueryState>
      )}

      {tab === "fyp" && (
        <QueryState status={courses.status} error={courses.error} data={courses.data} onRetry={() => void courses.refetch()} rows={3}>
          {() => <Fyp course={fyp} />}
        </QueryState>
      )}

      {tab === "prep" && (
        <EmptyState
          title="Test prep isn't built yet"
          hint="It needs a question-generation run over a course's materials, which has no endpoint so far. Until it exists, the course chat beside your materials is the closest thing — ask it to quiz you on a topic."
          action={
            <Button variant="ghost" onClick={() => setTab("courses")}>
              Go to courses
            </Button>
          }
        />
      )}

      {addingCourse && <CourseSheet onClose={() => setAddingCourse(false)} />}
    </Screen>
  );
}
