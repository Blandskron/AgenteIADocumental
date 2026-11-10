import type { ButtonHTMLAttributes } from "react";
export function IconButton({
  children,
  className = "",
  type = "button",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type={type}
      className={`icon-button ${className}`.trim()}
      {...props}
    >
      {children}
    </button>
  );
}
