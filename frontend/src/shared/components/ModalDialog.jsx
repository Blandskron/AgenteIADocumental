import { useEffect, useRef } from "react";

// Native top layer provides focus containment, background inertness and Escape.
export function ModalDialog({ onClose, children, onClick, ...props }) {
  const dialog = useRef(null), close = useRef(onClose);
  close.current = onClose;
  useEffect(() => {
    const element = dialog.current, previous = document.activeElement;
    element.showModal();
    return () => { element.close(); if (previous?.isConnected) previous.focus(); };
  }, []);
  return <dialog {...props} ref={dialog} onCancel={(event) => { event.preventDefault(); close.current?.(); }}
    onClick={(event) => {
      const bounds = event.currentTarget.getBoundingClientRect();
      if (event.target === event.currentTarget && (event.clientX < bounds.left || event.clientX > bounds.right
        || event.clientY < bounds.top || event.clientY > bounds.bottom)) close.current?.();
      else onClick?.(event);
    }}>{children}</dialog>;
}
