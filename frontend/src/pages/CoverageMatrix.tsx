import { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { getRun, type Run, type TestCase } from '../api/client';
import { AlertTriangleIcon, CheckIcon, CoverageIcon } from '../components/icons';
import { getLastRunId } from '../lib/lastRun';
import styles from './CoverageMatrix.module.css';

type CoverageFilter = 'all' | 'covered' | 'uncovered';

interface Row {
  conditionId: string;
  ac: string | null;
  requirement: string;
  linked: TestCase[];
  covered: boolean;
}

// Mirrors src/traceability/rtm_builder.py's build_rtm() — computed client-side
// from the already-fetched Run rather than a second request, since we need
// each linked case's full status (for pill color) anyway, not just its id.
function buildRtm(run: Run): Row[] {
  const byCondition = new Map<string, TestCase[]>();
  for (const tc of run.test_cases) {
    if (!tc.condition_id) continue;
    const list = byCondition.get(tc.condition_id) ?? [];
    list.push(tc);
    byCondition.set(tc.condition_id, list);
  }
  return run.conditions.map((c) => {
    const linked = byCondition.get(c.id) ?? [];
    return {
      conditionId: c.id,
      ac: c.ac_ref,
      requirement: c.text,
      linked,
      covered: linked.some((tc) => tc.status === 'approved'),
    };
  });
}

export function CoverageMatrix() {
  const { runId: paramRunId } = useParams();
  const runId = paramRunId || getLastRunId() || undefined;

  const [run, setRun] = useState<Run | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState<CoverageFilter>('all');

  useEffect(() => {
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
  }, [runId]);

  const rows = useMemo(() => (run ? buildRtm(run) : []), [run]);

  const filteredRows = useMemo(() => {
    return rows.filter((r) => {
      if (filter === 'covered' && !r.covered) return false;
      if (filter === 'uncovered' && r.covered) return false;
      if (query && !r.requirement.toLowerCase().includes(query.toLowerCase()) && !r.linked.some((tc) => tc.id.includes(query))) {
        return false;
      }
      return true;
    });
  }, [rows, filter, query]);

  const gapCount = rows.filter((r) => !r.covered).length;

  if (!runId || (!loading && !run)) {
    return (
      <div className="page">
        <PageHeader />
        <div className={`card ${styles.emptyState}`}>
          <CoverageIcon size={30} color="var(--text-faint)" />
          <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-body-2)' }}>
            {loadError ?? 'No requirements decomposed yet'}
          </div>
          <div className="pageMeta" style={{ maxWidth: 360 }}>
            Run a generation from a Jira ticket or document to decompose requirements and build the coverage matrix.
          </div>
          <Link to="/">Start a generation run</Link>
        </div>
      </div>
    );
  }

  if (loading || !run) {
    return (
      <div className="page">
        <PageHeader />
        <p className="pageMeta">Loading…</p>
      </div>
    );
  }

  return (
    <div className="page" style={{ maxWidth: 1200 }}>
      <PageHeader run={run} />

      {gapCount === 0 ? (
        <div className={`${styles.banner} ${styles.bannerOk}`}>
          <CheckIcon size={17} color="var(--success-icon)" />
          All requirements covered
        </div>
      ) : (
        <div className={`${styles.banner} ${styles.bannerGap}`}>
          <AlertTriangleIcon size={17} color="var(--warning-text-2)" />
          <span className={styles.bannerGapText}>{gapCount} requirement(s) have no approved test coverage</span>
          <a
            href="#"
            onClick={(e) => {
              e.preventDefault();
              setFilter('uncovered');
            }}
          >
            Jump to gaps
          </a>
        </div>
      )}

      <div className={`card ${styles.toolbar}`}>
        <input
          type="text"
          className={styles.searchInput}
          placeholder="Search requirement or test case ID…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <div className={styles.filterGroup}>
          {(['all', 'covered', 'uncovered'] as const).map((f) => (
            <button
              key={f}
              className={`${styles.filterBtn} ${filter === f ? styles.filterBtnActive : ''}`}
              onClick={() => setFilter(f)}
            >
              {f === 'all' ? 'All' : f === 'covered' ? 'Covered' : 'Uncovered'}
            </button>
          ))}
        </div>
      </div>

      <div className={styles.headerRow}>
        <div>AC</div>
        <div>Requirement / Condition</div>
        <div>Linked Test Cases</div>
        <div>Covered</div>
      </div>

      <div className={styles.rows}>
        {filteredRows.map((row) => (
          <div key={row.conditionId} className={`card ${styles.row} ${!row.covered ? styles.rowUncovered : ''}`}>
            <div className={styles.rowAc}>{row.ac ?? '—'}</div>
            <div className={styles.rowReq}>{row.requirement}</div>
            <div className={styles.linkedWrap}>
              {row.linked.length === 0 ? (
                <span className={styles.linkedNone}>— none —</span>
              ) : (
                row.linked.map((tc) => (
                  <Link
                    key={tc.id}
                    to={`/review/${run.id}`}
                    className={styles.linkedPill}
                    style={{
                      color: tc.status === 'approved' ? 'var(--success-text-strong)' : tc.status === 'rejected' ? 'var(--danger-text)' : 'var(--text-secondary)',
                      background: tc.status === 'approved' ? 'var(--success-bg)' : tc.status === 'rejected' ? 'var(--danger-bg-2)' : 'var(--bg-soft)',
                    }}
                  >
                    {tc.id.split('::').pop()}
                  </Link>
                ))
              )}
            </div>
            <div className={styles.coveredCell} style={{ color: row.covered ? 'var(--success-text-strong)' : 'var(--warning-text-2)' }}>
              {row.covered ? <CheckIcon size={15} color="var(--success-icon)" /> : <AlertTriangleIcon size={15} color="var(--warning-text-2)" />}
              {row.covered ? 'Covered' : 'Not covered'}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function PageHeader({ run }: { run?: Run | null }) {
  return (
    <div style={{ marginBottom: 18 }}>
      <div className="pageEyebrow">Coverage Matrix</div>
      <h1 className="pageTitle">Coverage Matrix</h1>
      {run && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: 'var(--text-muted)' }}>
          <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--text-body-2)' }}>{run.source_id}</span>
          {run.module && (
            <>
              <span>·</span>
              <span>{run.module}</span>
            </>
          )}
        </div>
      )}
    </div>
  );
}
