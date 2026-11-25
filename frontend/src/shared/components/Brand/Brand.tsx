export const brandSymbolUrl = "/brand/krondocs-isotipo.svg";

export interface BrandProps {
  className?: string;
  variant?: "wordmark" | "compact" | "isotipo";
  showDescriptor?: boolean;
  showSignature?: boolean;
}

export function Brand({
  className = "",
  variant = "wordmark",
  showDescriptor = false,
  showSignature = false,
}: BrandProps) {
  if (variant === "isotipo") {
    return (
      <div className={`brand brand--isotipo ${className}`.trim()}>
        <img
          src={brandSymbolUrl}
          alt="KronDocs"
          width="36"
          height="36"
          className="brand-symbol-img"
        />
      </div>
    );
  }

  return (
    <div className={`brand brand--${variant} ${className}`.trim()}>
      <img
        src={brandSymbolUrl}
        alt=""
        aria-hidden="true"
        width={variant === "compact" ? "28" : "36"}
        height={variant === "compact" ? "28" : "36"}
        className="brand-symbol-img"
      />
      <div className="brand-wordmark-group">
        <span className="brand-wordmark">
          Kron<span className="brand-wordmark-accent">Docs</span>
        </span>
        {showDescriptor && (
          <span className="brand-descriptor">Document Intelligence</span>
        )}
        {showSignature && (
          <span className="brand-signature">Open Source · By BLANDSKRON</span>
        )}
      </div>
    </div>
  );
}
