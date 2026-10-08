import { useEffect, useRef, useState, type ReactNode } from "react";

interface DialogProps {
  title: string;
  onClose: () => void;
  children: ReactNode;
  wide?: boolean;
}

/** A modal built on the browser's own <dialog>, which handles focus and the Escape key. */
export function Dialog({ title, onClose, children, wide }: DialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    dialog?.showModal();
    return () => dialog?.close();
  }, []);

  return (
    <dialog
      ref={dialogRef}
      className={`dialog ${wide ? "dialog--wide" : ""}`}
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      onClick={(event) => {
        // A click on the dimmed backdrop lands on the <dialog> element itself.
        if (event.target === dialogRef.current) onClose();
      }}
    >
      <h2 className="dialog__title">{title}</h2>
      {children}
    </dialog>
  );
}

interface TextInputDialogProps {
  title: string;
  label: string;
  placeholder?: string;
  initialValue?: string;
  submitLabel: string;
  maxLength?: number;
  onSubmit: (value: string) => Promise<void>;
  onClose: () => void;
}

/** A dialog that asks for one line of text, like a name. Shows the server's error if saving fails. */
export function TextInputDialog({
  title,
  label,
  placeholder,
  initialValue = "",
  submitLabel,
  maxLength = 40,
  onSubmit,
  onClose,
}: TextInputDialogProps) {
  const [value, setValue] = useState(initialValue);
  const [errorMessage, setErrorMessage] = useState("");
  const [saving, setSaving] = useState(false);

  return (
    <Dialog title={title} onClose={onClose}>
      <form
        className="dialog__form"
        onSubmit={async (event) => {
          event.preventDefault();
          if (!value.trim()) return;
          setSaving(true);
          try {
            await onSubmit(value.trim());
            onClose();
          } catch (error) {
            setErrorMessage(error instanceof Error ? error.message : "Something went wrong.");
            setSaving(false);
          }
        }}
      >
        <label className="field">
          <span className="field__label">{label}</span>
          <input
            className="input"
            value={value}
            onChange={(event) => setValue(event.target.value)}
            placeholder={placeholder}
            maxLength={maxLength}
            autoFocus
            autoComplete="off"
          />
        </label>
        {errorMessage && (
          <p className="form-error" role="alert">
            {errorMessage}
          </p>
        )}
        <div className="dialog__actions">
          <button type="button" className="button" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="button button--primary" disabled={saving || !value.trim()}>
            {submitLabel}
          </button>
        </div>
      </form>
    </Dialog>
  );
}

interface ConfirmDialogProps {
  title: string;
  explanation: string;
  confirmLabel: string;
  onConfirm: () => Promise<void>;
  onClose: () => void;
}

export function ConfirmDialog({ title, explanation, confirmLabel, onConfirm, onClose }: ConfirmDialogProps) {
  return (
    <Dialog title={title} onClose={onClose}>
      <p className="dialog__text">{explanation}</p>
      <div className="dialog__actions">
        <button type="button" className="button" onClick={onClose}>
          Cancel
        </button>
        <button
          type="button"
          className="button button--danger"
          onClick={async () => {
            await onConfirm();
            onClose();
          }}
        >
          {confirmLabel}
        </button>
      </div>
    </Dialog>
  );
}
