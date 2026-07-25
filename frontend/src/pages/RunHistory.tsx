import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { listRuns, type Run, type RunStepStatus } from '../api/client';
import { ClockIcon } from '../components/icons';
import { Pill } from '../components/Pill';
import { setLastRunId } from '../lib/lastRun';
import styles from './RunHistory.module.css';

const STATUS_TONE: Record<RunStepStatus, 'success' | 'brand' | 'danger' | 'neutral'> = {
  done: 'success',
  in_progress: 'brand',
  failed: 'danger',
  pending: 'neutral',
};

const STATUS_LABEL: Record<RunStepStatus, string> = {
  done: 'Done',
  in_progress: 'In progress',
  failed: 'Failed',
  pending: 'Pending',
};

export function RunHistory() {
  const navigate = useNavigate();
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listRuns()
      .then(setRuns)
      .finally(() => setLoading(false));
  }, []);

  function openRun(run: Run) {
    setLastRunId(run.id);
    navigate(run.status === 'done' ? `/review/${run.id}` : `/`);
  }

  return (
    <div className="page" style={{ maxWidth: 900 }}>
      <div style={{ marginBottom: 20 }}>
        <div className="pageEyebrow">Run History</div>
        <h1 className="pageTitle">Past Generation Runs</h1>
        <div className="pageMeta">Reopen a completed run to keep reviewing its test cases.</div>
      </div>

      {loading ? (
        <p className="pageMeta">Loading…</p>
      ) : runs.length === 0 ? (
        <div className={`card ${styles.emptyState}`}>
          <ClockIcon size={28} color="var(--text-faint)" />
          <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-body-2)' }}>No runs yet</div>
          <div className="pageMeta">Runs you start from the Generate screen will show up here.</div>
        </div>
      ) : (
        <div className={styles.list}>
          {runs.map((run) => {
            const approved = run.test_cases.filter((tc) => tc.status === 'approved').length;
            return (
              <div key={run.id} className={`card ${styles.row}`} onClick={() => openRun(run)}>
                <div className={styles.rowMain}>
                  <div className={styles.rowSource}>
                    {run.source_id}
                    {run.module ? ` · ${run.module}` : ''}
                  </div>
                  <div className={styles.rowMeta}>{new Date(run.created_at).toLocaleString()}</div>
                </div>
                {run.status === 'done' && (
                  <div className={styles.rowCounts}>
                    {run.test_cases.length} cases · {approved} approved
                  </div>
                )}
                <Pill tone={STATUS_TONE[run.status]}>{STATUS_LABEL[run.status]}</Pill>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
