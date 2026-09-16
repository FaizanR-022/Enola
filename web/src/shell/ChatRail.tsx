import { Badge, Mono } from "@/ui";
import { ChatThread } from "@/screens/chat/ChatThread";
import { useShell } from "./ShellState";
import type { Screen } from "./screens";
import styles from "./ChatRail.module.css";

/** Same conversation as the Chat tab: a viewport onto it, scoped to the current screen. */
export function ChatRail({ screen }: { screen: Screen }) {
  const { setRailOpen } = useShell();
  const scope = screen.id === "home" ? "today" : screen.id;
  return (
    <aside className={styles["rail"]} aria-label="Chat rail">
      <header className={styles["head"]}>
        <Mono upper>Chat</Mono>
        <Badge tone="accent" pill>
          scoped: {scope}
        </Badge>
        <span className={styles["spacer"]} />
        <button type="button" className={styles["close"]} onClick={() => setRailOpen(false)} aria-label="Close chat rail">
          ✕
        </button>
      </header>
      <div className={styles["body"]}>
        <p className={styles["note"]}>Same conversation as the Chat tab. This is a viewport onto it, not a second thread. Whatever screen you are on becomes the scope.</p>
        <ChatThread scope={scope} compact />
      </div>
    </aside>
  );
}
