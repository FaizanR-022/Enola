import { cx } from "@/lib/cx";
import { Badge, Mono } from "@/ui";
import { ChatThread } from "@/screens/chat/ChatThread";
import { useShell } from "./ShellState";
import type { Screen } from "./screens";
import styles from "./ChatRail.module.css";

/** Same conversation as the Chat tab: a viewport onto it, scoped to the current screen. */
export function ChatRail({ screen }: { screen: Screen }) {
  const { setRailMode, railMode } = useShell();
  const scope = screen.id === "home" ? "today" : screen.id;
  return (
    <aside className={cx(styles["rail"], railMode === "full" && styles["full"])} aria-label="Chat rail">
      <header className={styles["head"]}>
        <Mono upper>Chat</Mono>
        <Badge tone="accent" pill>
          scoped: {scope}
        </Badge>
        <span className={styles["spacer"]} />
        <button type="button" className={styles["close"]} onClick={() => setRailMode(railMode === "full" ? "rail" : "full")} aria-label={railMode === "full" ? "Back to rail" : "Full screen"} title={railMode === "full" ? "Back to rail (Esc)" : "Full screen"}>
          {railMode === "full" ? "⤡" : "⤢"}
        </button>
        <button type="button" className={styles["close"]} onClick={() => setRailMode("closed")} aria-label="Close chat rail">
          ✕
        </button>
      </header>
      <div className={styles["body"]}>
        {railMode !== "full" && <p className={styles["note"]}>Same conversation as the Chat tab. This is a viewport onto it, not a second thread. Whatever screen you are on becomes the scope.</p>}
        <ChatThread scope={scope} compact={railMode !== "full"} />
      </div>
    </aside>
  );
}
