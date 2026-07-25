import { useEffect, useState } from 'react';
import { browseLibrary, listLibrarySessions, listModules, type LibraryHit, type LibrarySession } from '../api/client';
import { ChevronDownIcon } from '../components/icons';
import { ImportTestCasesCard } from '../components/ImportTestCasesCard';
import { Pill } from '../components/Pill';
import styles from './TestCaseLibrary.module.css';

function formatDate(iso: string): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}

function priorityTone(priority: string): 'danger' | 'warning' | 'neutral' {
  if (priority === 'High') return 'danger';
  if (priority === 'Medium') return 'warning';
  return 'neutral';
}

function CaseRow({ hit, showSessionTag }: { hit: LibraryHit; showSessionTag?: boolean }) {
  const [open, setOpen] = useState(false);

  return (
    <div className={styles.caseCard}>
      <button type="button" className={styles.caseSummary} onClick={() => setOpen((o) => !o)}>
        <ChevronDownIcon
          size={13}
          color="var(--text-faint)"
          className={open ? styles.chevron : `${styles.chevron} ${styles.chevronClosed}`}
        />
        <span className={styles.rowId}>{hit.id}</span>
        <span className={styles.rowTitle}>{hit.metadata.title}</span>
        {hit.metadata.priority && <Pill tone={priorityTone(hit.metadata.priority)}>{hit.metadata.priority}</Pill>}
        {hit.metadata.module && <span className={styles.rowMeta}>{hit.metadata.module}</span>}
        {showSessionTag && hit.metadata.session_label && (
          <span className={styles.sessionTag}>{hit.metadata.session_label}</span>
        )}
      </button>

      {open && (
        <div className={styles.caseDetail}>
          <div className={styles.detailField}>
            <div className={styles.detailLabel}>Description</div>
            <div className={styles.detailValue}>{hit.description || '—'}</div>
          </div>
          <div className={styles.detailField}>
            <div className={styles.detailLabel}>Pre-conditions</div>
            <div className={styles.detailValue}>{hit.preconditions || '—'}</div>
          </div>
          <div className={styles.detailField}>
            <div className={styles.detailLabel}>Steps</div>
            {hit.steps.length === 0 ? (
              <div className={styles.detailValue}>—</div>
            ) : (
              <ol className={styles.stepsList}>
                {hit.steps.map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ol>
            )}
          </div>
          <div className={styles.detailField}>
            <div className={styles.detailLabel}>Expected Results</div>
            <div className={styles.detailValue}>{hit.expected_result || '—'}</div>
          </div>
        </div>
      )}
    </div>
  );
}

function SessionGroup({
  session,
  open,
  onToggle,
  cases,
  loading,
}: {
  session: LibrarySession;
  open: boolean;
  onToggle: () => void;
  cases: LibraryHit[] | undefined;
  loading: boolean;
}) {
  return (
    <div className={`card ${styles.sessionCard}`}>
      <button type="button" className={styles.sessionHeader} onClick={onToggle}>
        <ChevronDownIcon size={14} color="var(--text-faint)" className={open ? styles.chevron : `${styles.chevron} ${styles.chevronClosed}`} />
        <span className={styles.sessionLabel}>{session.session_label}</span>
        <span className={styles.sessionMeta}>
          {session.count} case{session.count === 1 ? '' : 's'} · {formatDate(session.session_created_at)}
        </span>
      </button>
      {open && (
        <div className={styles.sessionBody}>
          {loading ? (
            <div className="pageMeta">Loading…</div>
          ) : !cases || cases.length === 0 ? (
            <div className="pageMeta">No cases found.</div>
          ) : (
            cases.map((hit) => <CaseRow key={hit.id} hit={hit} />)
          )}
        </div>
      )}
    </div>
  );
}

export function TestCaseLibrary() {
  const [query, setQuery] = useState('');
  const [moduleFilter, setModuleFilter] = useState('');
  const [modules, setModules] = useState<string[]>([]);

  const [sessions, setSessions] = useState<LibrarySession[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(true);
  const [openSessions, setOpenSessions] = useState<Set<string>>(new Set());
  const [sessionCases, setSessionCases] = useState<Record<string, LibraryHit[]>>({});
  const [loadingSessions, setLoadingSessions] = useState<Set<string>>(new Set());

  const [searchHits, setSearchHits] = useState<LibraryHit[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);

  const isFiltering = query.trim() !== '' || moduleFilter !== '';

  function refreshModules() {
    listModules().then(setModules).catch(() => setModules([]));
  }

  function refreshSessions() {
    setSessionsLoading(true);
    listLibrarySessions()
      .then(setSessions)
      .catch(() => setSessions([]))
      .finally(() => setSessionsLoading(false));
  }

  useEffect(() => {
    refreshModules();
    refreshSessions();
  }, []);

  useEffect(() => {
    if (!isFiltering) return;
    setSearchLoading(true);
    const t = setTimeout(() => {
      browseLibrary({ q: query || undefined, module: moduleFilter || undefined, n: 30 })
        .then(setSearchHits)
        .catch(() => setSearchHits([]))
        .finally(() => setSearchLoading(false));
    }, 300);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query, moduleFilter, isFiltering]);

  function toggleSession(session: LibrarySession) {
    const id = session.session_id;
    setOpenSessions((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
    if (!sessionCases[id]) {
      setLoadingSessions((prev) => new Set(prev).add(id));
      browseLibrary({ sessionId: id, n: 500 })
        .then((hits) => setSessionCases((prev) => ({ ...prev, [id]: hits })))
        .catch(() => setSessionCases((prev) => ({ ...prev, [id]: [] })))
        .finally(() =>
          setLoadingSessions((prev) => {
            const next = new Set(prev);
            next.delete(id);
            return next;
          }),
        );
    }
  }

  const uploadedSessions = sessions.filter((s) => s.source === 'library');
  const generatedSessions = sessions.filter((s) => s.source === 'generated');

  return (
    <div className="page" style={{ maxWidth: 1200 }}>
      <div style={{ marginBottom: 18 }}>
        <div className="pageEyebrow">Test Case Library</div>
        <h1 className="pageTitle">Old Test Case Library</h1>
        <div className="pageMeta">
          Import your team's existing test cases to seed the style/pattern library that generation draws on.
        </div>
      </div>

      <div style={{ marginBottom: 20 }}>
        <ImportTestCasesCard
          onImported={() => {
            refreshModules();
            refreshSessions();
          }}
        />
      </div>

      <div className={`card ${styles.toolbar}`}>
        <input
          type="text"
          className={styles.searchInput}
          placeholder="Search test cases…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <div style={{ position: 'relative' }}>
          <select
            className={styles.select}
            value={moduleFilter}
            onChange={(e) => setModuleFilter(e.target.value)}
            style={{ paddingRight: 26 }}
          >
            <option value="">All modules</option>
            {modules.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
          <span style={{ position: 'absolute', right: 8, top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none' }}>
            <ChevronDownIcon size={12} color="var(--text-faint)" />
          </span>
        </div>
      </div>

      {isFiltering ? (
        searchLoading ? (
          <div className="pageMeta">Loading…</div>
        ) : searchHits.length === 0 ? (
          <div className={styles.emptyState}>
            <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-body-2)' }}>No test cases found</div>
            <div className="pageMeta">Adjust your search or module filter.</div>
          </div>
        ) : (
          <div className={styles.list}>
            {searchHits.map((hit) => (
              <CaseRow key={hit.id} hit={hit} showSessionTag />
            ))}
          </div>
        )
      ) : sessionsLoading ? (
        <div className="pageMeta">Loading…</div>
      ) : sessions.length === 0 ? (
        <div className={styles.emptyState}>
          <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-body-2)' }}>No test cases yet</div>
          <div className="pageMeta">Import a CSV/XLSX above, or run a generation and approve some cases.</div>
        </div>
      ) : (
        <>
          <div className={styles.sectionHeading}>
            Uploaded Test Cases <span className={styles.sectionHeadingCount}>({uploadedSessions.length})</span>
          </div>
          {uploadedSessions.length === 0 ? (
            <div className="pageMeta" style={{ marginBottom: 20 }}>
              None yet — import a CSV/XLSX above.
            </div>
          ) : (
            <div className={styles.sessionList} style={{ marginBottom: 24 }}>
              {uploadedSessions.map((s) => (
                <SessionGroup
                  key={s.session_id}
                  session={s}
                  open={openSessions.has(s.session_id)}
                  onToggle={() => toggleSession(s)}
                  cases={sessionCases[s.session_id]}
                  loading={loadingSessions.has(s.session_id)}
                />
              ))}
            </div>
          )}

          <div className={styles.sectionHeading}>
            Generated Test Cases <span className={styles.sectionHeadingCount}>({generatedSessions.length})</span>
          </div>
          {generatedSessions.length === 0 ? (
            <div className="pageMeta">None yet — approve cases from a generation run to see them here.</div>
          ) : (
            <div className={styles.sessionList}>
              {generatedSessions.map((s) => (
                <SessionGroup
                  key={s.session_id}
                  session={s}
                  open={openSessions.has(s.session_id)}
                  onToggle={() => toggleSession(s)}
                  cases={sessionCases[s.session_id]}
                  loading={loadingSessions.has(s.session_id)}
                />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
