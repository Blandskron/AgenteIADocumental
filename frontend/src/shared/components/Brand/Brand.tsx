const logoUrl = "/blandskron.svg";

export function Brand({ subtitle = "", className = "" }) {
  const isFull = className.includes("login-brand");

  if (isFull) {
    return (
      <div
        className={`brand ${className}`.trim()}
        style={{ flexDirection: "column", gap: "12px", alignItems: "center" }}
      >
        <img
          src={logoUrl}
          alt="Blandskron Documental"
          style={{ height: "60px", objectFit: "contain", maxWidth: "100%" }}
        />
        {subtitle && (
          <p style={{ fontSize: "14px", color: "var(--muted)", margin: 0 }}>
            {subtitle}
          </p>
        )}
      </div>
    );
  }

  return (
    <div className={`brand ${className}`.trim()}>
      <div
        className="brand-mark"
        style={{
          overflow: "hidden",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "transparent",
          border: "none",
        }}
      >
        <img
          src={logoUrl}
          alt="Blandskron Documental"
          style={{ width: "32px", height: "32px", objectFit: "contain" }}
        />
      </div>
      <div>
        <h1 style={{ margin: 0, fontSize: "17px", fontWeight: 850 }}>
          Blandskron Documental
        </h1>
        {subtitle && (
          <p
            style={{
              margin: "2px 0 0 0",
              fontSize: "12px",
              color: "var(--muted)",
            }}
          >
            {subtitle}
          </p>
        )}
      </div>
    </div>
  );
}
