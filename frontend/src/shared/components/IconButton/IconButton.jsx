export function IconButton({ children, className = "", ...props }) {
  return (
    <button className={`icon-button ${className}`.trim()} {...props}>
      {children}
    </button>
  );
}
