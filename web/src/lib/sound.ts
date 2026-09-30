/** Short synthesized cues. No audio files: an oscillator and a fast gain envelope.
 *
 *  Rules: the AudioContext is created lazily on the first user gesture (browsers block
 *  it otherwise); nothing plays while the tab is hidden; nothing plays for events the
 *  user did not trigger; and the mute setting lives in localStorage. */

import { readSetting, writeSetting } from "./settings";

type Cue = "done" | "dismissed" | "held" | "sent" | "reply";

let context: AudioContext | null = null;
let unlocked = false;

/** Call from a click/keydown handler once; later cues can play from anywhere. */
export function unlockAudio(): void {
  if (unlocked) return;
  try {
    context ??= new AudioContext();
    if (context.state === "suspended") void context.resume();
    unlocked = true;
  } catch {
    context = null;
  }
}

if (typeof window !== "undefined") {
  const once = () => {
    unlockAudio();
    window.removeEventListener("pointerdown", once);
    window.removeEventListener("keydown", once);
  };
  window.addEventListener("pointerdown", once);
  window.addEventListener("keydown", once);
}

export function isMuted(): boolean {
  return readSetting("soundMuted", false);
}

export function setMuted(muted: boolean): void {
  writeSetting("soundMuted", muted);
}

function tone(ctx: AudioContext, at: number, from: number, to: number, ms: number, gain: number): void {
  const osc = ctx.createOscillator();
  const env = ctx.createGain();
  osc.type = "sine";
  osc.frequency.setValueAtTime(from, at);
  osc.frequency.exponentialRampToValueAtTime(to, at + ms / 1000);
  env.gain.setValueAtTime(0.0001, at);
  env.gain.exponentialRampToValueAtTime(gain, at + 0.008);
  env.gain.exponentialRampToValueAtTime(0.0001, at + ms / 1000);
  osc.connect(env).connect(ctx.destination);
  osc.start(at);
  osc.stop(at + ms / 1000 + 0.02);
}

/** Pitch carries meaning: rising for done, falling for dismissed, a soft two-note for Held. */
export function play(cue: Cue): void {
  if (isMuted() || document.visibilityState !== "visible" || !unlocked || !context) return;
  const ctx = context;
  const now = ctx.currentTime;
  // Gains were 0.035-0.05, which is inaudible over laptop speakers: the cues fired and
  // nobody ever heard one. Loud enough to notice, short enough not to intrude.
  switch (cue) {
    case "done":
      tone(ctx, now, 520, 790, 130, 0.22);
      break;
    case "dismissed":
      tone(ctx, now, 620, 360, 150, 0.18);
      break;
    case "held":
      tone(ctx, now, 440, 440, 90, 0.2);
      tone(ctx, now + 0.1, 560, 560, 110, 0.2);
      break;
    case "sent":
      tone(ctx, now, 680, 920, 80, 0.16);
      break;
    // An answer landing is the cue you actually want: ask, look away, hear it arrive.
    case "reply":
      tone(ctx, now, 560, 700, 90, 0.18);
      break;
  }
}
