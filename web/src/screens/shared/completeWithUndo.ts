import type { Task } from "@/data";
import type { Schemas } from "@/lib/api";
import { play } from "@/lib/sound";
import type { ToastAction } from "@/shell/ShellState";

type SetState = (vars: { id: number; state: Schemas["TaskState"] }, options?: { onSuccess?: () => void }) => void;
type Say = (message: string, action?: ToastAction, durationMs?: number) => void;

/** Complete (or reopen) a task, with the undo toast and the sound cue in one place. */
export function completeWithUndo(task: Task, setState: SetState, say: Say): void {
  const completing = task.state !== "done";
  setState(
    { id: task.id, state: completing ? "done" : "open" },
    {
      onSuccess: () => {
        if (!completing) {
          say("Reopened");
          return;
        }
        play("done");
        say(`Done · ${task.title}`, { label: "Undo", onClick: () => setState({ id: task.id, state: "open" }) }, 6000);
      },
    },
  );
}
