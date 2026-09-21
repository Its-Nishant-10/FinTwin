"use client";

/** Last-resort boundary: a rendering failure shows this instead of a blank page. */
export default function ErrorPage({ error, reset }: { error: Error; reset: () => void }) {
  return (
    <main>
      <h1>FinTwin</h1>
      <div className="card">
        <p className="status-down">Something went wrong drawing the dashboard.</p>
        <p className="todo">{error.message}</p>
        <button type="button" className="btn btn--primary" onClick={reset}>
          Try again
        </button>
      </div>
    </main>
  );
}
