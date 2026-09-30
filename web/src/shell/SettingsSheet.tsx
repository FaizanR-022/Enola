import { useSetting } from "@/lib/settings";
import { play, unlockAudio } from "@/lib/sound";
import { useTheme } from "@/theme/theme";
import { Button, Mono, Sheet } from "@/ui";
import { VoiceSettings } from "./VoiceSettings";
import styles from "./SettingsSheet.module.css";

/** Per-device preferences. Nothing here touches the server. */
export function SettingsSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { theme, setTheme } = useTheme();
  const [muted, setMuted] = useSetting("soundMuted");

  return (
    <Sheet open={open} onClose={onClose} title="Settings" width="sm">
      <section className={styles["group"]}>
        <Mono upper>Theme</Mono>
        <div className={styles["row"]}>
          <Button size="sm" variant={theme === "dark" ? "primary" : "ghost"} onClick={() => setTheme("dark")}>
            Dark
          </Button>
          <Button size="sm" variant={theme === "light" ? "primary" : "ghost"} onClick={() => setTheme("light")}>
            Light
          </Button>
        </div>
      </section>
      <section className={styles["group"]}>
        <Mono upper>Sound</Mono>
        <label className={styles["toggle"]}>
          <input
            type="checkbox"
            checked={!muted}
            onChange={(e) => {
              unlockAudio();
              setMuted(!e.target.checked);
              if (e.target.checked) play("done");
            }}
          />
          <span>Play short cues for done, sent and Held</span>
        </label>
        <p className={styles["hint"]}>Synthesized in the browser, never while the tab is in the background. Saved on this device.</p>
      </section>
      <VoiceSettings />
    </Sheet>
  );
}
