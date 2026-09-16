import { useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useHeldCount } from "@/lib/held";
import { cx } from "@/lib/cx";
import { Badge, Dot, Mono, Sheet } from "@/ui";
import { PHONE_MORE, PHONE_TABS, type ScreenId } from "./screens";
import styles from "./PhoneTabs.module.css";

/** Phone navigation: four tabs at the bottom, the other screens in a sheet. */
export function PhoneTabs({ current }: { current: ScreenId }) {
  const [moreOpen, setMoreOpen] = useState(false);
  const navigate = useNavigate();
  const held = useHeldCount();
  const inMore = PHONE_MORE.some((s) => s.id === current);

  return (
    <>
      <nav className={styles["tabs"]} aria-label="Primary">
        {PHONE_TABS.map((tab) => {
          const active = current === tab.id && !moreOpen;
          return (
            <NavLink key={tab.id} to={tab.path} end={tab.path === "/"} className={cx(styles["tab"])} onClick={() => setMoreOpen(false)}>
              <Dot size={7} tone={active ? (tab.id === "approvals" ? "held" : "accent") : "line"} className={styles["square"]} />
              <Mono tone={active ? "text" : "muted"} size={10}>
                {tab.id === "approvals" ? "held" : tab.label.toLowerCase()}
              </Mono>
              {tab.badge === "held" && held > 0 && (
                <Badge tone="held" solid pill className={styles["badge"]}>
                  {held}
                </Badge>
              )}
            </NavLink>
          );
        })}
        <button type="button" className={cx(styles["tab"])} onClick={() => setMoreOpen((v) => !v)} aria-expanded={moreOpen}>
          <Dot size={7} tone={moreOpen || inMore ? "accent" : "line"} className={styles["square"]} />
          <Mono tone={moreOpen || inMore ? "text" : "muted"} size={10}>
            more
          </Mono>
        </button>
      </nav>
      <Sheet open={moreOpen} onClose={() => setMoreOpen(false)} bare>
        <div className={styles["grid"]}>
          {PHONE_MORE.map((screen) => (
            <button
              key={screen.id}
              type="button"
              className={cx(styles["cell"], current === screen.id && styles["cellActive"])}
              onClick={() => {
                setMoreOpen(false);
                navigate(screen.path);
              }}
            >
              <Dot size={6} tone={screen.dot} />
              <span className={styles["cellLabel"]}>{screen.label}</span>
            </button>
          ))}
        </div>
      </Sheet>
    </>
  );
}
