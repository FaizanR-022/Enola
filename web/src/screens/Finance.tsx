/** Finance. Manual entry only, PKR, no bank connections ever.
 *
 *  Five entry paths, all one tap from the header: log expense (the common case),
 *  log income, transfer, split, settle up. Views: the ledger, spend by category, and
 *  who owes whom with a settle action. Balances come from the server, derived. */

import { useMemo, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { usePeople } from "@/data";
import { currentMonth, monthLabel, shiftMonth, useAccounts, useCategories, useFinanceMutations, useFinanceSummary, useSettlements, useTransactions, type Account, type Category, type OwedRow, type Transaction } from "@/data/finance";
import { errorMessage } from "@/lib/api";
import { cx } from "@/lib/cx";
import { dateLabel, fromDatetimeLocal, pkr, signedPkr, toDatetimeLocal } from "@/lib/format";
import { play } from "@/lib/sound";
import { useFinishBoot, useHeaderMeta, useShell } from "@/shell/ShellState";
import { Avatar, Badge, Button, Card, CardRow, EmptyState, Field, Input, Mono, QueryState, ScreenHeader, Select, Sheet, TextArea } from "@/ui";
import { Grid, Screen, Stack } from "./Screen";
import styles from "./Finance.module.css";

type Entry = "expense" | "income" | "transfer" | "split" | "settle";

const ENTRY_LABEL: Record<Entry, string> = { expense: "Log expense", income: "Log income", transfer: "Transfer", split: "Split", settle: "Settle up" };

export function Finance() {
  const [month, setMonth] = useState(currentMonth);
  const [entry, setEntry] = useState<Entry | null>(null);
  const [settleWith, setSettleWith] = useState<OwedRow | null>(null);
  const [addingAccount, setAddingAccount] = useState(false);
  const accounts = useAccounts();
  const transactions = useTransactions(month);
  const summary = useFinanceSummary(month);
  const settlements = useSettlements();
  const mutations = useFinanceMutations();
  const { say } = useShell();
  const navigate = useNavigate();
  useFinishBoot();
  useHeaderMeta(`${monthLabel(month)} · PKR`);

  const openSettle = (row: OwedRow | null) => {
    setSettleWith(row);
    setEntry("settle");
  };

  return (
    <Screen>
      <ScreenHeader
        title="Finance"
        subtitle="Manual entry only. No accounts linked, ever."
        actions={
          <div className={styles["entries"]}>
            <Button size="sm" variant="primary" onClick={() => setEntry("expense")}>
              Log expense
            </Button>
            <Button size="sm" onClick={() => setEntry("income")}>
              Income
            </Button>
            <Button size="sm" onClick={() => setEntry("transfer")}>
              Transfer
            </Button>
            <Button size="sm" onClick={() => setEntry("split")}>
              Split
            </Button>
            <Button size="sm" onClick={() => openSettle(null)}>
              Settle up
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setAddingAccount(true)}>
              Add account
            </Button>
          </div>
        }
      />

      <QueryState status={accounts.status} error={accounts.error} data={accounts.data} onRetry={() => void accounts.refetch()} rows={2}>
        {(page) =>
          page.items.length === 0 ? (
            <EmptyState
              title="No accounts yet."
              hint="Add the places your money lives: a bank account, a wallet, cash."
              action={
                <Button size="sm" onClick={() => setAddingAccount(true)}>
                  Add account
                </Button>
              }
            />
          ) : (
            <Grid min="178px">
              {page.items.map((a) => (
                <Card key={a.id}>
                  <Mono upper>{a.name}</Mono>
                  <span className={styles["balance"]}>{pkr(a.balance, false)}</span>
                  <span className={cx(styles["delta"], Number(a.month_delta) > 0 && styles["deltaUp"])}>{signedPkr(a.month_delta)} this month</span>
                </Card>
              ))}
            </Grid>
          )
        }
      </QueryState>

      <div className={styles["monthRow"]}>
        <Button size="sm" variant="ghost" onClick={() => setMonth((m) => shiftMonth(m, -1))} aria-label="Previous month">
          ←
        </Button>
        <span className={styles["monthLabel"]}>{monthLabel(month)}</span>
        <Button size="sm" variant="ghost" onClick={() => setMonth((m) => shiftMonth(m, 1))} disabled={month >= currentMonth()} aria-label="Next month">
          →
        </Button>
      </div>

      <Grid min="310px">
        <Card title="Ledger" meta={<Mono>{transactions.data ? `${transactions.data.total} entries` : ""}</Mono>} flush>
          <QueryState status={transactions.status} error={transactions.error} data={transactions.data} onRetry={() => void transactions.refetch()} rows={6}>
            {(page) =>
              page.items.length === 0 ? (
                <EmptyState inline title={`Nothing logged in ${monthLabel(month)}.`} hint="Log an expense from the header, or tell Enola “spent 450 on fuel”." />
              ) : (
                page.items.map((t) => <LedgerRow key={t.id} tx={t} onDelete={() => mutations.removeTransaction.mutate(t.id, { onSuccess: () => say("Removed") })} />)
              )
            }
          </QueryState>
        </Card>

        <Stack>
          <QueryState status={summary.status} error={summary.error} data={summary.data} onRetry={() => void summary.refetch()} rows={4}>
            {(s) => (
              <>
                <Card title="Who owes whom" meta={<Mono tone={Number(s.net_owed) > 0 ? "ok" : Number(s.net_owed) < 0 ? "danger" : "muted"}>net {signedPkr(s.net_owed)}</Mono>} flush note="Settling only records it here. Enola never moves money.">
                  {s.owed.length === 0 ? (
                    <EmptyState inline title="Nobody owes anybody." hint="Splits and settlements land here." />
                  ) : (
                    s.owed.map((o) => (
                      <CardRow key={o.person_id} interactive onClick={() => navigate(`/people/${o.person_id}`)}>
                        <Avatar name={o.person_name} size="sm" />
                        <span className={styles["oweMain"]}>
                          <span className={styles["oweName"]}>{o.person_name}</span>
                          <span className={styles["oweDetail"]}>{o.detail}</span>
                        </span>
                        <Mono size={12} tone={Number(o.amount) > 0 ? "ok" : "danger"}>
                          {signedPkr(o.amount)}
                        </Mono>
                        <Button
                          variant="link"
                          onClick={(event) => {
                            event.stopPropagation();
                            openSettle(o);
                          }}
                        >
                          Settle
                        </Button>
                      </CardRow>
                    ))
                  )}
                </Card>
                <Card title={`${monthLabel(month).split(" ")[0]} spend`} meta={<Mono size={11} tone="soft">{pkr(s.total_spend)}</Mono>}>
                  {s.spend.length === 0 ? (
                    <EmptyState inline title="No spending this month." />
                  ) : (
                    <>
                      <div className={styles["bars"]}>
                        {s.spend.map((row) => (
                          <span key={row.category_name} className={styles["bar"]} style={{ ["--w" as string]: `${row.pct}%`, ["--c" as string]: `var(--${row.color_token})` }} />
                        ))}
                      </div>
                      {s.spend.map((row) => (
                        <div key={row.category_name} className={styles["spendRow"]}>
                          <span className={styles["swatch"]} style={{ ["--c" as string]: `var(--${row.color_token})` }} />
                          <span className={styles["spendName"]}>{row.category_name}</span>
                          <Mono size={12} tone="text">
                            {pkr(row.amount, false)}
                          </Mono>
                          <Mono className={styles["pct"]}>{row.pct}%</Mono>
                        </div>
                      ))}
                    </>
                  )}
                  {Number(s.total_income) > 0 && <div className={styles["spendNote"]}>Income this month: {pkr(s.total_income)}.</div>}
                </Card>
              </>
            )}
          </QueryState>
          <Card title="Settlements" flush>
            <QueryState status={settlements.status} error={settlements.error} data={settlements.data} rows={2}>
              {(page) =>
                page.items.length === 0 ? (
                  <EmptyState inline title="No repayments recorded." />
                ) : (
                  page.items.slice(0, 8).map((st) => (
                    <CardRow key={st.id}>
                      <Mono className={styles["date"]}>{dateLabel(st.occurred_at)}</Mono>
                      <span className={styles["txMain"]}>
                        <span className={styles["txTitle"]}>
                          {st.direction === "they_paid_me" ? `${st.person_name} paid you` : `You paid ${st.person_name}`}
                        </span>
                        {st.note && <span className={styles["oweDetail"]}>{st.note}</span>}
                      </span>
                      <Mono size={12} tone={st.direction === "they_paid_me" ? "ok" : "danger"}>
                        {pkr(st.amount, false)}
                      </Mono>
                    </CardRow>
                  ))
                )
              }
            </QueryState>
          </Card>
        </Stack>
      </Grid>

      {addingAccount && <AccountSheet onClose={() => setAddingAccount(false)} />}
      {entry && (
        <EntrySheet
          entry={entry}
          settleWith={settleWith}
          onClose={() => {
            setEntry(null);
            setSettleWith(null);
          }}
          onDone={(message) => {
            setEntry(null);
            setSettleWith(null);
            play("done");
            say(message);
          }}
        />
      )}
    </Screen>
  );
}

function LedgerRow({ tx, onDelete }: { tx: Transaction; onDelete: () => void }) {
  const isIn = tx.kind === "income";
  const isTransfer = tx.kind === "transfer";
  return (
    <CardRow>
      <Mono className={styles["date"]}>{dateLabel(tx.occurred_at)}</Mono>
      <span className={styles["txMain"]}>
        <span className={styles["txTitle"]}>{tx.title}</span>
        <span className={styles["txTags"]}>
          {tx.category_name && <Badge>{tx.category_name}</Badge>}
          {isTransfer && (
            <Mono>
              {tx.account_name} → {tx.to_account_name}
            </Mono>
          )}
          {!isTransfer && <Mono>{tx.account_name}</Mono>}
          {tx.splits.length > 0 && (
            <Mono tone="accent">
              split {tx.splits.length + 1} ways · {tx.paid_by_me ? "you paid" : "they paid"}
              {tx.splits.every((s) => s.settled) ? " · settled" : ""}
            </Mono>
          )}
        </span>
      </span>
      <Mono size={12} tone={isIn ? "ok" : isTransfer ? "soft" : "text"}>
        {isIn ? "+" : isTransfer ? "⇄ " : ""}
        {pkr(tx.amount, false)}
      </Mono>
      <button type="button" className={styles["remove"]} onClick={onDelete} aria-label={`Delete ${tx.title}`}>
        ✕
      </button>
    </CardRow>
  );
}

const ACCOUNT_KINDS = ["cash", "wallet", "bank"] as const;

/** Add a place money lives. This used to be a button that created one hardcoded "Cash"
 *  account, rendered only in the empty state — so after the first account there was no
 *  way to add a second. */
function AccountSheet({ onClose }: { onClose: () => void }) {
  const mutations = useFinanceMutations();
  const { say } = useShell();
  const [name, setName] = useState("");
  const [kind, setKind] = useState<(typeof ACCOUNT_KINDS)[number]>("cash");
  const [opening, setOpening] = useState("");
  const [error, setError] = useState<string | null>(null);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!name.trim()) return setError("Give the account a name.");
    const amount = opening.trim() === "" ? "0" : opening.trim();
    if (Number.isNaN(Number(amount))) return setError("The opening balance must be a number.");
    try {
      await mutations.createAccount.mutateAsync({ name: name.trim(), kind, opening_balance: amount, currency: "PKR" });
      say(`Added ${name.trim()}`);
      onClose();
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  return (
    <Sheet
      open
      onClose={onClose}
      title="Add an account"
      footer={
        <>
          <Button variant="primary" type="submit" form="account-form" busy={mutations.createAccount.isPending} disabled={!name.trim()}>
            Save
          </Button>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
        </>
      }
    >
      <form id="account-form" className={styles["form"]} onSubmit={(e) => void submit(e)}>
        <Field label="Name">{(id) => <Input id={id} value={name} onChange={(e) => setName(e.target.value)} placeholder="SadaPay" autoFocus />}</Field>
        <Field label="Kind">
          {(id) => (
            <Select id={id} value={kind} onChange={(e) => setKind(e.target.value as (typeof ACCOUNT_KINDS)[number])}>
              {ACCOUNT_KINDS.map((k) => (
                <option key={k} value={k}>
                  {k}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Opening balance · PKR" hint="What is in it today. Leave empty for zero — but then your balance goes negative as you spend.">
          {(id) => <Input id={id} mono inputMode="decimal" value={opening} onChange={(e) => setOpening(e.target.value)} placeholder="0" />}
        </Field>
        {error && <Mono tone="danger">{error}</Mono>}
      </form>
    </Sheet>
  );
}

function EntrySheet({ entry, settleWith, onClose, onDone }: { entry: Entry; settleWith: OwedRow | null; onClose: () => void; onDone: (message: string) => void }) {
  const accounts = useAccounts();
  const categories = useCategories();
  const people = usePeople({});
  const mutations = useFinanceMutations();
  const accountList: Account[] = accounts.data?.items ?? [];
  const categoryList: Category[] = categories.data?.items ?? [];
  const [amount, setAmount] = useState(settleWith ? String(Math.abs(Math.round(Number(settleWith.amount)))) : "");
  const [title, setTitle] = useState("");
  const [note, setNote] = useState("");
  const [when, setWhen] = useState(toDatetimeLocal(new Date().toISOString()));
  const [accountId, setAccountId] = useState<number | "">("");
  const [toAccountId, setToAccountId] = useState<number | "">("");
  const [categoryId, setCategoryId] = useState<number | "">("");
  const [newCategory, setNewCategory] = useState("");
  const [selectedPeople, setSelectedPeople] = useState<number[]>([]);
  const [personId, setPersonId] = useState<number | "">(settleWith?.person_id ?? "");
  const [direction, setDirection] = useState<"they_paid_me" | "i_paid_them">(settleWith && Number(settleWith.amount) < 0 ? "i_paid_them" : "they_paid_me");
  const [error, setError] = useState<string | null>(null);

  const account = accountId === "" ? accountList[0] : accountList.find((a) => a.id === accountId);
  const amountNumber = Number(amount);
  const preview = useMemo(() => {
    if (entry !== "split" || !amountNumber || selectedPeople.length === 0) return null;
    const n = selectedPeople.length + 1;
    const each = Math.round(amountNumber / n);
    return `${pkr(amountNumber)} split ${n} ways · ${pkr(each)} each. You paid, so ${n - 1} ${n - 1 === 1 ? "person owes" : "people owe"} you ${pkr(each)}.`;
  }, [entry, amountNumber, selectedPeople]);

  const busy = mutations.createTransaction.isPending || mutations.createSettlement.isPending || mutations.createCategory.isPending;

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    if (!amountNumber || amountNumber <= 0) return setError("Enter an amount.");
    const occurred_at = fromDatetimeLocal(when) ?? new Date().toISOString();
    try {
      if (entry === "settle") {
        if (personId === "") return setError("Pick a person.");
        const person = (people.data?.items ?? []).find((p) => p.id === personId);
        await mutations.createSettlement.mutateAsync({ person_id: personId, amount: String(amountNumber), direction, note, account_id: accountId === "" ? null : accountId, occurred_at, allocations: null });
        return onDone(`Recorded · ${direction === "they_paid_me" ? `${person?.name ?? "they"} paid you` : `you paid ${person?.name ?? "them"}`} ${pkr(amountNumber)}`);
      }
      if (!account) return setError("Add an account first.");
      let category_id: number | null = categoryId === "" ? null : categoryId;
      if ((entry === "expense" || entry === "split") && category_id === null && newCategory.trim()) {
        const created = await mutations.createCategory.mutateAsync({ name: newCategory.trim().toLowerCase(), color_token: "tx3" });
        category_id = created.id;
      }
      if (entry === "transfer") {
        if (toAccountId === "" || toAccountId === account.id) return setError("Pick a different destination account.");
        await mutations.createTransaction.mutateAsync({ account_id: account.id, to_account_id: toAccountId, kind: "transfer", amount: String(amountNumber), title: title || `Transfer to ${accountList.find((a) => a.id === toAccountId)?.name ?? ""}`, notes: note, occurred_at, paid_by_me: true, splits: [] });
        return onDone(`Transferred ${pkr(amountNumber)}`);
      }
      if (entry === "income") {
        if (!title.trim()) return setError("What was it for?");
        await mutations.createTransaction.mutateAsync({ account_id: account.id, kind: "income", amount: String(amountNumber), title: title.trim(), notes: note, occurred_at, paid_by_me: true, splits: [] });
        return onDone(`Logged income · ${pkr(amountNumber)} · ${account.name}`);
      }
      if (entry === "split" && selectedPeople.length === 0) return setError("Pick who to split with.");
      const categoryName = categoryList.find((c) => c.id === category_id)?.name ?? newCategory.trim().toLowerCase();
      await mutations.createTransaction.mutateAsync({
        account_id: account.id,
        category_id,
        kind: "expense",
        amount: String(amountNumber),
        title: title.trim() || categoryName || "expense",
        notes: note,
        occurred_at,
        paid_by_me: true,
        splits: entry === "split" ? selectedPeople.map((id) => ({ person_id: id, share_amount: null })) : [],
      });
      onDone(entry === "split" ? `Logged ${pkr(amountNumber)} split ${selectedPeople.length + 1} ways · written to ${selectedPeople.length} profiles` : `Logged: ${pkr(amountNumber)} · ${categoryName || "uncategorised"} · ${account.name}`);
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  const accountField = (value: number | "", onChange: (id: number | "") => void, id: string) => (
    <Select id={id} value={value === "" ? (accountList[0]?.id ?? "") : value} onChange={(e) => onChange(e.target.value === "" ? "" : Number(e.target.value))}>
      {accountList.map((a) => (
        <option key={a.id} value={a.id}>
          {a.name} · {pkr(a.balance, false)}
        </option>
      ))}
    </Select>
  );

  return (
    <Sheet
      open
      onClose={onClose}
      title={ENTRY_LABEL[entry]}
      footer={
        <>
          <Button variant="primary" type="submit" form="finance-entry" busy={busy}>
            Save
          </Button>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          {entry === "settle" && <span className={styles["sheetNote"]}>Records it here. No money moves.</span>}
          {entry === "split" && <span className={styles["sheetNote"]}>Writes to Finance and to each person's profile.</span>}
        </>
      }
    >
      <form id="finance-entry" className={styles["form"]} onSubmit={(e) => void submit(e)}>
        <div className={styles["sheetRow"]}>
          <Field label="Amount · PKR">{(id) => <Input id={id} mono inputMode="numeric" value={amount} onChange={(e) => setAmount(e.target.value)} autoFocus />}</Field>
          <Field label="When">{(id) => <Input id={id} type="datetime-local" mono value={when} onChange={(e) => setWhen(e.target.value)} />}</Field>
        </div>

        {entry === "settle" ? (
          <>
            <Field label="With">
              {(id) => (
                <Select id={id} value={personId} onChange={(e) => setPersonId(e.target.value === "" ? "" : Number(e.target.value))}>
                  <option value="">Pick a person</option>
                  {(people.data?.items ?? []).map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                      {p.balance !== 0 ? ` · ${signedPkr(p.balance)}` : ""}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label="Direction">
              {(id) => (
                <Select id={id} value={direction} onChange={(e) => setDirection(e.target.value as "they_paid_me" | "i_paid_them")}>
                  <option value="they_paid_me">They paid me</option>
                  <option value="i_paid_them">I paid them</option>
                </Select>
              )}
            </Field>
            <Field label="Into / from account" hint="Optional. Updates that account's balance.">
              {(id) => (
                <Select id={id} value={accountId} onChange={(e) => setAccountId(e.target.value === "" ? "" : Number(e.target.value))}>
                  <option value="">Not tracked</option>
                  {accountList.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.name}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            {settleWith && <p className={styles["hint"]}>Outstanding with {settleWith.person_name}: {signedPkr(settleWith.amount)}. Partial amounts are fine.</p>}
          </>
        ) : (
          <>
            {entry !== "transfer" && <Field label="What for">{(id) => <Input id={id} value={title} onChange={(e) => setTitle(e.target.value)} placeholder={entry === "income" ? "Freelance — landing page" : "Carpool fuel — Shell Gulshan"} />}</Field>}
            <div className={styles["sheetRow"]}>
              <Field label={entry === "transfer" ? "From" : "Account"}>{(id) => accountField(accountId, setAccountId, id)}</Field>
              {entry === "transfer" && <Field label="To">{(id) => accountField(toAccountId, setToAccountId, id)}</Field>}
              {(entry === "expense" || entry === "split") && (
                <Field label="Category">
                  {(id) => (
                    <Select id={id} value={categoryId} onChange={(e) => setCategoryId(e.target.value === "" ? "" : Number(e.target.value))}>
                      <option value="">— new below —</option>
                      {categoryList.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.name}
                        </option>
                      ))}
                    </Select>
                  )}
                </Field>
              )}
            </div>
            {(entry === "expense" || entry === "split") && categoryId === "" && (
              <Field label="New category" hint="Reuse an existing one when you can; tags are for scanning, not taxonomy.">
                {(id) => <Input id={id} value={newCategory} onChange={(e) => setNewCategory(e.target.value)} placeholder="carpool" />}
              </Field>
            )}
            {entry === "split" && (
              <div>
                <Mono upper className={styles["sheetLabel"]}>
                  Split with · from your People catalogue
                </Mono>
                <div className={styles["chips"]}>
                  {(people.data?.items ?? []).map((p) => {
                    const on = selectedPeople.includes(p.id);
                    return (
                      <button key={p.id} type="button" className={cx(styles["chip"], on && styles["chipOn"])} onClick={() => setSelectedPeople((s) => (on ? s.filter((x) => x !== p.id) : [...s, p.id]))} aria-pressed={on}>
                        <Avatar name={p.name} size="sm" />
                        {p.name}
                      </button>
                    );
                  })}
                </div>
                {preview && (
                  <Card>
                    <Mono upper>Preview</Mono>
                    <span className={styles["preview"]}>{preview}</span>
                  </Card>
                )}
              </div>
            )}
          </>
        )}
        <Field label="Note">{(id) => <TextArea id={id} rows={2} value={note} onChange={(e) => setNote(e.target.value)} />}</Field>
        {error && <Mono tone="danger">{error}</Mono>}
      </form>
    </Sheet>
  );
}
