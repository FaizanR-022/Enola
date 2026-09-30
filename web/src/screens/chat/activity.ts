/** Turning the agent's plumbing into something a person can skim.
 *
 *  A turn produces assistant messages that carry only tool calls, and tool messages
 *  carrying raw rows. Rendering those one-to-one shows the machine: "→ list_open_tasks"
 *  followed by a wall of piped ids. Here they collapse into one quiet line per turn —
 *  "Checked your tasks" — with the raw output available on demand for when something
 *  looks wrong.
 */

import type { ChatMessage } from "@/data";

/** What each tool did, in the owner's terms. Falls back to the raw name if a tool is
 *  added here without a label, which is visible but not broken. */
const LABELS: Record<string, string> = {
  search_people: "Looked through your people",
  list_open_tasks: "Checked your tasks",
  list_applications: "Checked your applications",
  search_documents: "Searched your documents",
  finance_summary: "Checked your spending",
  who_owes_me: "Checked who owes you",
  list_accounts: "Checked your accounts",
  list_categories: "Checked your categories",
  list_email_threads: "Looked at your inbox",
  read_email_thread: "Read the thread",
  create_task: "Added a task",
  log_interaction: "Logged a touchpoint",
  remember: "Remembered that",
  log_expense: "Logged the expense",
  log_income: "Logged the income",
  log_transfer: "Logged the transfer",
  split_expense: "Split the expense",
  record_settlement: "Recorded the settlement",
  send_email: "Drafted an email",
  delete_person: "Proposed removing a record",
};

export function labelFor(tool: string): string {
  return LABELS[tool] ?? tool.replace(/_/g, " ");
}

export interface ActivityStep {
  tool: string;
  label: string;
  output: string;
}

export type ThreadItem =
  | { kind: "message"; message: ChatMessage }
  | { kind: "activity"; steps: ActivityStep[] };

function isPlumbing(message: ChatMessage): boolean {
  // An assistant turn that only announces tool calls says nothing to the owner.
  return message.role === "tool" || (message.role === "enola" && !message.text.trim() && message.tool_calls.length > 0);
}

/** Collapse runs of tool activity into one item, keeping real replies as they are. */
export function groupThread(messages: ChatMessage[]): ThreadItem[] {
  const items: ThreadItem[] = [];
  let open: ActivityStep[] | null = null;
  let pending: string[] = [];

  const flush = () => {
    if (open && open.length) items.push({ kind: "activity", steps: open });
    open = null;
    pending = [];
  };

  for (const message of messages) {
    if (!isPlumbing(message)) {
      // A reply with text can still carry tool calls; keep the text, drop the calls.
      flush();
      items.push({ kind: "message", message });
      continue;
    }
    open ??= [];
    if (message.role === "enola") {
      pending.push(...message.tool_calls.map((c) => String(c["name"])));
      continue;
    }
    const tool = message.tool_name ?? pending.shift() ?? "tool";
    open.push({ tool, label: labelFor(tool), output: message.text });
  }
  flush();
  return items;
}

/** One line for a whole run of activity. Repeats collapse: a model that asks the same
 *  question twice should not look twice as busy. */
export function summarise(steps: ActivityStep[]): string {
  const seen: string[] = [];
  for (const step of steps) {
    if (!seen.includes(step.label)) seen.push(step.label);
  }
  if (seen.length === 1) return seen[0]!;
  if (seen.length === 2) return `${seen[0]} and ${lower(seen[1]!)}`;
  return `${seen.slice(0, -1).join(", ")} and ${lower(seen[seen.length - 1]!)}`;
}

function lower(text: string): string {
  return text.charAt(0).toLowerCase() + text.slice(1);
}
