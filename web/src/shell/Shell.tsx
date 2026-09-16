import { Outlet, useLocation } from "react-router-dom";
import { cx } from "@/lib/cx";
import { ChatRail } from "./ChatRail";
import { CommandPalette } from "./CommandPalette";
import { Header } from "./Header";
import { Nav } from "./Nav";
import { PhoneTabs } from "./PhoneTabs";
import { ShellStateProvider, useShell } from "./ShellState";
import { Splash } from "./Splash";
import { Toast } from "./Toast";
import { screenForPath } from "./screens";
import styles from "./Shell.module.css";

function ShellFrame() {
  const { railOpen, bootDone } = useShell();
  const location = useLocation();
  const screen = screenForPath(location.pathname);

  return (
    <div className={styles["root"]} data-screen={screen.id}>
      {!bootDone && <Splash />}
      <Nav current={screen.id} />
      <div className={styles["main"]}>
        <Header screen={screen} />
        <div className={cx(styles["stage"], railOpen && styles["withRail"])}>
          <main className={styles["content"]} id="content">
            <Outlet />
          </main>
          {railOpen && <ChatRail screen={screen} />}
        </div>
      </div>
      <PhoneTabs current={screen.id} />
      <CommandPalette />
      <Toast />
    </div>
  );
}

/** The persistent shell. Screens mount inside it via the router's Outlet. */
export function Shell() {
  return (
    <ShellStateProvider>
      <ShellFrame />
    </ShellStateProvider>
  );
}
