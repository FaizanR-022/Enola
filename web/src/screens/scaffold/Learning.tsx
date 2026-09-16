/** Self-learning scaffold.
 *
 *  TODO(wire): replace mock constants with
 *    - GET /api/learning-goals                    → GOALS
 *    - PATCH /api/learning-goals/{id}             → progress and resource ticks
 *    - GET /api/postings?status=saved + applications' tags → SKILL_GAPS
 *      (the gap computation is a small service: tags in saved postings minus tags on
 *       the owner's resume/projects; it does not exist yet)
 */

import { cx } from "@/lib/cx";
import { useFinishBoot, useHeaderMeta } from "@/shell/ShellState";
import { Badge, Card, Mono, ScreenHeader } from "@/ui";
import { Screen, Stack } from "../Screen";
import { GOALS, SKILL_GAPS } from "./mock";
import styles from "./Learning.module.css";

export function Learning() {
  useFinishBoot();
  useHeaderMeta(`${GOALS.length} goals`);
  return (
    <Screen narrow>
      <ScreenHeader title="Self-learning" subtitle="Goals are seeded from gaps in the postings you save." />
      <Card title="Skill gaps from saved postings" flush>
        <div className={styles["gaps"]}>
          {SKILL_GAPS.map((g) => (
            <Badge key={g.skill} tone="held" pill>
              {g.skill} · {g.postings}
            </Badge>
          ))}
        </div>
      </Card>
      <Stack>
        {GOALS.map((g) => (
          <Card key={g.id}>
            <div className={styles["head"]}>
              <span className={styles["title"]}>{g.title}</span>
              <Mono size={11} tone="soft">
                {g.progress_pct}%
              </Mono>
            </div>
            <div className={styles["track"]}>
              <span className={cx(styles["fill"], g.seeded_from_postings ? styles["fillAccent"] : styles["fillSoft"])} style={{ ["--pct" as string]: `${g.progress_pct}%` }} />
            </div>
            <span className={styles["gap"]}>{g.gap_note}</span>
            <div className={styles["resources"]}>
              {g.resources.map((r) => (
                <Badge key={r.id} tone={r.done ? "ok" : "accent"}>
                  {r.done ? "✓ " : ""}
                  {r.label}
                </Badge>
              ))}
            </div>
          </Card>
        ))}
      </Stack>
    </Screen>
  );
}
