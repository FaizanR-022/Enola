import { useEffect, useState } from "react";
import { useSetting } from "@/lib/settings";
import { recognitionStatus, speak, stopSpeaking, synthesisSupported, useSpeaking, voices } from "@/lib/speech";
import { Button, Mono, Select } from "@/ui";
import styles from "./SettingsSheet.module.css";

const SAMPLE = "Drafted, not sent. It's waiting for your approval in Approvals.";

/** Voice settings: auto-speak (off by default), voice, rate. Persisted per device. */
export function VoiceSettings() {
  const [autoSpeak, setAutoSpeak] = useSetting("autoSpeak");
  const [voiceName, setVoiceName] = useSetting("voiceName");
  const [rate, setRate] = useSetting("speechRate");
  const speaking = useSpeaking();
  const [list, setList] = useState<SpeechSynthesisVoice[]>(() => voices());
  const canSpeak = synthesisSupported();
  const mic = recognitionStatus();

  useEffect(() => {
    if (!canSpeak) return;
    const refresh = () => setList(voices());
    refresh();
    window.speechSynthesis.addEventListener("voiceschanged", refresh);
    return () => window.speechSynthesis.removeEventListener("voiceschanged", refresh);
  }, [canSpeak]);

  return (
    <section className={styles["group"]}>
      <Mono upper>Voice</Mono>
      {!canSpeak ? (
        <p className={styles["hint"]}>This browser cannot speak (no speechSynthesis). Text replies still work.</p>
      ) : (
        <>
          <label className={styles["toggle"]}>
            <input type="checkbox" checked={autoSpeak} onChange={(e) => setAutoSpeak(e.target.checked)} />
            <span>Read every reply aloud</span>
          </label>
          <p className={styles["hint"]}>Off by default. Replies to something you said with the mic are always spoken. Any new input stops playback, and a Held reply says so before anything else.</p>
          <label className={styles["toggle"]}>
            <span>Voice</span>
            <Select className={styles["select"]} value={voiceName} onChange={(e) => setVoiceName(e.target.value)} aria-label="Voice">
              <option value="">Browser default</option>
              {list.map((v) => (
                <option key={v.name} value={v.name}>
                  {v.name} · {v.lang}
                </option>
              ))}
            </Select>
          </label>
          <label className={styles["toggle"]}>
            <span>Rate</span>
            <input className={styles["range"]} type="range" min={0.7} max={1.5} step={0.1} value={rate} onChange={(e) => setRate(Number(e.target.value))} aria-label="Speech rate" />
            <Mono>{rate.toFixed(1)}×</Mono>
          </label>
          <div className={styles["row"]}>
            <Button size="sm" onClick={() => speak(SAMPLE)} disabled={speaking}>
              Hear a sample
            </Button>
            {speaking && (
              <Button size="sm" variant="ghost" onClick={stopSpeaking}>
                Stop
              </Button>
            )}
          </div>
        </>
      )}
      <p className={styles["hint"]}>{mic.ok ? "Push-to-talk: hold the mic in chat, speak, release. The words land in the box for you to check; nothing sends until you press Send." : mic.reason}</p>
    </section>
  );
}
