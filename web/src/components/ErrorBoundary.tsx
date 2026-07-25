import { Component, type ReactNode } from "react";

/* Catches render errors in a tool so the whole app never white-screens. */
export default class ErrorBoundary extends Component<
  { children: ReactNode }, { error: Error | null }
> {
  state = { error: null as Error | null };
  static getDerivedStateFromError(error: Error) { return { error }; }
  componentDidCatch(error: Error) { console.error("[Foreman] tool error:", error); }

  render() {
    if (this.state.error) {
      return (
        <div className="mx-auto max-w-md rounded-xl border border-red/30 bg-red/5 p-6 text-center">
          <div className="font-display text-lg font-bold text-red">Something went wrong here</div>
          <p className="mt-2 text-sm text-muted">
            This tool hit an error. Try reloading, or check that the API is running.
          </p>
          <button onClick={() => this.setState({ error: null })}
            className="mt-4 rounded-lg border border-line-strong px-4 py-2 text-sm transition hover:border-amber/50">
            Try again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
