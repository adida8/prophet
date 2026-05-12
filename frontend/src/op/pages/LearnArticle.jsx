// Generic primer layout — masthead + breadcrumb + article shell + next-up + footer.
// The article body content is passed as children so each primer file keeps
// its copy alongside its routing slug.

import Footer from "../Footer";
import Masthead from "../Masthead";

export default function LearnArticle({
  navigate,
  currentPath,
  eyebrow,
  title,
  standfirst,
  meta,
  editionLeft,
  editionRight,
  crumbLabel,
  children,
  nextLabel,
  nextHref,
  nextDescription,
}) {
  const goLearn = (e) => {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.button === 1) return;
    e.preventDefault();
    if (navigate) navigate("/learn");
  };

  const goNext = (e) => {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.button === 1) return;
    if (!nextHref) return;
    e.preventDefault();
    if (nextHref.startsWith("/#")) {
      if (navigate) navigate("/");
      setTimeout(() => {
        const id = nextHref.slice(2);
        const t = document.getElementById(id);
        if (t) t.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 50);
      return;
    }
    if (navigate) navigate(nextHref);
  };

  return (
    <div className="op-site">
      <Masthead
        variant="minimal"
        currentPath={currentPath}
        navigate={navigate}
        editionLeft={editionLeft}
        editionRight={editionRight}
      />

      <main className="page">
        <div className="crumb">
          <a href="/learn" onClick={goLearn}>Learn</a>
          <span className="sep">·</span>
          <span>{crumbLabel}</span>
        </div>

        <article className="learn-article">
          <div className="eyebrow">{eyebrow}</div>
          <h1>{title}</h1>
          <p className="standfirst">{standfirst}</p>
          <div className="meta">{meta}</div>

          <div className="article-body">{children}</div>

          <div className="nextup">
            <span className="nlbl">{nextDescription || "Next up"}</span>
            <a href={nextHref} onClick={goNext}>
              {nextLabel} <span className="arr">→</span>
            </a>
          </div>
        </article>
      </main>

      <Footer navigate={navigate} currentPath={currentPath} />
    </div>
  );
}
