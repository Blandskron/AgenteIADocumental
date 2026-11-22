import type { PropsWithChildren } from "react";
import { Component } from "react";
import { PageState } from "./PageState.tsx";

export type ErrorBoundaryProps = PropsWithChildren<{
  resetKey?: string;
}>;

export class ErrorBoundary extends Component<
  ErrorBoundaryProps,
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidUpdate(prevProps: ErrorBoundaryProps) {
    if (this.state.failed && prevProps.resetKey !== this.props.resetKey) {
      this.setState({ failed: false });
    }
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
