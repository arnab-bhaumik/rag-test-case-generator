// Typed fetch wrappers for the FastAPI backend (api/main.py).

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

export type Category =
  | 'Positive'
  | 'Negative'
  | 'Boundary'
  | 'Edge'
  | 'Security'
  | 'Integration'
  | 'Data Validation';

export type Priority = 'High' | 'Medium' | 'Low';
export type ReviewStatus = 'unreviewed' | 'approved' | 'rejected';
export type RunStepStatus = 'pending' | 'in_progress' | 'done' | 'failed';

export interface Condition {
  id: string;
  requirement_id: string;
  text: string;
  ac_ref: string | null;
  order: number;
}

export interface TestCase {
  id: string;
  title: string; // shown in the UI as "Test Scenario"
  description: string;
  preconditions: string;
  steps: string[];
  expected_result: string;
  module: string | null;
  priority: Priority;
  category: Category | null;
  source: string;
  trace: string | null;
  status: ReviewStatus;
  grounded: boolean;
  manually_verified: boolean;
  edited: boolean;
  condition_id: string | null;
  jira_key: string | null;
}

export interface RunStep {
  name: string;
  status: RunStepStatus;
  current: number; // conditions processed so far — only meaningful when total > 0
  total: number; // 0 means this step isn't divisible (e.g. decomposition, retrieval)
}

export interface CoverageGap {
  category: Category;
  acknowledged: boolean;
}

export interface Run {
  id: string;
  source_type: 'jira' | 'doc';
  source_id: string;
  module: string | null;
  scope: string | null;
  id_prefix: string | null;
  status: RunStepStatus;
  steps: RunStep[];
  error: string | null;
  created_at: string;
  requirement_text: string;
  conditions: Condition[];
  test_cases: TestCase[];
  gaps: CoverageGap[];
}

export interface RunStatus {
  id: string;
  status: RunStepStatus;
  steps: RunStep[];
  error: string | null;
}

export interface LibraryHit {
  id: string;
  document: string;
  metadata: {
    title: string;
    module: string;
    priority: string;
    source: string;
    session_id: string;
    session_label: string;
    session_created_at: string;
  };
  distance?: number;
  // Parsed back out of `document` server-side — the full case content.
  description: string;
  preconditions: string;
  steps: string[];
  expected_result: string;
}

export interface LibrarySession {
  session_id: string;
  session_label: string;
  session_created_at: string;
  source: string; // "library" (uploaded) | "generated"
  count: number;
}

export interface RTMRow {
  condition_id: string;
  ac_ref: string | null;
  condition_text: string;
  linked_test_case_ids: string[];
  covered: boolean;
}

export interface Coverage {
  rtm: RTMRow[];
  gaps: CoverageGap[];
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, init);
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
  return res.json() as Promise<T>;
}

function postJson<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

// --- Runs (Screen 1 — Generate) ---

export function createJiraRun(ticketKey: string, module?: string, scope?: string, idPrefix?: string): Promise<Run> {
  const form = new FormData();
  form.set('source_type', 'jira');
  form.set('ticket_key', ticketKey);
  if (module) form.set('module', module);
  if (scope) form.set('scope', scope);
  if (idPrefix) form.set('id_prefix', idPrefix);
  return request<Run>('/runs', { method: 'POST', body: form });
}

export function createDocRun(file: File, module?: string, scope?: string, idPrefix?: string): Promise<Run> {
  const form = new FormData();
  form.set('source_type', 'doc');
  form.set('file', file);
  if (module) form.set('module', module);
  if (scope) form.set('scope', scope);
  if (idPrefix) form.set('id_prefix', idPrefix);
  return request<Run>('/runs', { method: 'POST', body: form });
}

// Scans an uploaded DOCX for red-marked text (a common convention for design
// docs reused across releases) — used to pre-fill the Scope box, never to
// silently filter what gets generated.
export function detectChangedText(file: File): Promise<{ detected_text: string }> {
  const form = new FormData();
  form.set('file', file);
  return request('/documents/detect-changes', { method: 'POST', body: form });
}

export function getRun(runId: string): Promise<Run> {
  return request<Run>(`/runs/${runId}`);
}

export function getRunStatus(runId: string): Promise<RunStatus> {
  return request<RunStatus>(`/runs/${runId}/status`);
}

export function listRuns(): Promise<Run[]> {
  return request<Run[]>('/runs');
}

// --- Test Case Library (Screen 5) ---

export function importLibrary(file: File): Promise<{ imported: number; total_in_library: number }> {
  const form = new FormData();
  form.set('file', file);
  return request('/library/import', { method: 'POST', body: form });
}

export function browseLibrary(opts: { q?: string; module?: string; sessionId?: string; n?: number } = {}): Promise<LibraryHit[]> {
  const params = new URLSearchParams();
  if (opts.q) params.set('q', opts.q);
  if (opts.module) params.set('module', opts.module);
  if (opts.sessionId) params.set('session_id', opts.sessionId);
  if (opts.n) params.set('n', String(opts.n));
  const qs = params.toString();
  return request<LibraryHit[]>(`/library${qs ? `?${qs}` : ''}`);
}

export function listLibrarySessions(): Promise<LibrarySession[]> {
  return request<LibrarySession[]>('/library/sessions');
}

// --- Test Cases (Screen 2 — Review Queue) ---

export interface TestCaseUpdate {
  id?: string;
  title?: string;
  description?: string;
  preconditions?: string;
  steps?: string[];
  expected_result?: string;
  priority?: Priority;
  manually_verified?: boolean;
  status?: 'unreviewed'; // only revert-to-unreviewed goes through PATCH; approve/reject go through bulk-* below
}

export function patchTestCase(id: string, update: TestCaseUpdate): Promise<TestCase> {
  return request<TestCase>(`/test-cases/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(update),
  });
}

export function bulkApprove(ids: string[]): Promise<{ approved: TestCase[]; blocked: string[] }> {
  return postJson('/test-cases/bulk-approve', { ids });
}

export function bulkReject(ids: string[]): Promise<{ rejected: TestCase[] }> {
  return postJson('/test-cases/bulk-reject', { ids });
}

export function regenerateTestCase(id: string): Promise<TestCase[]> {
  return request<TestCase[]>(`/test-cases/${id}/regenerate`, { method: 'POST' });
}

// --- Coverage (Screen 3 — Coverage Matrix, and gap actions on Screen 2) ---

export function getRunCoverage(runId: string): Promise<Coverage> {
  return request<Coverage>(`/runs/${runId}/coverage`);
}

export function acknowledgeGap(runId: string, category: Category): Promise<CoverageGap> {
  return request<CoverageGap>(`/runs/${runId}/gaps/${encodeURIComponent(category)}/acknowledge`, { method: 'POST' });
}

export function generateGap(runId: string, category: Category): Promise<TestCase[]> {
  return request<TestCase[]>(`/runs/${runId}/gaps/${encodeURIComponent(category)}/generate`, { method: 'POST' });
}

// --- Export (Screen 4) ---

export interface ExportStatus {
  approved_count: number;
  blocked: boolean;
  reason: string | null;
  note: string | null; // non-blocking — e.g. "N cases still need verification"
}

export interface JiraUploadResult {
  test_case_id: string;
  success: boolean;
  jira_key: string | null;
  jira_url: string | null;
  reason: string | null;
}

export function getExportStatus(runId: string): Promise<ExportStatus> {
  return request<ExportStatus>(`/export/${runId}/status`);
}

export async function downloadExcel(runId: string): Promise<{ blob: Blob; filename: string }> {
  const res = await fetch(`${API_BASE}/export/excel`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ run_id: runId }),
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
  const disposition = res.headers.get('Content-Disposition') ?? '';
  const match = disposition.match(/filename="?([^"]+)"?/);
  return { blob: await res.blob(), filename: match?.[1] ?? `${runId}_test_cases.xlsx` };
}

export function uploadToJira(runId: string, testCaseIds?: string[]): Promise<JiraUploadResult[]> {
  return postJson('/export/jira', { run_id: runId, test_case_ids: testCaseIds ?? null });
}

// --- Modules (shared dropdown/filter options, and full CRUD on Settings) ---

export function listModules(): Promise<string[]> {
  return request<string[]>('/modules');
}

export function createModule(name: string): Promise<string[]> {
  return postJson('/modules', { name });
}

export function deleteModule(name: string): Promise<string[]> {
  return request<string[]>(`/modules/${encodeURIComponent(name)}`, { method: 'DELETE' });
}

export function renameModule(name: string, newName: string): Promise<{ renamed_test_cases: number; modules: string[] }> {
  return request(`/modules/${encodeURIComponent(name)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ new_name: newName }),
  });
}

// --- Config (Settings screen) ---
// GET never returns secret values, only whether they're set — PATCH/test
// endpoints accept them write-only, same contract.

export interface AppConfig {
  llm_provider: string;
  groq_model: string;
  groq_configured: boolean;
  anthropic_model: string;
  anthropic_configured: boolean;
  jira_base_url: string;
  jira_configured: boolean;
  jira_project_key: string;
}

export function getConfig(): Promise<AppConfig> {
  return request<AppConfig>('/config');
}

export interface LLMConfigUpdate {
  llm_provider?: 'groq' | 'claude';
  groq_api_key?: string;
  groq_model?: string;
  anthropic_api_key?: string;
  anthropic_model?: string;
}

export function updateLLMConfig(body: LLMConfigUpdate): Promise<AppConfig> {
  return request<AppConfig>('/config/llm', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export interface JiraConfigUpdate {
  jira_base_url?: string;
  jira_email?: string;
  jira_api_token?: string;
  jira_project_key?: string;
}

export function updateJiraConfig(body: JiraConfigUpdate): Promise<AppConfig> {
  return request<AppConfig>('/config/jira', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export interface ConnectionTestResult {
  success: boolean;
  message: string;
}

export function testLLMConfig(provider: 'groq' | 'claude', apiKey: string, model: string): Promise<ConnectionTestResult> {
  return postJson('/config/llm/test', { provider, api_key: apiKey, model });
}

export function testJiraConfig(baseUrl: string, email: string, apiToken: string): Promise<ConnectionTestResult> {
  return postJson('/config/jira/test', { jira_base_url: baseUrl, jira_email: email, jira_api_token: apiToken });
}
