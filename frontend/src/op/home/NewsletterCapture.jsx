// Newsletter capture — presentational only in this PR. No backend route,
// no fetch. The submit handler is a no-op preventDefault.

export default function NewsletterCapture() {
  const handleSubmit = (e) => {
    e.preventDefault();
    // Intentionally no-op — newsletter backend is a separate workstream.
  };

  return (
    <section className="news" aria-labelledby="news-title">
      <div className="news-inner">
        <div>
          <h2 id="news-title">The matchday edition.</h2>
          <p>One short edition per matchday — what the prices moved, what's still off, what we read.</p>
        </div>
        <form onSubmit={handleSubmit}>
          <label className="visually-hidden" htmlFor="news-email">Email address</label>
          <input id="news-email" type="email" placeholder="your.email@domain.com" required />
          <button type="submit">Subscribe</button>
          <div className="fine" style={{ flexBasis: "100%" }}>
            No tips, no spam, one click to leave.
          </div>
        </form>
      </div>
    </section>
  );
}
