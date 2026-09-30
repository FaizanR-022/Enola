import { useNavigate } from "react-router-dom";
import type { Person } from "@/data";
import { agoLabel } from "@/lib/format";
import { Avatar, Badge, CardRow, Mono } from "@/ui";
import styles from "./PersonRow.module.css";

function lastTone(person: Person): "ok" | "danger" | "soft" | "muted" {
  if (person.going_cold) return "danger";
  if (person.days_since_contact === null) return "muted";
  return person.days_since_contact <= 1 ? "ok" : "soft";
}

export function PersonRow({ person, compact = false }: { person: Person; compact?: boolean | undefined }) {
  const navigate = useNavigate();
  return (
    <CardRow interactive onClick={() => navigate(`/people/${person.id}`)} className={styles["row"]}>
      <Avatar name={person.name} size={compact ? "sm" : "md"} />
      <span className={styles["main"]}>
        <span className={styles["name"]}>{person.name}</span>
        <span className={styles["role"]}>{person.role}</span>
      </span>
      {!compact && (
        <span className={styles["tags"]}>
          {person.tags.slice(0, 3).map((tag) => (
            <Badge key={tag} tone="soft">
              {tag}
            </Badge>
          ))}
        </span>
      )}
      <Mono size={10} tone={lastTone(person)} className={styles["last"]}>
        {agoLabel(person.last_contacted_at)}
      </Mono>
    </CardRow>
  );
}
