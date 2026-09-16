import { cx } from "@/lib/cx";
import styles from "./Avatar.module.css";

export interface AvatarProps {
  name: string;
  size?: "sm" | "md" | "lg" | undefined;
  /** Square with accent fill: Enola herself. */
  enola?: boolean | undefined;
  className?: string | undefined;
}

export function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}

export function Avatar({ name, size = "md", enola = false, className }: AvatarProps) {
  return (
    <span className={cx(styles["avatar"], styles[size], enola && styles["enola"], className)} aria-hidden>
      {enola ? "E" : initials(name)}
    </span>
  );
}
