import { LoaderCircle } from "lucide-react";
import { Button } from "./Button/Button.tsx";
export function PageState({
  title,
  description,
  retry,
  loading = false,
}: {
  title: string;
  description?: string;
  retry?: () => void;
  loading?: boolean;
}) {
  return (
    <main className="page-state" id="main-content" tabIndex={-1}>
      <div role={loading ? "status" : "alert"}>
        {loading && (
          <LoaderCircle className="loading-icon" aria-hidden="true" size={28} />
        )}
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      {retry && <Button onClick={retry}>Volver a cargar</Button>}
    </main>
  );
}
