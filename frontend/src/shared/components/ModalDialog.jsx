import { useEffect, useRef } from "react";
import "./ModalDialog.css";

// Native top layer provides focus containment, background inertness and Escape.
export function ModalDialog({ onClose, children, onClick, ...props }) {
  const dialog = useRef(null), close = useRef(onClose);
  const restore = useRef(document.activeElement);
  close.current = onClose;
  useEffect(() => {
    const element = dialog.current, previous = restore.current;
    element.showModal();
    return () => { element.close(); if (previous?.isConnected) previous.focus(); };
  }, []);
  return <dialog {...props} ref={dialog} onCancel={(event) => { event.preventDefault(); close.current?.(); }}
    onKeyDown={(event) => {
      if (event.key !== "Tab") return;
      const items = [...event.currentTarget.querySelectorAll('button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])')]
        .filter((element) => element.getClientRects().length);
      const first = items[0], last = items.at(-1);
      if (!first) { event.preventDefault(); return; }
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }}
    onClick={(event) => {
      const bounds = event.currentTarget.getBoundingClientRect();
      if (event.target === event.currentTarget && (event.clientX < bounds.left || event.clientX > bounds.right
        || event.clientY < bounds.top || event.clientY > bounds.bottom)) close.current?.();
      else onClick?.(event);
    }}>{children}</dialog>;
}
