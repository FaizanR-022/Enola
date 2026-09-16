import { forwardRef, useId, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from "react";
import { cx } from "@/lib/cx";
import { Mono } from "./Mono";
import styles from "./Field.module.css";

export interface FieldProps {
  label: ReactNode;
  hint?: ReactNode | undefined;
  error?: ReactNode | undefined;
  /** Render prop so the control gets the generated id for its label. */
  children: (id: string) => ReactNode;
  className?: string | undefined;
}

/** Label + control + hint/error. The control is whatever you pass in. */
export function Field({ label, hint, error, children, className }: FieldProps) {
  const id = useId();
  return (
    <div className={cx(styles["field"], className)}>
      <label htmlFor={id} className={styles["label"]}>
        <Mono upper>{label}</Mono>
      </label>
      {children(id)}
      {error ? <div className={styles["error"]}>{error}</div> : hint ? <div className={styles["hint"]}>{hint}</div> : null}
    </div>
  );
}

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  mono?: boolean | undefined;
  bare?: boolean | undefined;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input({ mono = false, bare = false, className, ...rest }, ref) {
  return <input ref={ref} className={cx(styles["control"], styles["input"], mono && styles["mono"], bare && styles["bare"], className)} {...rest} />;
});

export interface TextAreaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  bare?: boolean | undefined;
}

export const TextArea = forwardRef<HTMLTextAreaElement, TextAreaProps>(function TextArea({ bare = false, className, ...rest }, ref) {
  return <textarea ref={ref} className={cx(styles["control"], styles["textarea"], bare && styles["bare"], className)} {...rest} />;
});

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(function Select({ className, ...rest }, ref) {
  return <select ref={ref} className={cx(styles["control"], styles["select"], className)} {...rest} />;
});
