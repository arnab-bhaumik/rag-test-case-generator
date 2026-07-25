// Review and Coverage Matrix are per-run screens, but the sidebar nav links
// to them with no run in the URL (Run History — the natural way to pick a
// run — doesn't exist until Sprint 8). Remembering the most recently
// generated run locally lets "Review"/"Coverage Matrix" in the sidebar still
// go somewhere useful without a run list.
const KEY = 'qa-test-generator:last-run-id';

export function setLastRunId(id: string) {
  localStorage.setItem(KEY, id);
}

export function getLastRunId(): string | null {
  return localStorage.getItem(KEY);
}
