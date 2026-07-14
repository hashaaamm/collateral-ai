import { Component, type ReactNode } from "react";

type Props = {
  children: ReactNode;
  /** Rendered in place of `children` once a descendant throws. `reset` clears
   *  the caught error so the subtree re-mounts (pair it with a data refetch). */
  fallback: (error: Error, reset: () => void) => ReactNode;
};

type State = { error: Error | null };

/**
 * Minimal React error boundary. Catches render/lifecycle errors from its
 * subtree — used to keep app chrome (the sidebar) mounted when a page crashes,
 * while the router's defaultErrorComponent handles errors above the shell.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  reset = () => this.setState({ error: null });

  render() {
    const { error } = this.state;
    if (error) return this.props.fallback(error, this.reset);
    return this.props.children;
  }
}
