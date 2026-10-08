import { useLayoutEffect, useRef, useState, type KeyboardEvent } from "react";
import type { Participant } from "../api/types";
import { Avatar } from "./Avatar";

const MAX_MENTION_SUGGESTIONS = 6;
// The "@partial-name" being typed right before the cursor.
const MENTION_IN_PROGRESS = /(?:^|\s)@([^\s@]*)$/;

interface ComposerProps {
  placeholder: string;
  participants: Participant[];
  onSend: (body: string) => Promise<void>;
}

interface Selection {
  start: number;
  end: number;
}

/** A Markdown text box with a formatting toolbar and @mention suggestions. */
export function Composer({ placeholder, participants, onSend }: ComposerProps) {
  const textAreaRef = useRef<HTMLTextAreaElement>(null);
  const [text, setText] = useState("");
  const [pendingSelection, setPendingSelection] = useState<Selection | null>(null);
  const [mentionQuery, setMentionQuery] = useState<string | null>(null);
  const [highlightedSuggestion, setHighlightedSuggestion] = useState(0);
  const [sending, setSending] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  // Grow the box with its content (CSS caps the height), and restore the cursor after edits.
  useLayoutEffect(() => {
    const textArea = textAreaRef.current;
    if (!textArea) return;
    textArea.style.height = "auto";
    textArea.style.height = `${textArea.scrollHeight}px`;
    if (pendingSelection) {
      textArea.focus();
      textArea.setSelectionRange(pendingSelection.start, pendingSelection.end);
      setPendingSelection(null);
    }
  }, [text, pendingSelection]);

  const suggestions =
    mentionQuery === null
      ? []
      : participants
          .filter((participant) => participant.displayName.toLowerCase().includes(mentionQuery.toLowerCase()))
          .slice(0, MAX_MENTION_SUGGESTIONS);

  const updateMentionQuery = (newText: string, cursor: number) => {
    const match = MENTION_IN_PROGRESS.exec(newText.slice(0, cursor));
    setMentionQuery(match ? match[1] : null);
    setHighlightedSuggestion(0);
  };

  const replaceSelection = (buildReplacement: (selected: string) => { text: string; select: Selection }) => {
    const textArea = textAreaRef.current;
    if (!textArea) return;
    const { selectionStart, selectionEnd } = textArea;
    const replacement = buildReplacement(text.slice(selectionStart, selectionEnd));
    setText(text.slice(0, selectionStart) + replacement.text + text.slice(selectionEnd));
    setPendingSelection({
      start: selectionStart + replacement.select.start,
      end: selectionStart + replacement.select.end,
    });
  };

  const wrapSelection = (before: string, after = before) =>
    replaceSelection((selected) => ({
      text: before + selected + after,
      select: { start: before.length, end: before.length + selected.length },
    }));

  const prefixLines = (prefixForLine: (lineIndex: number) => string) =>
    replaceSelection((selected) => {
      const prefixed = (selected || "")
        .split("\n")
        .map((line, index) => prefixForLine(index) + line)
        .join("\n");
      return { text: prefixed, select: { start: prefixed.length, end: prefixed.length } };
    });

  const insertLink = () =>
    replaceSelection((selected) => {
      const linkText = `[${selected}](https://)`;
      const urlStart = selected.length + 3;
      return { text: linkText, select: { start: urlStart, end: urlStart + "https://".length } };
    });

  const insertMention = (participant: Participant) => {
    const textArea = textAreaRef.current;
    if (!textArea) return;
    const cursor = textArea.selectionStart;
    const beforeCursor = text.slice(0, cursor).replace(/@[^\s@]*$/, "");
    // Use the id when two participants share the name, so the right one gets tagged.
    const nameIsShared =
      participants.filter((other) => other.displayName.toLowerCase() === participant.displayName.toLowerCase())
        .length > 1;
    const mention = `@${nameIsShared ? participant.id : participant.displayName} `;
    setText(beforeCursor + mention + text.slice(cursor));
    const newCursor = beforeCursor.length + mention.length;
    setPendingSelection({ start: newCursor, end: newCursor });
    setMentionQuery(null);
  };

  const send = async () => {
    const body = text.trim();
    if (!body || sending) return;
    setSending(true);
    setErrorMessage("");
    try {
      await onSend(body);
      setText("");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Could not send the message.");
    } finally {
      setSending(false);
      textAreaRef.current?.focus();
    }
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (suggestions.length > 0) {
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        event.preventDefault();
        const step = event.key === "ArrowDown" ? 1 : -1;
        setHighlightedSuggestion((current) => (current + step + suggestions.length) % suggestions.length);
        return;
      }
      if (event.key === "Enter" || event.key === "Tab") {
        event.preventDefault();
        insertMention(suggestions[highlightedSuggestion]);
        return;
      }
      if (event.key === "Escape") {
        setMentionQuery(null);
        return;
      }
    }
    // Enter sends; Shift+Enter starts a new line.
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      void send();
    }
  };

  const toolbarButtons = [
    { label: "Bold", symbol: "B", action: () => wrapSelection("**") },
    { label: "Italic", symbol: "I", action: () => wrapSelection("_") },
    { label: "Strikethrough", symbol: "S", action: () => wrapSelection("~~") },
    { label: "Link", symbol: "🔗", action: insertLink },
    { label: "Numbered list", symbol: "1.", action: () => prefixLines((index) => `${index + 1}. `) },
    { label: "Bulleted list", symbol: "•", action: () => prefixLines(() => "- ") },
    { label: "Quote", symbol: "❝", action: () => prefixLines(() => "> ") },
    { label: "Code", symbol: "</>", action: () => wrapSelection("`") },
    { label: "Code block", symbol: "{ }", action: () => wrapSelection("```\n", "\n```") },
  ];

  return (
    <div className="composer">
      {suggestions.length > 0 && (
        <ul className="mention-suggestions" role="listbox">
          {suggestions.map((participant, index) => (
            <li
              key={participant.id}
              role="option"
              aria-selected={index === highlightedSuggestion}
              className={`mention-suggestions__item ${index === highlightedSuggestion ? "is-highlighted" : ""}`}
              onMouseDown={(event) => {
                event.preventDefault(); // keep focus in the text box
                insertMention(participant);
              }}
            >
              <Avatar name={participant.displayName} kind={participant.kind} icon={participant.icon} size="small" />
              <span>{participant.displayName}</span>
              <span className="muted">{participant.id}</span>
            </li>
          ))}
        </ul>
      )}
      <textarea
        ref={textAreaRef}
        className="composer__input"
        rows={1}
        value={text}
        placeholder={placeholder}
        onChange={(event) => {
          setText(event.target.value);
          updateMentionQuery(event.target.value, event.target.selectionStart);
        }}
        onKeyDown={handleKeyDown}
        onBlur={() => setMentionQuery(null)}
      />
      <div className="composer__toolbar">
        {toolbarButtons.map((button) => (
          <button
            key={button.label}
            type="button"
            className={`icon-button composer__format composer__format--${button.label.toLowerCase().replace(" ", "-")}`}
            title={button.label}
            aria-label={button.label}
            onMouseDown={(event) => event.preventDefault()} // keep the text selection
            onClick={button.action}
          >
            {button.symbol}
          </button>
        ))}
        <button
          type="button"
          className="composer__send"
          aria-label="Send"
          title="Send (Enter)"
          disabled={!text.trim() || sending}
          onClick={() => void send()}
        >
          ↑
        </button>
      </div>
      {errorMessage && (
        <p className="form-error composer__error" role="alert">
          {errorMessage}
        </p>
      )}
    </div>
  );
}
