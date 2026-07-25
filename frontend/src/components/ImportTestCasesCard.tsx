import { useState } from 'react';
import { importLibrary } from '../api/client';
import { AlertCircleIcon, UploadCloudIcon } from './icons';
import styles from './ImportTestCasesCard.module.css';

const ACCEPTED = ['.csv', '.xlsx', '.xlsm'];

// Shared by Screen 5 (Test Case Library) and Settings — same import path
// (POST /library/import), which is also what generation's "style examples"
// retrieval draws on. Uploading here isn't a separate feature from the
// Library screen's upload, just a second entry point to the same thing.
export function ImportTestCasesCard({ onImported }: { onImported?: () => void }) {
  const [importError, setImportError] = useState<string | null>(null);
  const [importResult, setImportResult] = useState<{ imported: number; total_in_library: number } | null>(null);
  const [importing, setImporting] = useState(false);

  async function handleFile(file: File) {
    setImportError(null);
    setImportResult(null);
    const suffix = file.name.toLowerCase().slice(file.name.lastIndexOf('.'));
    if (!ACCEPTED.includes(suffix)) {
      setImportError(`${file.name} — accepted: CSV, XLSX`);
      return;
    }
    setImporting(true);
    try {
      const result = await importLibrary(file);
      setImportResult(result);
      onImported?.();
    } catch (e) {
      setImportError(e instanceof Error ? e.message : 'Import failed');
    } finally {
      setImporting(false);
    }
  }

  return (
    <div className={`card ${styles.card}`}>
      <div className={styles.title}>Import test cases</div>
      <div className={styles.sub}>
        Columns: Test Case ID, Test Scenario, Description, Pre-conditions, Steps, Expected Results, Priority (Module optional) —
        common header variants (e.g. "Title", "Preconditions", "Test Steps") are matched automatically.
      </div>

      <label className={`${styles.dropzone} ${importError ? styles.dropzoneError : ''}`}>
        <input
          type="file"
          accept={ACCEPTED.join(',')}
          style={{ display: 'none' }}
          disabled={importing}
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) handleFile(f);
            e.target.value = '';
          }}
        />
        {importError ? (
          <>
            <AlertCircleIcon size={20} color="var(--danger)" />
            <div>
              <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--danger)' }}>File type not supported</div>
              <div style={{ fontSize: 12, color: 'var(--danger-text-2)' }}>{importError}</div>
            </div>
          </>
        ) : (
          <>
            <UploadCloudIcon size={20} color="var(--text-faint)" />
            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-body-2)' }}>
              {importing ? 'Importing…' : 'Click to upload a CSV or XLSX'}
            </div>
          </>
        )}
      </label>

      {importResult && (
        <div className={styles.resultBanner}>
          <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--success-text-strong)' }}>
            Imported {importResult.imported} test cases
          </span>
          <span style={{ fontSize: 12.5, color: 'var(--success-text)' }}>— {importResult.total_in_library} total in library</span>
        </div>
      )}
    </div>
  );
}
