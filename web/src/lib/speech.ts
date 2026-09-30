/** Browser speech, both directions. Push-to-talk over the Web Speech API's
 *  SpeechRecognition (transcripts only ever land in the input; nothing here sends), and
 *  replies over speechSynthesis with the voice and rate from settings.
 *
 *  Rules: playback is cancelled by any new input and by the stop control; the mic is
 *  offered only where recognition actually works, with the reason exposed otherwise. */

import { useSyncExternalStore } from "react";
import { readSetting } from "./settings";

// The DOM lib does not type SpeechRecognition; this is the slice we use.
interface RecognitionResult {
  readonly isFinal: boolean;
  readonly length: number;
  [index: number]: { readonly transcript: string };
}
interface RecognitionEvent {
  readonly resultIndex: number;
  readonly results: { readonly length: number; [index: number]: RecognitionResult };
}
interface Recognition {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  onresult: ((event: RecognitionEvent) => void) | null;
  onend: (() => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}
type RecognitionCtor = new () => Recognition;

function recognitionCtor(): RecognitionCtor | null {
  const w = window as unknown as { SpeechRecognition?: RecognitionCtor; webkitSpeechRecognition?: RecognitionCtor };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

export type RecognitionStatus = { ok: true } | { ok: false; reason: string };

/** Whether push-to-talk can work here, and if not, why (shown on hover). */
export function recognitionStatus(): RecognitionStatus {
  if (typeof window === "undefined") return { ok: false, reason: "No window." };
  if (!window.isSecureContext) return { ok: false, reason: "No mic: speech recognition needs HTTPS, or localhost." };
  if (!recognitionCtor()) return { ok: false, reason: "No mic: this browser has no speech recognition. Chrome and Edge do." };
  return { ok: true };
}

export interface ListenHandlers {
  onTranscript: (text: string, final: boolean) => void;
  onEnd: () => void;
  onError: (message: string) => void;
}

const ERRORS: Record<string, string> = {
  "not-allowed": "Microphone access was refused.",
  "audio-capture": "No microphone found.",
  network: "Speech recognition needs a network connection.",
  "no-speech": "Heard nothing.",
};

/** Start listening. Returns a handle whose stop() ends the capture; the final transcript
 *  arrives through onTranscript before onEnd. Null when recognition is unavailable. */
export function listen(handlers: ListenHandlers): { stop: () => void } | null {
  const Ctor = recognitionCtor();
  if (!Ctor || !recognitionStatus().ok) return null;
  const rec = new Ctor();
  rec.lang = navigator.language || "en-US";
  rec.interimResults = true;
  rec.continuous = true;
  rec.onresult = (event) => {
    let text = "";
    let final = true;
    for (let i = 0; i < event.results.length; i += 1) {
      const result = event.results[i];
      if (!result) continue;
      text += result[0]?.transcript ?? "";
      if (!result.isFinal) final = false;
    }
    handlers.onTranscript(text.trim(), final);
  };
  rec.onerror = (event) => {
    if (event.error === "aborted") return;
    handlers.onError(ERRORS[event.error] ?? `Speech recognition failed (${event.error}).`);
  };
  rec.onend = () => handlers.onEnd();
  try {
    rec.start();
  } catch {
    handlers.onError("Could not start the microphone.");
    return null;
  }
  return { stop: () => rec.stop() };
}

// ---- synthesis -----------------------------------------------------------------------

export function synthesisSupported(): boolean {
  return typeof window !== "undefined" && "speechSynthesis" in window && "SpeechSynthesisUtterance" in window;
}

const listeners = new Set<() => void>();
let speaking = false;
let current: SpeechSynthesisUtterance | null = null;

function setSpeaking(next: boolean): void {
  if (speaking === next) return;
  speaking = next;
  listeners.forEach((fn) => fn());
}

function subscribe(fn: () => void): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

/** True while Enola is talking. Drives the stop control. */
export function useSpeaking(): boolean {
  return useSyncExternalStore(subscribe, () => speaking, () => false);
}

export function voices(): SpeechSynthesisVoice[] {
  if (!synthesisSupported()) return [];
  return window.speechSynthesis.getVoices();
}

/** Speak text with the configured voice and rate. Replaces anything already playing. */
export function speak(text: string): void {
  if (!synthesisSupported() || !text.trim()) return;
  stopSpeaking();
  const utterance = new SpeechSynthesisUtterance(text);
  const wanted = readSetting("voiceName", "");
  const voice = wanted ? voices().find((v) => v.name === wanted) : undefined;
  if (voice) utterance.voice = voice;
  utterance.rate = readSetting("speechRate", 1);
  utterance.onend = () => {
    if (current === utterance) {
      current = null;
      setSpeaking(false);
    }
  };
  utterance.onerror = utterance.onend;
  current = utterance;
  setSpeaking(true);
  window.speechSynthesis.speak(utterance);
}

/** The explicit stop, and what every new input calls. */
export function stopSpeaking(): void {
  if (!synthesisSupported()) return;
  if (current !== null || window.speechSynthesis.speaking || window.speechSynthesis.pending) {
    window.speechSynthesis.cancel();
  }
  current = null;
  setSpeaking(false);
}
