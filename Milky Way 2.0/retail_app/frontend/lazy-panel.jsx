import React, { Suspense, lazy, useMemo, useState } from "react";
import { ArrowLeft, LoaderCircle } from "lucide-react";

export function PanelLoading({ title, onBack }) {
  return (
    <section className="improve-empty" aria-label={title} aria-busy="true">
      <p role="status">
        <LoaderCircle size={18} /> Loading {title.toLowerCase()}…
      </p>
      <button className="improve-button" onClick={onBack}>
        <ArrowLeft size={16} /> Back to chat
      </button>
    </section>
  );
}

export function PanelLoadError({ title, onRetry, onBack }) {
  return (
    <section className="improve-empty" aria-label={title}>
      <h2>This screen could not load</h2>
      <p role="alert">
        Check your connection and try again. If the app was updated, reload it
        to get the latest version.
      </p>
      <div className="improve-actions">
        <button className="improve-button primary" onClick={onRetry}>
          Try again
        </button>
        <button
          className="improve-button"
          onClick={() => window.location.reload()}
        >
          Reload app
        </button>
        <button className="improve-button" onClick={onBack}>
          Back to chat
        </button>
      </div>
    </section>
  );
}

class PanelBoundary extends React.Component {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? (
      <PanelLoadError {...this.props} />
    ) : (
      this.props.children
    );
  }
}

/** Keep optional screens out of the initial chat bundle and recover from chunk failures. */
export function LazyPanel({ load, title, onBack, panelProps = {} }) {
  const [attempt, setAttempt] = useState(0);
  // A fresh lazy component retries the loader rather than retaining its rejected promise.
  const Panel = useMemo(() => lazy(load), [load, attempt]);
  return (
    <PanelBoundary
      key={attempt}
      title={title}
      onBack={onBack}
      onRetry={() => setAttempt((value) => value + 1)}
    >
      <Suspense fallback={<PanelLoading title={title} onBack={onBack} />}>
        <Panel {...panelProps} />
      </Suspense>
    </PanelBoundary>
  );
}
