import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { createDocRun, createJiraRun, detectChangedText, getRun, getRunStatus, listModules, type Run, type RunStep } from '../api/client';
import { Button } from '../components/Button';
import { AlertCircleIcon, AlertTriangleIcon, CheckIcon, ChevronDownIcon, UploadCloudIcon } from '../components/icons';
import { setLastRunId } from '../lib/lastRun';
import styles from './Generate.module.css';

type Tab = 'jira' | 'doc';
type Phase = 'idle' | 'submitting' | 'in_progress' | 'done' | 'failed';

const TICKET_KEY_RE = /^[A-Za-z][A-Za-z0-9]*-\d+$/;
const POLL_MS = 2000;

export function Generate() {
  const [tab, setTab] = useState<Tab>('jira');
  const [ticketKey, setTicketKey] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [module, setModule] = useState('');
  const [modules, setModules] = useState<string[]>([]);
  const [scope, setScope] = useState('');
  const [scopeAutoFilled, setScopeAutoFilled] = useState(false);
  const [detecting, setDetecting] = useState(false);
  const [idPrefix, setIdPrefix] = useState('');
  const [phase, setPhase] = useState<Phase>('idle');
  const [run, setRun] = useState<Run | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const pollRef = useRef<number | null>(null);

  useEffect(() => {
    listModules().then(setModules).catch(() => setModules([]));
  }, []);

  useEffect(() => {
    return () => {
      if (pollRef.current) window.clearInterval(pollRef.current);
    };
  }, []);

  const ticketKeyTouched = ticketKey.trim().length > 0;
  const ticketKeyValid = TICKET_KEY_RE.test(ticketKey.trim());
  const canSubmit = tab === 'jira' ? ticketKeyValid : !!file && !fileError;

  function handleFileChange(f: File | null) {
    setFile(f);
    setFileError(null);
    if (scopeAutoFilled) {
      setScope('');
      setScopeAutoFilled(false);
    }
    if (f) {
      const suffix = f.name.toLowerCase().slice(f.name.lastIndexOf('.'));
      if (suffix !== '.pdf' && suffix !== '.docx') {
        setFileError(`${f.name} — accepted: PDF, DOCX`);
        return;
      }
      if (suffix === '.docx') {
        setDetecting(true);
        detectChangedText(f)
          .then(({ detected_text }) => {
            // Only pre-fill if the user hasn't already typed their own scope —
            // this is a suggestion, never a silent override.
            if (detected_text && !scope.trim()) {
              setScope(detected_text);
              setScopeAutoFilled(true);
            }
          })
          .catch(() => {})
          .finally(() => setDetecting(false));
      }
    }
  }

  function startPolling(runId: string) {
    pollRef.current = window.setInterval(async () => {
      try {
        const status = await getRunStatus(runId);
        setRun((prev) => (prev ? { ...prev, status: status.status, steps: status.steps, error: status.error } : prev));
        if (status.status === 'done') {
          if (pollRef.current) window.clearInterval(pollRef.current);
          const full = await getRun(runId);
          setRun(full);
          setLastRunId(runId);
          setPhase('done');
        } else if (status.status === 'failed') {
          if (pollRef.current) window.clearInterval(pollRef.current);
          setPhase('failed');
        }
      } catch {
        // transient network error — keep polling, next tick may succeed
      }
    }, POLL_MS);
  }

  async function handleSubmit() {
    setSubmitError(null);
    setPhase('submitting');
    try {
      const created =
        tab === 'jira'
          ? await createJiraRun(ticketKey.trim(), module || undefined, scope.trim() || undefined, idPrefix.trim() || undefined)
          : await createDocRun(file!, module || undefined, scope.trim() || undefined, idPrefix.trim() || undefined);
      setRun(created);
      setPhase('in_progress');
      startPolling(created.id);
    } catch (e) {
      setSubmitError(e instanceof Error ? e.message : 'Failed to start run');
      setPhase('idle');
    }
  }

  function handleRetry() {
    setPhase('idle');
    setRun(null);
  }

  return (
    <div className="page">
      <div style={{ marginBottom: 40 }}>
        <div className="pageEyebrow">Generate</div>
        <h1 className="pageTitle">Start a Test Case Generation Run</h1>
        <div className="pageMeta">Generate categorized test cases from a Jira ticket or a design doc.</div>
      </div>

      <div className={styles.wrap}>
        {(phase === 'in_progress' || phase === 'done') && run ? (
          <RunProgress run={run} phase={phase} />
        ) : phase === 'failed' && run ? (
          <RunFailed run={run} onRetry={handleRetry} />
        ) : (
          <div className={`card ${styles.formCard}`}>
            <div className={styles.cardTitle}>New Generation Run</div>

            <div className={styles.tabs}>
              <button className={`${styles.tab} ${tab === 'jira' ? styles.tabActive : ''}`} onClick={() => setTab('jira')}>
                From Jira Ticket
              </button>
              <button className={`${styles.tab} ${tab === 'doc' ? styles.tabActive : ''}`} onClick={() => setTab('doc')}>
                Upload Document
              </button>
            </div>

            {tab === 'jira' ? (
              <div className={styles.field}>
                <label className="label">Jira Ticket Key</label>
                <div className={styles.inputWrap}>
                  <input
                    type="text"
                    placeholder="e.g. PROJ-123"
                    value={ticketKey}
                    onChange={(e) => setTicketKey(e.target.value)}
                    className="textInput"
                    style={{
                      fontFamily: 'var(--font-mono)',
                      paddingRight: ticketKeyTouched ? 36 : undefined,
                      borderColor: ticketKeyTouched ? (ticketKeyValid ? 'var(--success)' : 'var(--danger)') : undefined,
                      background: ticketKeyTouched && !ticketKeyValid ? 'var(--danger-bg)' : undefined,
                    }}
                  />
                  {ticketKeyTouched && (
                    <span className={styles.inputIcon}>
                      {ticketKeyValid ? <CheckIcon size={16} color="var(--success)" /> : <AlertCircleIcon size={16} color="var(--danger)" />}
                    </span>
                  )}
                </div>
                {ticketKeyTouched && !ticketKeyValid && (
                  <div className={styles.errorText}>
                    <span>Invalid key format — expected PROJECT-123</span>
                  </div>
                )}
              </div>
            ) : (
              <div className={styles.field}>
                <label className="label">Document</label>
                <label
                  className={`${styles.dropzone} ${fileError ? styles.dropzoneError : file ? styles.dropzoneOk : ''}`}
                >
                  <input
                    type="file"
                    accept=".pdf,.docx"
                    style={{ display: 'none' }}
                    onChange={(e) => handleFileChange(e.target.files?.[0] ?? null)}
                  />
                  {fileError ? (
                    <>
                      <AlertCircleIcon size={22} color="var(--danger)" />
                      <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--danger)' }}>File type not supported</div>
                      <div style={{ fontSize: 12, color: 'var(--danger-text-2)' }}>{fileError}</div>
                    </>
                  ) : file ? (
                    <>
                      <CheckIcon size={22} color="var(--success)" />
                      <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-heading)' }}>{file.name}</div>
                      <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Click to choose a different file</div>
                    </>
                  ) : (
                    <>
                      <UploadCloudIcon size={22} color="var(--text-faint)" />
                      <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-body-2)' }}>Click to upload a PDF or DOCX</div>
                    </>
                  )}
                </label>
                {fileError && <div className={styles.errorText}>Try again with a supported file type.</div>}
              </div>
            )}

            <div className={styles.field}>
              <label className="label">
                Module <span style={{ fontWeight: 400, color: 'var(--text-disabled)' }}>(optional)</span>
              </label>
              <div style={{ position: 'relative' }}>
                <select
                  className={styles.select}
                  value={module}
                  onChange={(e) => setModule(e.target.value)}
                  style={{ appearance: 'none' }}
                >
                  <option value="">Select module…</option>
                  {modules.map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))}
                </select>
                <span style={{ position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none' }}>
                  <ChevronDownIcon size={14} color="var(--text-faint)" />
                </span>
              </div>
            </div>

            <div className={styles.field}>
              <label className="label">
                Focus / Scope <span style={{ fontWeight: 400, color: 'var(--text-disabled)' }}>(optional)</span>
              </label>
              <textarea
                className="textInput"
                rows={3}
                style={{ resize: 'vertical', fontFamily: 'inherit' }}
                placeholder="e.g. Only test the changes to the retry limit and lockout duration — leave blank to test the entire document/ticket."
                value={scope}
                onChange={(e) => {
                  setScope(e.target.value);
                  setScopeAutoFilled(false);
                }}
              />
              {detecting && <div className="pageMeta" style={{ marginTop: 4 }}>Scanning document for marked changes…</div>}
              {scopeAutoFilled && !detecting && (
                <div className="pageMeta" style={{ marginTop: 4 }}>
                  Detected from red text in this document — edit or clear as needed.
                </div>
              )}
            </div>

            <div className={styles.field}>
              <label className="label">
                Test Case ID Prefix <span style={{ fontWeight: 400, color: 'var(--text-disabled)' }}>(optional)</span>
              </label>
              <input
                type="text"
                className="textInput"
                style={{ fontFamily: 'var(--font-mono)' }}
                placeholder="e.g. DEMND002_Reg_TC_ — leave blank to auto-generate from the module (TC_MODULE_001)"
                value={idPrefix}
                onChange={(e) => setIdPrefix(e.target.value)}
              />
              <div className="pageMeta" style={{ marginTop: 4 }}>
                Used exactly as typed — numbers are appended directly after it, continuing from anything already using this prefix.
              </div>
            </div>

            {submitError && (
              <div className={styles.errorText} style={{ marginBottom: 12 }}>
                {submitError}
              </div>
            )}

            <Button variant="primary" full disabled={!canSubmit || phase === 'submitting'} onClick={handleSubmit}>
              {phase === 'submitting' ? 'Starting…' : 'Generate Test Cases'}
            </Button>

            <div className={styles.footerLink}>
              <Link to="/history">View past generation runs</Link>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function stepStatusLabel(step: RunStep): string {
  if (step.status === 'done') return 'Done';
  if (step.status === 'pending') return 'Waiting';
  // in_progress — only "Generating test cases" and "Checking coverage" loop
  // per-condition and report a real fraction; decomposition is one LLM call
  // and retrieval is local/near-instant, so neither has anything to divide.
  return step.total > 0 ? `In progress… (${step.current} of ${step.total} conditions)` : 'In progress…';
}

function RunProgress({ run, phase }: { run: Run; phase: Phase }) {
  return (
    <div className={`card ${styles.formCard}`}>
      <div className={styles.cardTitle}>New Generation Run</div>
      <div style={{ marginBottom: 18 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12.5, color: 'var(--text-muted)' }}>
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
            Test Case ID prefix: <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-body-2)', fontWeight: 500 }}>{run.id_prefix}</span>
          </div>
        )}
      </div>

      <div className={styles.steps}>
        {run.steps.map((step, i) => (
          <div key={step.name}>
            <div className={`${styles.step} ${step.status === 'in_progress' ? styles.stepActive : ''}`}>
              <div
                className={`${styles.stepDot} ${
                  step.status === 'done' ? styles.stepDotDone : step.status === 'in_progress' ? styles.stepDotActive : styles.stepDotPending
                }`}
              >
                {step.status === 'done' && <CheckIcon size={12} color="var(--bg-white)" />}
                {step.status === 'in_progress' && <span className={styles.stepDotInner} />}
              </div>
              <div>
                <div
                  className={`${styles.stepName} ${
                    step.status === 'in_progress' ? styles.stepNameActive : step.status === 'pending' ? styles.stepNamePending : ''
                  }`}
                >
                  {step.name}
                </div>
                <div className={styles.stepSub} style={{ color: step.status === 'in_progress' ? 'var(--brand)' : step.status === 'done' ? 'var(--success-icon)' : 'var(--text-disabled)' }}>
                  {stepStatusLabel(step)}
                </div>
                {step.status === 'in_progress' && step.total > 0 && (
                  <div className={styles.progressTrack}>
                    <div className={styles.progressFill} style={{ width: `${Math.round((step.current / step.total) * 100)}%` }} />
                  </div>
                )}
              </div>
            </div>
            {i < run.steps.length - 1 && <div className={styles.stepConnector} />}
          </div>
        ))}
      </div>

      {phase === 'done' && (
        <div className={styles.resultBanner} style={{ marginTop: 16 }}>
          <CheckIcon size={17} color="var(--success-icon)" />
          <div>
            <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--success-text-strong)' }}>
              Generated {run.test_cases.length} test cases across {run.conditions.length} conditions
            </div>
            <div style={{ fontSize: 12.5, color: 'var(--success-text)', marginTop: 2 }}>
              {run.gaps.length > 0 ? `${run.gaps.length} coverage gap(s) to review` : 'All 7 categories covered'}
            </div>
          </div>
        </div>
      )}

      {phase === 'done' ? (
        <Link to={`/review/${run.id}`}>
          <Button variant="primary" full>
            Review generated test cases
          </Button>
        </Link>
      ) : (
        <div className={styles.footerLink}>
          <a href="#" style={{ color: 'var(--danger)' }} onClick={(e) => e.preventDefault()}>
            Cancel run
          </a>
        </div>
      )}
    </div>
  );
}

function RunFailed({ run, onRetry }: { run: Run; onRetry: () => void }) {
  return (
    <div className={`card ${styles.formCard}`}>
      <div className={styles.cardTitle}>New Generation Run</div>
      <div className={styles.errorBanner}>
        <AlertCircleIcon size={17} color="var(--danger)" />
        <div>
          <div className={styles.errorBannerTitle}>Generation failed</div>
          <div className={styles.errorBannerText}>{run.error || 'An unexpected error occurred.'}</div>
        </div>
      </div>
      <Button variant="danger" full onClick={onRetry}>
        <AlertTriangleIcon size={14} /> Retry
      </Button>
      <div className={styles.footerLink}>
        <Link to="/history">View past generation runs</Link>
      </div>
    </div>
  );
}
