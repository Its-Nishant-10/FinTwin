/** Shown while the server waits on the backend for the first view. */
export default function Loading() {
  return (
    <main aria-busy="true">
      <h1>FinTwin</h1>
      <p className="tagline">Explainable AI personal finance intelligence &amp; simulation</p>
      <div className="card skeleton" role="status">
        Loading your digital twin…
      </div>
    </main>
  );
}
