export const brandSymbolUrl = "/blandskron-symbol.png";

export function Brand({ className = "" }: { className?: string }) {
  return (
    <div className={`brand ${className}`.trim()}>
      <img
        src="/blandskron-wordmark.png"
        alt="Blandskron"
        width="2048"
        height="424"
      />
    </div>
  );
}
