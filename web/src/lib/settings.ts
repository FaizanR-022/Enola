/** Per-device preferences in localStorage: sound, voice. Server state never lives here. */

import { useCallback, useSyncExternalStore } from "react";

export interface Settings {
  soundMuted: boolean;
  autoSpeak: boolean;
  voiceName: string;
  speechRate: number;
}

const DEFAULTS: Settings = { soundMuted: false, autoSpeak: false, voiceName: "", speechRate: 1 };
const KEY = "enola.settings";
const listeners = new Set<() => void>();
let cache: Settings | null = null;

function load(): Settings {
  if (cache) return cache;
  try {
    const raw = window.localStorage.getItem(KEY);
    cache = raw ? { ...DEFAULTS, ...(JSON.parse(raw) as Partial<Settings>) } : { ...DEFAULTS };
  } catch {
    cache = { ...DEFAULTS };
  }
  return cache;
}

export function readSetting<K extends keyof Settings>(key: K, fallback: Settings[K]): Settings[K] {
  const value = load()[key];
  return value === undefined ? fallback : value;
}

export function writeSetting<K extends keyof Settings>(key: K, value: Settings[K]): void {
  cache = { ...load(), [key]: value };
  try {
    window.localStorage.setItem(KEY, JSON.stringify(cache));
  } catch {
    /* storage blocked: the in-memory copy still applies for this session */
  }
  listeners.forEach((fn) => fn());
}

function subscribe(fn: () => void): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

/** React hook over one setting. */
export function useSetting<K extends keyof Settings>(key: K): [Settings[K], (value: Settings[K]) => void] {
  const value = useSyncExternalStore(subscribe, () => load()[key], () => DEFAULTS[key]);
  const set = useCallback((next: Settings[K]) => writeSetting(key, next), [key]);
  return [value, set];
}
