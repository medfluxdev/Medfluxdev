"use client";

import {
  createContext,
  useCallback,
  useContext,
  useRef,
  useState,
} from "react";
import type { ReactNode } from "react";
import { SignalIcon } from "./Signal";

export type ToastKind = "success" | "error" | "info";

interface ToastItem {
  id: number;
  kind: ToastKind;
  message: string;
}

type ToastPush = (message: string, kind?: ToastKind) => void;

const ToastContext = createContext<ToastPush>(() => {});

/**
 * Zeigt eine Benachrichtigung unten rechts an (UAT Defect E). Feedbacks
 * verschwinden nach ~5s; `role` meldet den Zustand via aria-live/status bzw.
 * alert für Fehler. Mehrere Meldungen stapeln sich.
 */
export function useToast(): ToastPush {
  return useContext(ToastContext);
}

export const TOAST_DURATION_MS = 5000;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const nextId = useRef(1);

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const push = useCallback<ToastPush>(
    (message, kind = "info") => {
      const id = nextId.current++;
      setToasts((prev) => [...prev.slice(-4), { id, kind, message }]);
      window.setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== id));
      }, TOAST_DURATION_MS);
    },
    []
  );

  return (
    <ToastContext.Provider value={push}>
      {children}
      <div
        className="toast-viewport"
        role="region"
        aria-live="polite"
        aria-label="Benachrichtigungen"
      >
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`toast toast--${t.kind}`}
            role={t.kind === "error" ? "alert" : "status"}
          >
            <SignalIcon tone={t.kind === "error" ? "critical" : t.kind === "success" ? "done" : "info"} className="toast-icon" />
            <span className="toast-msg">{t.message}</span>
            <button
              type="button"
              className="toast-close"
              onClick={() => dismiss(t.id)}
              aria-label="Benachrichtigung schließen"
            >
              ×
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}