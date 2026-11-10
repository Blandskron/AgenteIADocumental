import React from "react";
import { createRoot } from "react-dom/client";
import { ErrorBoundary } from "@/shared/components/ErrorBoundary.tsx";

import "../shared/styles/index.css";
import { App } from "./App";
import { AuthProvider } from "./providers/AuthProvider";
import { ThemeProvider } from "./providers/ThemeProvider";

const root = document.getElementById("root");
if (!root) throw new Error("No se encontró el contenedor de la aplicación.");
createRoot(root).render(
  <React.StrictMode>
    <ErrorBoundary>
      <AuthProvider>
        <ThemeProvider>
          <App />
        </ThemeProvider>
      </AuthProvider>
    </ErrorBoundary>
  </React.StrictMode>,
);
