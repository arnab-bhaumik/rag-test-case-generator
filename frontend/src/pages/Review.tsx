import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  acknowledgeGap,
  bulkApprove,
  bulkReject,
  generateGap,
  getRun,
  patchTestCase,
  regenerateTestCase,
  type Category,
  type Priority,
  type Run,
  type TestCase,
} from '../api/client';
import { Button } from '../components/Button';
import { AlertTriangleIcon, CheckIcon, ChevronDownIcon, XIcon } from '../components/icons';
import { Pill } from '../components/Pill';
import { getLastRunId } from '../lib/lastRun';
import styles from './Review.module.css';

const CATEGORY_ORDER: Category[] = ['Positive', 'Negative', 'Boundary', 'Edge', 'Security', 'Integration', 'Data Validation'];
const PRIORITY_ORDER: Priority[] = ['High', 'Medium', 'Low'];

const CATEGORY_DOT_VAR: Record<Category, string> = {
  Positive: '--cat-positive',
  Negative: '--cat-negative',
  Boundary: '--cat-boundary',
  Edge: '--cat-edge',
  Security: '--cat-security',
  Integration: '--cat-integration',
  'Data Validation': '--cat-data-validation',
};

export function Review() {
  const { runId: paramRunId } = useParams();
  const runId = paramRunId || getLastRunId() || undefined;

  const [run, setRun] = useState<Run | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [openSections, setOpenSections] = useState<Partial<Record<Category, boolean>>>({});
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [bulkMessage, setBulkMessage] = useState<string | null>(null);
  const [priorityFilter, setPriorityFilter] = useState<Set<Priority>>(new Set());
  const [verificationFilter, setVerificationFilter] = useState(false);

  function reload() {
    if (!runId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    getRun(runId)
      .then((r) => {
        setRun(r);
        setLoadError(null);
      })
      .catch((e) => setLoadError(e instanceof Error ? e.message : 'Failed to load run'))
      .finally(() => setLoading(false));
  }

  useEffect(reload, [runId]);

  function updateCaseLocal(updated: TestCase | TestCase[]) {
    const list = Array.isArray(updated) ? updated : [updated];
    setRun((prev) => {
      if (!prev) return prev;
      const byId = new Map(list.map((c) => [c.id, c]));
      const existingIds = new Set(prev.test_cases.map((c) => c.id));
      const merged = prev.test_cases.map((c) => byId.get(c.id) ?? c);
      const added = list.filter((c) => !existingIds.has(c.id));
      return { ...prev, test_cases: [...merged, ...added] };
    });
  }

  // regenerate replaces a case with brand-new-ID case(s) — updateCaseLocal's
  // id-matching merge would leave the stale original sitting alongside the
  // new ones, so this removes it explicitly instead.
  function replaceCaseLocal(oldId: string, replacements: TestCase[]) {
    setRun((prev) => (prev ? { ...prev, test_cases: [...prev.test_cases.filter((c) => c.id !== oldId), ...replacements] } : prev));
  }

  // Same problem as replaceCaseLocal, one case at a time — editing the Test
  // Case ID itself changes the key everything else (selection, expansion)
  // was tracking it by, so those need to move to the new id too.
  function replaceCaseIdLocal(oldId: string, updated: TestCase) {
    setRun((prev) => (prev ? { ...prev, test_cases: [...prev.test_cases.filter((c) => c.id !== oldId), updated] } : prev));
    setSelected((prev) => {
      if (!prev.has(oldId)) return prev;
      const next = new Set(prev);
      next.delete(oldId);
      next.add(updated.id);
      return next;
    });
    setExpandedId((prev) => (prev === oldId ? updated.id : prev));
  }

  if (!runId) {
    return (
      <div className="page">
        <PageHeader />
        <EmptyState />
      </div>
    );
  }

  if (loading) {
    return (
      <div className="page">
        <PageHeader run={run} />
        <p className="pageMeta">Loading…</p>
      </div>
    );
  }

  if (loadError || !run) {
    return (
      <div className="page">
        <PageHeader />
        <EmptyState message={loadError ?? undefined} />
      </div>
    );
  }

  const cases = run.test_cases;
  const counts = {
    total: cases.length,
    approved: cases.filter((c) => c.status === 'approved').length,
    rejected: cases.filter((c) => c.status === 'rejected').length,
    unreviewed: cases.filter((c) => c.status === 'unreviewed').length,
    gaps: run.gaps.filter((g) => !g.acknowledged).length,
  };

  const hasActiveFilter = priorityFilter.size > 0 || verificationFilter;
  const filteredCases = cases.filter(
    (c) => (priorityFilter.size === 0 || priorityFilter.has(c.priority)) && (!verificationFilter || !c.grounded),
  );

  function togglePriorityFilter(p: Priority) {
    setPriorityFilter((prev) => {
      const next = new Set(prev);
      if (next.has(p)) next.delete(p);
      else next.add(p);
      return next;
    });
  }

  function clearFilters() {
    setPriorityFilter(new Set());
    setVerificationFilter(false);
  }

  const selectedCount = selected.size;

  function toggleSelectAll() {
    setSelected((prev) => (prev.size > 0 ? new Set() : new Set(filteredCases.map((c) => c.id))));
  }

  function toggleSelect(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function handleBulkApprove() {
    const { approved, blocked } = await bulkApprove([...selected]);
    setSelected(new Set());
    setBulkMessage(
      blocked.length > 0
        ? `${approved.length} approved. ${blocked.length} blocked — still ${blocked.length === 1 ? 'needs' : 'need'} manual verification (expand the case, check "I have manually verified…", then approve it individually).`
        : null,
    );
    reload();
  }

  async function handleBulkReject() {
    await bulkReject([...selected]);
    setSelected(new Set());
    setBulkMessage(null);
    reload();
  }

  return (
    <div className="page" style={{ maxWidth: 1360 }}>
      <PageHeader run={run} />

      <div className={styles.statsRow}>
        <div className={`card ${styles.statCard}`}>
          <div className={styles.statNum}>{counts.total}</div>
          <div className={styles.statLabel}>Total generated</div>
        </div>
        <div className={`card ${styles.statCard}`}>
          <div className={`${styles.statNum} ${styles.approved}`}>{counts.approved}</div>
          <div className={styles.statLabel}>Approved</div>
        </div>
        <div className={`card ${styles.statCard}`}>
          <div className={`${styles.statNum} ${styles.rejected}`}>{counts.rejected}</div>
          <div className={styles.statLabel}>Rejected</div>
        </div>
        <div className={`card ${styles.statCard}`}>
          <div className={styles.statNum}>{counts.unreviewed}</div>
          <div className={styles.statLabel}>Unreviewed</div>
        </div>
        <div className={`card ${styles.statCard} ${counts.gaps > 0 ? styles.gapAlert : ''}`}>
          <div className={`${styles.statNum} ${counts.gaps > 0 ? styles.gap : ''}`}>{counts.gaps}</div>
          <div className={styles.statLabel}>Coverage gaps</div>
        </div>
      </div>

      <div className={`card ${styles.filterBar}`}>
        <span className={styles.filterLabel}>Filter:</span>
        {PRIORITY_ORDER.map((p) => (
          <button
            key={p}
            type="button"
            className={`${styles.filterChip} ${priorityFilter.has(p) ? styles.filterChipActive : ''}`}
            onClick={() => togglePriorityFilter(p)}
          >
            {p}
          </button>
        ))}
        <button
          type="button"
          className={`${styles.filterChip} ${verificationFilter ? styles.filterChipActive : ''}`}
          onClick={() => setVerificationFilter((v) => !v)}
        >
          Needs verification
        </button>
        {hasActiveFilter && (
          <>
            <button type="button" className={styles.filterClear} onClick={clearFilters}>
              Clear filters
            </button>
            <span className={styles.toolbarCount} style={{ marginLeft: 'auto' }}>
              Showing {filteredCases.length} of {cases.length}
            </span>
          </>
        )}
      </div>

      <div className={`card ${styles.toolbar}`}>
        <input type="checkbox" checked={selectedCount > 0 && selectedCount === filteredCases.length} onChange={toggleSelectAll} />
        <span className={styles.toolbarCount}>{selectedCount} selected</span>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          <Button variant="secondary" disabled={selectedCount === 0} onClick={handleBulkReject}>
            <XIcon size={14} /> Reject selected
          </Button>
          <Button variant="primary" disabled={selectedCount === 0} onClick={handleBulkApprove}>
            <CheckIcon size={14} /> Approve selected
          </Button>
        </div>
      </div>

      {bulkMessage && (
        <div className={styles.bulkMessage}>
          <AlertTriangleIcon size={16} color="var(--warning-text-2)" />
          <span>{bulkMessage}</span>
        </div>
      )}

      {hasActiveFilter && filteredCases.length === 0 && (
        <div className={`card ${styles.emptyState}`}>
          <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-body-2)' }}>No test cases match this filter</div>
          <div className="pageMeta">Try a different priority, or clear the filter.</div>
          <button type="button" className={styles.filterClear} onClick={clearFilters}>
            Clear filters
          </button>
        </div>
      )}

      <div className={styles.sections}>
        {CATEGORY_ORDER.map((category) => {
          const catCasesAll = cases.filter((c) => c.category === category);
          const catCases = filteredCases.filter((c) => c.category === category);
          const gap = run.gaps.find((g) => g.category === category);
          const isEmpty = catCasesAll.length === 0; // genuine gap — no cases were ever generated here
          const hiddenByFilter = !isEmpty && catCases.length === 0 && hasActiveFilter;
          const open = openSections[category] ?? true;
          const allReviewed = catCases.length > 0 && catCases.every((c) => c.status !== 'unreviewed');

          if (hiddenByFilter) return null;

          return (
            <div key={category} className={`card ${styles.section} ${isEmpty && !gap?.acknowledged ? styles.sectionGap : ''}`}>
              <div
                className={`${styles.sectionHeader} ${isEmpty && !gap?.acknowledged ? styles.sectionHeaderGap : ''}`}
                onClick={() => setOpenSections((s) => ({ ...s, [category]: !open }))}
              >
                <span className={`${styles.chevron} ${!open ? styles.chevronClosed : ''}`}>
                  <ChevronDownIcon size={14} color="var(--text-muted-2)" />
                </span>
                <span className={styles.dot} style={{ background: `var(${CATEGORY_DOT_VAR[category]})` }} />
                <span className={styles.sectionName}>{category}</span>
                <span className={styles.sectionCount}>
                  {!isEmpty && `${catCases.length}${allReviewed ? ' · all reviewed' : ` · ${catCases.filter((c) => c.status === 'unreviewed').length} unreviewed`}`}
                </span>
                {isEmpty && (
                  <Pill tone={gap?.acknowledged ? 'neutral' : 'warning'}>
                    {gap?.acknowledged ? 'Reviewed — not applicable' : 'Gap — no cases generated'}
                  </Pill>
                )}
              </div>

              {open && isEmpty && (
                <GapContent
                  runId={run.id}
                  category={category}
                  acknowledged={gap?.acknowledged ?? false}
                  onFilled={(newCases) => {
                    updateCaseLocal(newCases);
                    setRun((prev) => (prev ? { ...prev, gaps: prev.gaps.filter((g) => g.category !== category) } : prev));
                  }}
                  onAcknowledged={() =>
                    setRun((prev) =>
                      prev
                        ? { ...prev, gaps: prev.gaps.map((g) => (g.category === category ? { ...g, acknowledged: true } : g)) }
                        : prev,
                    )
                  }
                />
              )}

              {open && !isEmpty && (
                <div className={styles.caseList}>
                  {catCases.map((c) => (
                    <CaseRow
                      key={c.id}
                      testCase={c}
                      selected={selected.has(c.id)}
                      expanded={expandedId === c.id}
                      onToggleSelect={() => toggleSelect(c.id)}
                      onToggleExpand={() => setExpandedId((prev) => (prev === c.id ? null : c.id))}
                      onSaved={updateCaseLocal}
                      onIdChanged={replaceCaseIdLocal}
                      onRegenerated={(newCases) => {
                        replaceCaseLocal(c.id, newCases);
                        setExpandedId(null);
                      }}
                    />
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function PageHeader({ run }: { run?: Run | null }) {
  return (
    <div style={{ marginBottom: 20 }}>
      <div className="pageEyebrow">Review</div>
      <h1 className="pageTitle">Review Generated Test Cases</h1>
      {run && (
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: 'var(--text-muted)' }}>
            <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--text-body-2)' }}>{run.source_id}</span>
            {run.module && (
              <>
                <span>·</span>
                <span>{run.module}</span>
              </>
            )}
          </div>
          {run.scope && (
            <div style={{ fontSize: 12.5, color: 'var(--text-muted)', marginTop: 4 }}>
              Scoped to: <span style={{ color: 'var(--text-body-2)', fontWeight: 500 }}>{run.scope}</span>
            </div>
          )}
          {run.id_prefix && (
            <div style={{ fontSize: 12.5, color: 'var(--text-muted)', marginTop: 4 }}>
              Test Case ID prefix:{' '}
              <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-body-2)', fontWeight: 500 }}>{run.id_prefix}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function EmptyState({ message }: { message?: string }) {
  return (
    <div className={`card ${styles.emptyState}`}>
      <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-body-2)' }}>
        {message ? 'Could not load this run' : 'No run selected'}
      </div>
      <div className="pageMeta">{message ?? 'Start a generation run to review its test cases here.'}</div>
      <Link to="/" style={{ marginTop: 4 }}>
        Start a generation run
      </Link>
    </div>
  );
}

function GapContent({
  runId,
  category,
  acknowledged,
  onFilled,
  onAcknowledged,
}: {
  runId: string;
  category: Category;
  acknowledged: boolean;
  onFilled: (cases: TestCase[]) => void;
  onAcknowledged: () => void;
}) {
  const [busy, setBusy] = useState<'generate' | 'acknowledge' | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleGenerate() {
    setBusy('generate');
    setError(null);
    try {
      const cases = await generateGap(runId, category);
      onFilled(cases);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not generate cases for this category');
    } finally {
      setBusy(null);
    }
  }

  async function handleAcknowledge() {
    setBusy('acknowledge');
    try {
      await acknowledgeGap(runId, category);
      onAcknowledged();
    } finally {
      setBusy(null);
    }
  }

  if (acknowledged) {
    return (
      <div className={styles.gapContent}>
        <div className="pageMeta">This category was reviewed and marked not applicable for this requirement.</div>
      </div>
    );
  }

  return (
    <div className={styles.gapContent}>
      <div className={styles.gapText}>
        No test cases were generated for this category. This may be an intentional gap or a missed requirement branch.
      </div>
      <div className={styles.gapActions}>
        <Button variant="primary" disabled={busy !== null} onClick={handleGenerate}>
          {busy === 'generate' ? 'Generating…' : 'Generate manually'}
        </Button>
        <Button variant="secondary" disabled={busy !== null} onClick={handleAcknowledge}>
          {busy === 'acknowledge' ? 'Saving…' : 'Mark reviewed — not applicable'}
        </Button>
      </div>
      {error && <div className={styles.gapError}>{error}</div>}
    </div>
  );
}

function CaseRow({
  testCase,
  selected,
  expanded,
  onToggleSelect,
  onToggleExpand,
  onSaved,
  onIdChanged,
  onRegenerated,
}: {
  testCase: TestCase;
  selected: boolean;
  expanded: boolean;
  onToggleSelect: () => void;
  onToggleExpand: () => void;
  onSaved: (updated: TestCase) => void;
  onIdChanged: (oldId: string, updated: TestCase) => void;
  onRegenerated: (newCases: TestCase[]) => void;
}) {
  const [caseId, setCaseId] = useState(testCase.id);
  const [idError, setIdError] = useState<string | null>(null);
  const [title, setTitle] = useState(testCase.title);
  const [description, setDescription] = useState(testCase.description);
  const [preconditions, setPreconditions] = useState(testCase.preconditions);
  const [steps, setSteps] = useState(testCase.steps);
  const [expectedResult, setExpectedResult] = useState(testCase.expected_result);
  const [busy, setBusy] = useState(false);
  const [approveError, setApproveError] = useState<string | null>(null);
  const [regenerateError, setRegenerateError] = useState<string | null>(null);

  useEffect(() => {
    setCaseId(testCase.id);
    setIdError(null);
    setRegenerateError(null);
    setTitle(testCase.title);
    setDescription(testCase.description);
    setPreconditions(testCase.preconditions);
    setSteps(testCase.steps);
    setExpectedResult(testCase.expected_result);
  }, [testCase]);

  const needsVerification = !testCase.grounded;
  const approveDisabled = needsVerification && !testCase.manually_verified;

  async function save(
    patch: Partial<{ title: string; description: string; preconditions: string; steps: string[]; expected_result: string }>,
  ) {
    const updated = await patchTestCase(testCase.id, patch);
    onSaved(updated);
  }

  async function saveId() {
    const trimmed = caseId.trim();
    if (trimmed === testCase.id) return;
    setIdError(null);
    try {
      const updated = await patchTestCase(testCase.id, { id: trimmed });
      onIdChanged(testCase.id, updated);
    } catch (e) {
      setIdError(e instanceof Error ? e.message : 'Could not update Test Case ID');
      setCaseId(testCase.id);
    }
  }

  async function handleApprove() {
    setBusy(true);
    try {
      // Routed through bulk-approve (with a single id) rather than PATCH so
      // the grounding gate is enforced by the same server-side check the
      // toolbar's "Approve selected" uses — one enforcement point, not two.
      const { approved, blocked } = await bulkApprove([testCase.id]);
      if (approved[0]) onSaved(approved[0]);
      else if (blocked.length) setApproveError('Blocked: needs verification before it can be approved.');
    } finally {
      setBusy(false);
    }
  }

  async function handleReject() {
    setBusy(true);
    try {
      const { rejected } = await bulkReject([testCase.id]);
      if (rejected[0]) onSaved(rejected[0]);
    } finally {
      setBusy(false);
    }
  }

  async function handleUndo() {
    const updated = await patchTestCase(testCase.id, { status: 'unreviewed' });
    onSaved(updated);
  }

  async function handleToggleVerify() {
    const updated = await patchTestCase(testCase.id, { manually_verified: !testCase.manually_verified });
    onSaved(updated);
  }

  async function handleRegenerate() {
    setBusy(true);
    setRegenerateError(null);
    try {
      const fresh = await regenerateTestCase(testCase.id);
      onRegenerated(fresh);
    } catch (e) {
      setRegenerateError(e instanceof Error ? e.message : 'Regeneration failed — try again.');
    } finally {
      setBusy(false);
    }
  }

  const statusColor =
    testCase.status === 'approved' ? 'var(--success-icon)' : testCase.status === 'rejected' ? 'var(--danger)' : 'var(--text-disabled)';

  return (
    <div className={`${styles.caseRow} ${testCase.status === 'rejected' ? styles.caseRowRejected : ''}`}>
      <div className={styles.caseHeader} onClick={onToggleExpand}>
        <input type="checkbox" checked={selected} onClick={(e) => e.stopPropagation()} onChange={onToggleSelect} />
        {testCase.status === 'approved' && <CheckIcon size={17} color={statusColor} />}
        {testCase.status === 'rejected' && <XIcon size={17} color={statusColor} />}
        {testCase.status === 'unreviewed' && (
          <span style={{ width: 17, height: 17, borderRadius: '50%', border: `1.5px solid ${statusColor}`, flexShrink: 0 }} />
        )}
        <span className={styles.caseId}>{testCase.id}</span>
        <span className={`${styles.caseTitle} ${testCase.status === 'rejected' ? styles.caseTitleRejected : ''}`}>{testCase.title}</span>
        <Pill tone={testCase.priority === 'High' ? 'danger' : testCase.priority === 'Medium' ? 'warning' : 'neutral'}>
          {testCase.priority}
        </Pill>
        {testCase.status === 'approved' && <Pill tone="success">Approved</Pill>}
        {testCase.status === 'rejected' && <Pill tone="danger">Rejected</Pill>}
        {testCase.edited && <Pill tone="brand">Edited</Pill>}
        {needsVerification && <Pill tone="warning">Needs verification</Pill>}
        {testCase.trace && <span className={styles.caseTrace}>{testCase.trace}</span>}
      </div>

      {expanded && (
        <div className={styles.caseDetail}>
          <div className="pageMeta">
            Derived from: <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-body-2)', fontWeight: 600 }}>{testCase.trace}</span>
          </div>

          <div className={styles.detailField}>
            <label className="label">Test Case ID</label>
            <input
              className="textInput"
              style={{ fontFamily: 'var(--font-mono)' }}
              value={caseId}
              onChange={(e) => setCaseId(e.target.value)}
              onBlur={saveId}
            />
            {idError && <div className={styles.gapError}>{idError}</div>}
          </div>

          <div className={styles.detailField}>
            <label className="label">Test Scenario</label>
            <input className="textInput" value={title} onChange={(e) => setTitle(e.target.value)} onBlur={() => save({ title })} />
          </div>

          <div className={styles.detailField}>
            <label className="label">Description</label>
            <input
              className="textInput"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              onBlur={() => save({ description })}
            />
          </div>

          <div className={styles.detailField}>
            <label className="label">Pre-conditions</label>
            <input
              className="textInput"
              value={preconditions}
              onChange={(e) => setPreconditions(e.target.value)}
              onBlur={() => save({ preconditions })}
            />
          </div>

          <div className={styles.detailField}>
            <label className="label">Steps</label>
            {steps.map((step, i) => (
              <div key={i} className={styles.stepRow}>
                <span className={styles.stepN}>{i + 1}.</span>
                <input
                  className="textInput"
                  style={{ flex: 1 }}
                  value={step}
                  onChange={(e) => setSteps((s) => s.map((v, j) => (j === i ? e.target.value : v)))}
                  onBlur={() => save({ steps })}
                />
                <button
                  className={styles.stepRemove}
                  title="Remove step"
                  onClick={() => {
                    const next = steps.filter((_, j) => j !== i);
                    setSteps(next);
                    save({ steps: next });
                  }}
                >
                  <XIcon size={12} />
                </button>
              </div>
            ))}
            <button
              className={styles.addStep}
              onClick={() => setSteps((s) => [...s, 'New step'])}
            >
              + Add step
            </button>
          </div>

          <div className={styles.detailField}>
            <label className="label">Expected Results</label>
            <input
              className="textInput"
              value={expectedResult}
              onChange={(e) => setExpectedResult(e.target.value)}
              onBlur={() => save({ expected_result: expectedResult })}
            />
          </div>

          <div className={`${styles.groundedBanner} ${testCase.grounded ? styles.groundedOk : styles.groundedWarn}`}>
            {testCase.grounded ? <CheckIcon size={15} color="var(--success-icon)" /> : <span>⚠</span>}
            <span style={{ fontSize: 13, fontWeight: 600 }}>
              {testCase.grounded ? 'Grounded — verified against source requirement' : 'Needs verification — could not confirm against source'}
            </span>
          </div>

          {needsVerification && (
            <label className={styles.verifyCheck}>
              <input type="checkbox" checked={testCase.manually_verified} onChange={handleToggleVerify} />
              I have manually verified this against the requirement
            </label>
          )}

          <div className={styles.caseActions}>
            <Button variant="primary" disabled={approveDisabled || busy} onClick={handleApprove}>
              <CheckIcon size={14} /> Approve
            </Button>
            <Button variant="danger" disabled={busy} onClick={handleReject}>
              <XIcon size={14} /> Reject
            </Button>
            <Button variant="secondary" disabled={busy} onClick={handleRegenerate}>
              Regenerate this one
            </Button>
            {testCase.status === 'rejected' && (
              <button className={styles.undoLink} onClick={handleUndo}>
                Undo reject
              </button>
            )}
          </div>
          {approveError && <div className={styles.gapError}>{approveError}</div>}
          {regenerateError && <div className={styles.gapError}>{regenerateError}</div>}
        </div>
      )}
    </div>
  );
}
