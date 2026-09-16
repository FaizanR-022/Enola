import { useNavigate } from "react-router-dom";
import { Button, Dot, Mono } from "@/ui";
import styles from "./HeldBanner.module.css";

/** The one thing on the dashboard that can interrupt: something is waiting on you. */
export function HeldBanner({ summary }: { summary: string }) {
  const navigate = useNavigate();
  return (
    <div className={styles["banner"]} role="status">
      <span className={styles["state"]}>
        <Dot tone="held" size={6} pulse />
        <Mono upper tone="held" bold>
          Held
        </Mono>
      </span>
      <span className={styles["summary"]}>{summary}</span>
      <Button variant="primary" size="sm" onClick={() => navigate("/approvals")}>
        Review
      </Button>
    </div>
  );
}
