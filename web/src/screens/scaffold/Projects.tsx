/** Projects scaffold. "Remind me what this repo was." Deliberately shallow.
 *
 *  TODO(wire): replace mock constants with
 *    - GET /api/projects                                   → PROJECTS
 *    - PATCH /api/projects/{id}                            → status / summary edits
 *    - GET /api/tasks?entity_type=project&entity_id=<id>   → linked tasks
 *  Structure summaries come from a WRITE_LOCAL agent tool that reads the repo's top level;
 *  it does not exist yet and must never become a code browser.
 */

import { agoLabel } from "@/lib/format";
import { useFinishBoot, useHeaderMeta } from "@/shell/ShellState";
import { Badge, Card, Dot, Mono, ScreenHeader } from "@/ui";
import { Grid, Screen } from "../Screen";
import { PROJECTS } from "./mock";
import styles from "./Projects.module.css";

function statusTone(status: string): "ok" | "accent" | "muted" {
  return status === "active" ? "ok" : status === "coursework" ? "accent" : "muted";
}

export function Projects() {
  useFinishBoot();
  useHeaderMeta(`${PROJECTS.length} repos`);
  return (
    <Screen>
      <ScreenHeader title="Projects" subtitle="“Remind me what this repo was.” Deliberately shallow." />
      <Grid min="288px">
        {PROJECTS.map((p) => (
          <Card key={p.id}>
            <div className={styles["head"]}>
              <Dot size={6} tone={statusTone(p.status)} />
              <Mono size={12} tone="text">
                {p.name}
              </Mono>
              <span className={styles["spacer"]} />
              <Mono upper>{p.status}</Mono>
            </div>
            <p className={styles["summary"]}>{p.summary}</p>
            <div className={styles["stack"]}>
              {p.stack.map((s) => (
                <Badge key={s} tone="soft">
                  {s}
                </Badge>
              ))}
            </div>
            <div className={styles["foot"]}>
              <Mono>{p.linked_task_count} linked tasks</Mono>
              <Mono>touched {agoLabel(p.last_touched_at)}</Mono>
            </div>
          </Card>
        ))}
      </Grid>
    </Screen>
  );
}
