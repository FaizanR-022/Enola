import { NavLink } from "react-router-dom";
import { useOwner } from "@/lib/auth";
import { useHeldCount, useReminderCount } from "@/lib/held";
import { cx } from "@/lib/cx";
import { Avatar, Badge, Dot, Mono } from "@/ui";
import { useShell } from "./ShellState";
import { Wordmark } from "./Wordmark";
import { NAV_SECTIONS, type ScreenId } from "./screens";
import styles from "./Nav.module.css";

export function Nav({ current }: { current: ScreenId }) {
  const owner = useOwner();
  const held = useHeldCount();
  const reminders = useReminderCount();
  const { setSettingsOpen } = useShell();

  return (
    <nav className={styles["nav"]} aria-label="Primary">
      <div className={styles["brand"]}>
        <Wordmark size="sm" />
      </div>
      <div className={styles["sections"]}>
        {NAV_SECTIONS.map((section) => (
          <div key={section.label} className={styles["section"]}>
            <Mono upper className={styles["sectionLabel"]}>
              {section.label}
            </Mono>
            {section.items.map((item) => (
              <NavLink key={item.id} to={item.path} className={cx(styles["item"], current === item.id && styles["active"])} end={item.path === "/"}>
                <Dot tone={current === item.id ? "accent" : item.dot} />
                <span className={styles["label"]}>{item.label}</span>
                {item.badge === "held" && held > 0 && (
                  <Badge tone="held" pill>
                    {held}
                  </Badge>
                )}
                {item.id === "home" && reminders > 0 && (
                  <Badge tone="neutral" pill title={`${reminders} unread reminders`}>
                    {reminders}
                  </Badge>
                )}
              </NavLink>
            ))}
          </div>
        ))}
      </div>
      <div className={styles["foot"]}>
        <Avatar name={owner.data?.name ?? "?"} size="sm" />
        <span className={styles["owner"]}>{owner.data?.name ?? ""}</span>
        <NavLink to="/memory" className={cx(styles["memoryLink"])}>
          <Mono>memory</Mono>
        </NavLink>
        <button type="button" className={cx(styles["memoryLink"])} onClick={() => setSettingsOpen(true)} aria-label="Settings">
          <Mono>settings</Mono>
        </button>
      </div>
    </nav>
  );
}
