import { useLocation } from "react-router-dom";
import { useFinishBoot, useHeaderMeta } from "@/shell/ShellState";
import { Screen } from "./Screen";
import { ChatThread } from "./chat/ChatThread";

export function Chat() {
  const location = useLocation();
  const state = location.state as { ask?: string } | null;
  useFinishBoot();
  useHeaderMeta("all context");
  return (
    <Screen fill>
      <ChatThread scope="everything" initialAsk={state?.ask} />
    </Screen>
  );
}
