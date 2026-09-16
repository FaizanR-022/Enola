import { useSearch } from "@/data";
import type { DotTone } from "@/ui";

export interface PaletteHit {
  id: string;
  label: string;
  meta: string;
  dot: DotTone;
  path: string;
  group?: string;
}

const TONES: ReadonlySet<string> = new Set(["line", "muted", "soft", "accent", "held", "ok", "danger", "paper"]);

function toTone(value: string): DotTone {
  return (TONES.has(value) ? value : "muted") as DotTone;
}

/** Global search for the palette, shaped for its rows. */
export function usePaletteSearch(query: string) {
  const search = useSearch(query);
  const data: PaletteHit[] | undefined = search.data?.map((hit, index) => ({
    id: `${hit.group}:${hit.path}:${index}`,
    label: hit.label,
    meta: hit.meta,
    dot: toTone(hit.dot),
    path: hit.path,
    group: hit.group,
  }));
  return { data, isFetching: search.isFetching };
}
