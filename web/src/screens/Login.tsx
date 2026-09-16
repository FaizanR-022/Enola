import { useState, type FormEvent } from "react";
import { errorMessage } from "@/lib/api";
import { useLogin } from "@/lib/auth";
import { useTheme } from "@/theme/theme";
import { Button, Field, Input, Mono } from "@/ui";
import { Mark } from "@/shell/Wordmark";
import styles from "./Login.module.css";

export function Login() {
  const [password, setPassword] = useState("");
  const login = useLogin();
  const { theme, toggle } = useTheme();

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (password) login.mutate(password);
  };

  return (
    <div className={styles["page"]}>
      <form className={styles["card"]} onSubmit={submit}>
        <Mark size="lg" />
        <div className={styles["word"]}>enola</div>
        <p className={styles["line"]}>Personal agent. One user, one machine.</p>
        <Field label="Password" error={login.isError ? errorMessage(login.error) : undefined}>
          {(id) => <Input id={id} type="password" autoFocus autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />}
        </Field>
        <Button type="submit" variant="primary" busy={login.isPending} disabled={!password}>
          Sign in
        </Button>
        <button type="button" className={styles["theme"]} onClick={toggle}>
          <Mono>{theme === "dark" ? "light theme" : "dark theme"}</Mono>
        </button>
      </form>
    </div>
  );
}
