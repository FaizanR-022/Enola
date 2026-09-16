/** Academics scaffold. Styled against mock data.
 *
 *  TODO(wire): replace mock constants with
 *    - GET /api/courses                         → useCourses()           (COURSES)
 *    - GET /api/assessments?course_id=          → deadlines per course   (COURSE_DEADLINES)
 *    - GET /api/documents?scope=course:<id>     → materials              (COURSE_FILES)
 *    - POST /api/documents (multipart, entity_type=course, entity_id)   → upload
 *    - GET /api/fyp-milestones?course_id=<fyp>  → FYP_MILESTONES
 *    - POST /api/chat {thread_id: "course:<id>", scope: "course:<id>"}  → scoped chat
 *      (retrieval is already scoped server-side: see enola/agent/tools/documents.py)
 *  Test prep has no endpoint yet; it needs a question-generation run over the course scope.
 */

import { useState } from "react";
import { cx } from "@/lib/cx";
import { useFinishBoot, useHeaderMeta } from "@/shell/ShellState";
import { Badge, Button, Card, CardRow, Dot, Mono, ScreenHeader } from "@/ui";
import { Grid, Screen, Stack } from "../Screen";
import { COURSES, COURSE_CHAT, COURSE_DEADLINES, COURSE_FILES, FYP, FYP_MILESTONES, FYP_NOTES } from "./mock";
import styles from "./Academics.module.css";

type Tab = "courses" | "fyp" | "prep";

export function Academics() {
  const [tab, setTab] = useState<Tab>("courses");
  const [courseId, setCourseId] = useState<number | null>(null);
  useFinishBoot();
  useHeaderMeta("Fall 2026 · 5 courses");
  const course = COURSES.find((c) => c.id === courseId) ?? null;

  return (
    <Screen paper>
      <ScreenHeader
        serif
        title="Academics"
        subtitle="Fall 2026 · final year · 5 courses and the FYP"
        actions={
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
        }
      />

      {tab === "courses" && !course && (
        <Grid min="252px">
          {COURSES.map((c) => (
            <button key={c.id} type="button" className={styles["course"]} onClick={() => setCourseId(c.id)}>
              <span className={styles["courseTop"]}>
                <Mono size={10}>{c.code}</Mono>
                <Mono tone={c.next_due_label.includes("today") ? "danger" : c.next_due_label.startsWith("asgn") ? "held" : "muted"}>{c.next_due_label}</Mono>
              </span>
              <span className={styles["courseName"]}>{c.name}</span>
              <span className={styles["courseMeta"]}>{c.instructor}</span>
              <span className={styles["courseCounts"]}>
                <Mono>{c.document_count} docs</Mono>
                <Mono>{c.assessment_count} deadlines</Mono>
              </span>
            </button>
          ))}
        </Grid>
      )}

      {tab === "courses" && course && (
        <Stack>
          <Button variant="link" onClick={() => setCourseId(null)}>
            ← All courses
          </Button>
          <div>
            <Mono size={10}>{course.code}</Mono>
            <h2 className={styles["courseTitle"]}>{course.name}</h2>
            <div className={styles["courseSub"]}>
              {course.instructor} · {course.room}
            </div>
          </div>
          <div className={styles["detail"]}>
            <Stack>
              <Card title="Deadlines" flush note="Extracted from the syllabus and slide decks. Enola asks before adding anything it is unsure about.">
                {COURSE_DEADLINES.map((d) => (
                  <CardRow key={d.title}>
                    <Mono upper tone={d.tone} className={styles["kind"]}>
                      {d.kind}
                    </Mono>
                    <span className={styles["deadlineTitle"]}>{d.title}</span>
                    <Mono size={11} tone={d.tone}>
                      {d.when}
                    </Mono>
                  </CardRow>
                ))}
              </Card>
              <Card title="Materials" meta={<Button variant="link">Upload</Button>}>
                <div className={styles["files"]}>
                  {COURSE_FILES.map((f) => (
                    <button key={f.name} type="button" className={styles["file"]}>
                      <span className={styles["fileThumb"]}>
                        <Mono className={styles["fileExt"]}>{f.ext}</Mono>
                      </span>
                      <Mono size={10} tone="soft" className={styles["fileName"]}>
                        {f.name}
                      </Mono>
                    </button>
                  ))}
                </div>
              </Card>
            </Stack>
            <Card
              title="Chat"
              meta={
                <Badge tone="neutral" pill>
                  scoped: {course.code} only
                </Badge>
              }
              flush
              className={styles["chat"]}
            >
              <div className={styles["chatBody"]}>
                {COURSE_CHAT.map((m, i) => (
                  <div key={i} className={styles["msg"]}>
                    <Mono upper tone={m.who === "enola" ? "accent" : "muted"}>
                      {m.who}
                    </Mono>
                    <span className={styles["msgText"]}>{m.text}</span>
                    {m.cite && <span className={styles["cite"]}>{m.cite}</span>}
                  </div>
                ))}
              </div>
              <div className={styles["chatBox"]}>Ask about these {course.document_count} documents…</div>
            </Card>
          </div>
        </Stack>
      )}

      {tab === "fyp" && (
        <Grid min="290px">
          <Stack>
            <div>
              <Mono size={10}>FYP · {FYP.code}</Mono>
              <h2 className={styles["fypTitle"]}>{FYP.title}</h2>
              <p className={styles["fypNote"]}>{FYP.note}</p>
            </div>
            <Card title="Milestones" flush>
              {FYP_MILESTONES.map((m) => (
                <CardRow key={m.id} align="start">
                  <Dot size={9} tone={m.state === "done" ? "accent" : m.state === "current" ? "held" : "line"} hollow={m.state === "upcoming"} className={styles["milestoneDot"]} />
                  <span className={styles["milestoneMain"]}>
                    <span className={cx(styles["milestoneTitle"], m.state === "upcoming" && styles["muted"])}>{m.title}</span>
                    {m.note && <span className={styles["milestoneNote"]}>{m.note}</span>}
                  </span>
                  <Mono>{m.due_at ? new Date(m.due_at).toLocaleDateString(undefined, { day: "numeric", month: "short" }) : "—"}</Mono>
                </CardRow>
              ))}
            </Card>
          </Stack>
          <Card title="Research notes" flush>
            {FYP_NOTES.map((n) => (
              <CardRow key={n.title} align="start" className={styles["note"]}>
                <span className={styles["noteMain"]}>
                  <span className={styles["noteTitle"]}>{n.title}</span>
                  <span className={styles["noteBody"]}>{n.body}</span>
                  <Mono>{n.meta}</Mono>
                </span>
              </CardRow>
            ))}
          </Card>
        </Grid>
      )}

      {tab === "prep" && (
        <Stack className={styles["prep"]}>
          <Card>
            <div className={styles["prepHead"]}>
              <div>
                <div className={styles["prepTitle"]}>Test prep · ML quiz 2</div>
                <div className={styles["prepSub"]}>Today 11:00 · trees, bagging, boosting. Built from lectures 5–7 and last year's quiz.</div>
              </div>
              <Badge pill>1h 19m left</Badge>
            </div>
          </Card>
          <Card tone="flat">
            <Mono upper>Question 4 of 12</Mono>
            <div className={styles["question"]}>Why does a random forest reduce variance more than a single deep tree, and what does bagging alone fail to fix?</div>
            <div className={styles["prepActions"]}>
              <Button>Show answer</Button>
              <Button variant="ghost">I got it wrong</Button>
              <Button variant="ghost">Skip</Button>
            </div>
            <div className={styles["prepFoot"]}>Wrong answers come back at the end and again tomorrow morning. Nothing leaves this mode; Enola will not post a score anywhere.</div>
          </Card>
          <div className={styles["stats"]}>
            {[
              ["9/12", "correct this session", "ok"],
              ["3", "coming back tomorrow", "held"],
              ["41m", "studied today", "soft"],
            ].map(([v, k, tone]) => (
              <Card key={k}>
                <Mono size={12} bold tone={tone as "ok" | "held" | "soft"} className={styles["statValue"]}>
                  {v}
                </Mono>
                <span className={styles["statKey"]}>{k}</span>
              </Card>
            ))}
          </div>
        </Stack>
      )}
    </Screen>
  );
}
