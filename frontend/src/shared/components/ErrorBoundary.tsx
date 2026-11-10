import type { PropsWithChildren } from "react";
import { Component } from "react";
import { PageState } from "./PageState.tsx";
export class ErrorBoundary extends Component<
  PropsWithChildren,
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    if (this.state.failed)
      return (
        <PageState
          title="No pudimos mostrar esta página"
          description="Vuelve a cargar para recuperar la aplicación."
          retry={() => window.location.reload()}
        />
      );
    return this.props.children;
  }
}
