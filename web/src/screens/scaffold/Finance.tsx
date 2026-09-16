/** Finance scaffold. Manual entry only; no bank connections, ever.
 *
 *  TODO(wire): replace mock constants with
 *    - GET /api/accounts                       → ACCOUNTS
 *    - GET /api/transactions?month=YYYY-MM     → TRANSACTIONS
 *    - GET /api/finance/summary?month=         → FINANCE_SUMMARY (spend bars, who owes whom)
 *    - POST /api/transactions {splits:[{person_id}]} → the "Log an expense" sheet
 *    - POST /api/splits/{id}/settle            → Settle
 *    - GET /api/people                         → SPLIT_PEOPLE chips
 *  "Remind" drafts a message through the agent (POST /api/chat) and is Held before sending.
 */

import { useMemo, useState } from "react";
import { cx } from "@/lib/cx";
import { dateLabel, pkr, signedPkr } from "@/lib/format";
import { useFinishBoot, useHeaderMeta, useShell } from "@/shell/ShellState";
import { Avatar, Badge, Button, Card, CardRow, Field, Input, Mono, ScreenHeader, Sheet } from "@/ui";
import { Grid, Screen, Stack } from "../Screen";
import { ACCOUNTS, FINANCE_SUMMARY, SPLIT_PEOPLE, TRANSACTIONS } from "./mock";
import styles from "./Finance.module.css";

export function Finance() {
  const [splitOpen, setSplitOpen] = useState(false);
  const { say } = useShell();
  useFinishBoot();
  useHeaderMeta("September · PKR");

  return (
    <Screen>
      <ScreenHeader
        title="Finance"
        subtitle="September · manual entry only, no accounts linked"
        actions={
          <Button size="sm" onClick={() => setSplitOpen(true)}>
            Log an expense
          </Button>
        }
      />
      <Grid min="178px">
        {ACCOUNTS.map((a) => (
          <Card key={a.id}>
            <Mono upper>{a.name}</Mono>
            <span className={styles["balance"]}>{pkr(a.balance, false)}</span>
            <span className={cx(styles["delta"], Number(a.month_delta) > 0 && styles["deltaUp"])}>{signedPkr(a.month_delta)} this month</span>
          </Card>
        ))}
      </Grid>
      <Grid min="310px">
        <Card title="Transactions" meta={<Mono>1–{new Date().getDate()} Sep</Mono>} flush>
          {TRANSACTIONS.map((t) => (
            <CardRow key={t.id}>
              <Mono className={styles["date"]}>{dateLabel(t.occurred_at)}</Mono>
              <span className={styles["txMain"]}>
                <span className={styles["txTitle"]}>{t.title}</span>
                <span className={styles["txTags"]}>
                  {t.category_name && <Badge>{t.category_name}</Badge>}
                  {t.splits.length > 0 && <Mono tone="accent">split {t.splits.length + 1} ways · you paid</Mono>}
                  {t.kind === "settlement" && <Mono tone="ok">settle up</Mono>}
                </span>
              </span>
              <Mono size={12} tone={t.kind === "settlement" || t.kind === "income" ? "ok" : "text"}>
                {t.kind === "settlement" || t.kind === "income" ? "−" : ""}
                {pkr(t.amount, false)}
              </Mono>
            </CardRow>
          ))}
        </Card>
        <Stack>
          <Card title="Who owes whom" meta={<Mono tone="ok">net +{pkr(FINANCE_SUMMARY.net_owed, false)}</Mono>} flush note="Settling only records it here. Enola never moves money.">
            {FINANCE_SUMMARY.owed.map((o) => (
              <CardRow key={o.person_id}>
                <Avatar name={o.person_name} size="sm" />
                <span className={styles["oweMain"]}>
                  <span className={styles["oweName"]}>{o.person_name}</span>
                  <span className={styles["oweDetail"]}>{o.detail}</span>
                </span>
                <Mono size={12} tone={Number(o.amount) > 0 ? "ok" : "danger"}>
                  {signedPkr(o.amount)}
                </Mono>
                <Button variant="link" onClick={() => say(Number(o.amount) > 0 ? "Reminder drafted · Held in Approvals, not sent" : `Marked settled · you paid ${o.person_name.split(" ")[0]}`)}>
                  {Number(o.amount) > 0 ? "Remind" : "Settle"}
                </Button>
              </CardRow>
            ))}
          </Card>
          <Card title="September spend" meta={<Mono size={11} tone="soft">{pkr(FINANCE_SUMMARY.total_spend)}</Mono>}>
            <div className={styles["bars"]}>
              {FINANCE_SUMMARY.spend.map((s) => (
                <span key={s.category_name} className={styles["bar"]} style={{ ["--w" as string]: `${s.pct}%`, ["--c" as string]: `var(--${s.color_token})` }} />
              ))}
            </div>
            {FINANCE_SUMMARY.spend.map((s) => (
              <div key={s.category_name} className={styles["spendRow"]}>
                <span className={styles["swatch"]} style={{ ["--c" as string]: `var(--${s.color_token})` }} />
                <span className={styles["spendName"]}>{s.category_name}</span>
                <Mono size={12} tone="text">
                  {pkr(s.amount, false)}
                </Mono>
                <Mono className={styles["pct"]}>{s.pct}%</Mono>
              </div>
            ))}
            <div className={styles["spendNote"]}>Carpool is up 34% on August. Two unpaid splits are sitting in it.</div>
          </Card>
        </Stack>
      </Grid>
      <LogExpenseSheet open={splitOpen} onClose={() => setSplitOpen(false)} />
    </Screen>
  );
}

function LogExpenseSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [amount, setAmount] = useState("2400");
  const [what, setWhat] = useState("Carpool fuel — Shell Gulshan");
  const [selected, setSelected] = useState<number[]>([6, 3]);
  const { say } = useShell();
  const preview = useMemo(() => {
    const n = selected.length + 1;
    const amt = Number(amount) || 0;
    const each = Math.round(amt / n);
    return `${pkr(amt)} split ${n} ways · ${pkr(each)} each. You paid, so ${n - 1} people owe you ${pkr(each)}. It will show on their profiles under shared money.`;
  }, [amount, selected]);
  return (
    <Sheet
      open={open}
      onClose={onClose}
      title="Log an expense"
      footer={
        <>
          <Button
            variant="primary"
            onClick={() => {
              say(`Logged · split ${selected.length + 1} ways · written to ${selected.length} profiles`);
              onClose();
            }}
          >
            Save
          </Button>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <span className={styles["sheetNote"]}>Writes to Finance and to each person's profile.</span>
        </>
      }
    >
      <div className={styles["sheetRow"]}>
        <Field label="Amount · PKR">{(id) => <Input id={id} mono value={amount} onChange={(e) => setAmount(e.target.value)} inputMode="numeric" />}</Field>
        <Field label="What for">{(id) => <Input id={id} value={what} onChange={(e) => setWhat(e.target.value)} />}</Field>
      </div>
      <div>
        <Mono upper className={styles["sheetLabel"]}>
          Split with · from your People catalogue
        </Mono>
        <div className={styles["chips"]}>
          {SPLIT_PEOPLE.map((p) => {
            const on = selected.includes(p.id);
            return (
              <button key={p.id} type="button" className={cx(styles["chip"], on && styles["chipOn"])} onClick={() => setSelected((s) => (on ? s.filter((x) => x !== p.id) : [...s, p.id]))} aria-pressed={on}>
                <Avatar name={p.name} size="sm" />
                {p.name}
              </button>
            );
          })}
        </div>
      </div>
      <Card>
        <Mono upper>Preview</Mono>
        <span className={styles["preview"]}>{preview}</span>
      </Card>
    </Sheet>
  );
}
