/** Join class names, dropping falsy values. CSS-module lookups are `string | undefined`
 *  under noUncheckedIndexedAccess, so every className goes through here. */
export function cx(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}
