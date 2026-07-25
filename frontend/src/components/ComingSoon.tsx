// Placeholder for nav routes not yet built — keeps the full 7-item sidebar
// navigable from Sprint 6 on, even though only Generate + Library exist so far.
// `page`/`pageEyebrow`/`pageTitle`/`pageMeta` are global utility classes from
// styles/tokens.css (imported once in index.css), not CSS modules.
export function ComingSoon({ title, sprint }: { title: string; sprint: string }) {
  return (
    <div className="page">
      <div className="pageEyebrow">Coming in {sprint}</div>
      <h1 className="pageTitle">{title}</h1>
      <p className="pageMeta">This screen isn't built yet — see plan.md for the sprint plan.</p>
    </div>
  );
}
