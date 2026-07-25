import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  downloadExcel,
  getExportStatus,
  getRun,
  uploadToJira,
  type ExportStatus,
  type JiraUploadResult,
  type Run,
} from '../api/client';
import { Button } from '../components/Button';
import { AlertTriangleIcon, CheckIcon, DownloadIcon, XIcon } from '../components/icons';
import { Modal } from '../components/Modal';
import { Spinner } from '../components/Spinner';
import { getLastRunId } from '../lib/lastRun';
import styles from './Export.module.css';

type UploadPhase = 'idle' | 'uploading' | 'results';

export function Export() {
  const { runId: paramRunId } = useParams();
  const runId = paramRunId || getLastRunId() || undefined;

  const [run, setRun] = useState<Run | null>(null);
  const [status, setStatus] = useState<ExportStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [confirmOpen, setConfirmOpen] = useState(false);
  const [phase, setPhase] = useState<UploadPhase>('idle');
  const [results, setResults] = useState<JiraUploadResult[]>([]);

  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  function reload() {
    if (!runId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    Promise.all([getRun(runId), getExportStatus(runId)])
      .then(([r, s]) => {
        setRun(r);
        setStatus(s);
        setLoadError(null);
      })
      .catch((e) => setLoadError(e instanceof Error ? e.message : 'Failed to load run'))
      .finally(() => setLoading(false));
  }

  useEffect(reload, [runId]);

  async function handleDownloadExcel() {
    if (!runId) return;
    setDownloading(true);
    setDownloadError(null);
    try {
      const { blob, filename } = await downloadExcel(runId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setDownloadError(e instanceof Error ? e.message : 'Download failed');
    } finally {
      setDownloading(false);
    }
  }

  async function handleConfirmUpload() {
    if (!runId) return;
    setConfirmOpen(false);
    setPhase('uploading');
    try {
      const r = await uploadToJira(runId);
      setResults(r);
      setPhase('results');
      reload(); // pick up persisted jira_key / any status change
    } catch {
      setPhase('idle');
    }
  }

  async function handleRetryFailed() {
    if (!runId) return;
    const failedIds = results.filter((r) => !r.success).map((r) => r.test_case_id);
    setPhase('uploading');
    try {
      const retried = await uploadToJira(runId, failedIds);
      const byId = new Map(retried.map((r) => [r.test_case_id, r]));
      setResults((prev) => prev.map((r) => byId.get(r.test_case_id) ?? r));
      setPhase('results');
      reload();
    } catch {
      setPhase('results');
    }
  }

  if (!runId || (!loading && !run)) {
    return (
      <div className="page">
        <PageHeader />
        <div className="pageMeta">
          {loadError ?? 'No run selected.'} <Link to="/">Start a generation run</Link>
        </div>
      </div>
    );
  }

  if (loading || !run || !status) {
    return (
      <div className="page">
        <PageHeader />
        <p className="pageMeta">Loading…</p>
      </div>
    );
  }

  return (
    <div className="page" style={{ maxWidth: 1000 }}>
      <PageHeader run={run} />

      {status.blocked && (
        <div className={styles.blockedBanner}>
          <AlertTriangleIcon size={17} color="var(--warning-text-2)" />
          <div>{status.reason}</div>
        </div>
      )}

      {!status.blocked && status.note && (
        <div className={styles.blockedBanner}>
          <AlertTriangleIcon size={17} color="var(--warning-text-2)" />
          <div>{status.note}</div>
        </div>
      )}

      {phase === 'idle' && (
        <div className={`card ${styles.actionsCard}`}>
          <div className={styles.actionRow}>
            <div>
              <div className={styles.actionTitle}>Download Excel</div>
              <div className={styles.actionSub}>{status.approved_count} approved test cases ready</div>
              {downloadError && <div className={styles.actionSub} style={{ color: 'var(--danger)' }}>{downloadError}</div>}
            </div>
            <Button variant="secondary" disabled={status.blocked || downloading} onClick={handleDownloadExcel}>
              <DownloadIcon size={15} /> {downloading ? 'Downloading…' : 'Download Excel'}
            </Button>
          </div>

          <div className={styles.divider} />

          <div className={styles.actionRow}>
            <div>
              <div className={styles.actionTitle}>Upload to Jira</div>
              <div className={styles.actionSub}>{status.approved_count} approved test cases ready</div>
            </div>
            <Button variant="primary" disabled={status.blocked} onClick={() => setConfirmOpen(true)}>
              Upload to Jira
            </Button>
          </div>
        </div>
      )}

      <Modal
        open={confirmOpen}
        onClose={() => setConfirmOpen(false)}
        title="Upload to Jira?"
        footer={
          <>
            <Button variant="secondary" onClick={() => setConfirmOpen(false)}>
              Cancel
            </Button>
            <Button variant="primary" onClick={handleConfirmUpload}>
              Confirm
            </Button>
          </>
        }
      >
        This will create {status.approved_count} test issues in Jira{run.source_type === 'jira' ? (
          <>
            , linked to <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>{run.source_id}</span>
          </>
        ) : null}
        . This cannot be undone.
      </Modal>

      {phase === 'uploading' && (
        <div className={`card ${styles.progressCard}`}>
          <Spinner size={28} />
          <div className={styles.progressText}>Uploading {status.approved_count} test cases to Jira…</div>
        </div>
      )}

      {phase === 'results' && (
        <ResultsCard results={results} run={run} onRetry={handleRetryFailed} onDone={() => setPhase('idle')} />
      )}
    </div>
  );
}

function ResultsCard({
  results,
  run,
  onRetry,
  onDone,
}: {
  results: JiraUploadResult[];
  run: Run;
  onRetry: () => void;
  onDone: () => void;
}) {
  const failCount = results.filter((r) => !r.success).length;
  const titleFor = (id: string) => run.test_cases.find((tc) => tc.id === id)?.title ?? id;

  return (
    <div className={`card ${styles.resultsCard}`}>
      <div className={styles.resultsHeadline}>
        {failCount === 0
          ? `All ${results.length} test cases uploaded successfully`
          : `${results.length - failCount} of ${results.length} uploaded successfully, ${failCount} failed`}
      </div>
      {failCount > 0 && <div className={styles.resultsSub}>Successful items were not re-uploaded.</div>}

      <div className={styles.resultsList}>
        {results.map((r) => (
          <div key={r.test_case_id} className={`${styles.resultRow} ${r.success ? styles.resultOk : styles.resultFail}`}>
            {r.success ? <CheckIcon size={15} color="var(--success-icon)" /> : <XIcon size={15} color="var(--warning-text-2)" />}
            <span className={styles.resultId}>{r.test_case_id.split('::').pop()}</span>
            <span className={styles.resultTitle}>{titleFor(r.test_case_id)}</span>
            {r.success ? (
              <a href={r.jira_url ?? '#'} target="_blank" rel="noreferrer">
                View {r.jira_key}
              </a>
            ) : (
              <span className={styles.resultReason}>{r.reason}</span>
            )}
          </div>
        ))}
      </div>

      <div style={{ display: 'flex', gap: 8 }}>
        {failCount > 0 && (
          <Button variant="primary" onClick={onRetry}>
            Retry failed only
          </Button>
        )}
        <Button variant="secondary" onClick={onDone}>
          Done
        </Button>
      </div>
    </div>
  );
}

function PageHeader({ run }: { run?: Run | null }) {
  return (
    <div style={{ marginBottom: 20 }}>
      <div className="pageEyebrow">Export</div>
      <h1 className="pageTitle">Export Approved Test Cases</h1>
      {run && (
        <div className="pageMeta">
          {run.source_id}
          {run.module ? ` · ${run.module}` : ''}
        </div>
      )}
    </div>
  );
}
