import { useEffect, useState } from 'react';
import {
  createModule,
  deleteModule,
  getConfig,
  listModules,
  renameModule,
  testJiraConfig,
  testLLMConfig,
  updateJiraConfig,
  updateLLMConfig,
  type AppConfig,
  type ConnectionTestResult,
} from '../api/client';
import { Button } from '../components/Button';
import { CheckIcon, PencilIcon, XIcon } from '../components/icons';
import { ImportTestCasesCard } from '../components/ImportTestCasesCard';
import { Pill } from '../components/Pill';
import styles from './Settings.module.css';

type Message = { type: 'success' | 'error'; text: string } | null;

function errorText(e: unknown, fallback: string): string {
  return e instanceof Error ? e.message : fallback;
}

export function Settings() {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [modules, setModules] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);

  // LLM form
  const [llmProvider, setLlmProvider] = useState<'groq' | 'claude'>('groq');
  const [groqApiKey, setGroqApiKey] = useState('');
  const [groqModel, setGroqModel] = useState('');
  const [anthropicApiKey, setAnthropicApiKey] = useState('');
  const [anthropicModel, setAnthropicModel] = useState('');
  const [llmSaving, setLlmSaving] = useState(false);
  const [llmMessage, setLlmMessage] = useState<Message>(null);
  const [groqTesting, setGroqTesting] = useState(false);
  const [groqTestResult, setGroqTestResult] = useState<ConnectionTestResult | null>(null);
  const [anthropicTesting, setAnthropicTesting] = useState(false);
  const [anthropicTestResult, setAnthropicTestResult] = useState<ConnectionTestResult | null>(null);

  // Jira form
  const [jiraBaseUrl, setJiraBaseUrl] = useState('');
  const [jiraEmail, setJiraEmail] = useState('');
  const [jiraApiToken, setJiraApiToken] = useState('');
  const [jiraProjectKey, setJiraProjectKey] = useState('');
  const [jiraSaving, setJiraSaving] = useState(false);
  const [jiraMessage, setJiraMessage] = useState<Message>(null);
  const [jiraTesting, setJiraTesting] = useState(false);
  const [jiraTestResult, setJiraTestResult] = useState<ConnectionTestResult | null>(null);

  // Modules
  const [newModuleName, setNewModuleName] = useState('');
  const [addingModule, setAddingModule] = useState(false);
  const [moduleBusy, setModuleBusy] = useState<string | null>(null);
  const [moduleError, setModuleError] = useState<string | null>(null);
  const [editingModule, setEditingModule] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');

  function refreshModules() {
    listModules()
      .then(setModules)
      .catch(() => {});
  }

  useEffect(() => {
    Promise.all([getConfig(), listModules()])
      .then(([c, m]) => {
        setConfig(c);
        setModules(m);
        setLlmProvider(c.llm_provider === 'claude' ? 'claude' : 'groq');
        setGroqModel(c.groq_model);
        setAnthropicModel(c.anthropic_model);
        setJiraBaseUrl(c.jira_base_url);
        setJiraProjectKey(c.jira_project_key);
      })
      .finally(() => setLoading(false));
  }, []);

  async function handleSaveLlm() {
    setLlmSaving(true);
    setLlmMessage(null);
    try {
      const updated = await updateLLMConfig({
        llm_provider: llmProvider,
        groq_api_key: groqApiKey || undefined,
        groq_model: groqModel || undefined,
        anthropic_api_key: anthropicApiKey || undefined,
        anthropic_model: anthropicModel || undefined,
      });
      setConfig(updated);
      setGroqApiKey('');
      setAnthropicApiKey('');
      setLlmMessage({ type: 'success', text: 'LLM settings saved.' });
    } catch (e) {
      setLlmMessage({ type: 'error', text: errorText(e, 'Save failed') });
    } finally {
      setLlmSaving(false);
    }
  }

  async function handleTestGroq() {
    setGroqTesting(true);
    setGroqTestResult(null);
    try {
      setGroqTestResult(await testLLMConfig('groq', groqApiKey, groqModel));
    } catch (e) {
      setGroqTestResult({ success: false, message: errorText(e, 'Test failed') });
    } finally {
      setGroqTesting(false);
    }
  }

  async function handleTestAnthropic() {
    setAnthropicTesting(true);
    setAnthropicTestResult(null);
    try {
      setAnthropicTestResult(await testLLMConfig('claude', anthropicApiKey, anthropicModel));
    } catch (e) {
      setAnthropicTestResult({ success: false, message: errorText(e, 'Test failed') });
    } finally {
      setAnthropicTesting(false);
    }
  }

  async function handleSaveJira() {
    setJiraSaving(true);
    setJiraMessage(null);
    try {
      const updated = await updateJiraConfig({
        jira_base_url: jiraBaseUrl || undefined,
        jira_email: jiraEmail || undefined,
        jira_api_token: jiraApiToken || undefined,
        jira_project_key: jiraProjectKey || undefined,
      });
      setConfig(updated);
      setJiraApiToken('');
      setJiraMessage({ type: 'success', text: 'Jira settings saved.' });
    } catch (e) {
      setJiraMessage({ type: 'error', text: errorText(e, 'Save failed') });
    } finally {
      setJiraSaving(false);
    }
  }

  async function handleTestJira() {
    setJiraTesting(true);
    setJiraTestResult(null);
    try {
      setJiraTestResult(await testJiraConfig(jiraBaseUrl, jiraEmail, jiraApiToken));
    } catch (e) {
      setJiraTestResult({ success: false, message: errorText(e, 'Test failed') });
    } finally {
      setJiraTesting(false);
    }
  }

  async function handleAddModule() {
    const name = newModuleName.trim();
    if (!name) return;
    setAddingModule(true);
    setModuleError(null);
    try {
      setModules(await createModule(name));
      setNewModuleName('');
    } catch (e) {
      setModuleError(errorText(e, 'Could not add module'));
    } finally {
      setAddingModule(false);
    }
  }

  async function handleDeleteModule(name: string) {
    setModuleBusy(name);
    setModuleError(null);
    try {
      setModules(await deleteModule(name));
    } catch (e) {
      setModuleError(errorText(e, `Could not delete "${name}"`));
    } finally {
      setModuleBusy(null);
    }
  }

  function startRename(name: string) {
    setEditingModule(name);
    setEditValue(name);
    setModuleError(null);
  }

  async function confirmRename() {
    if (!editingModule) return;
    const newName = editValue.trim();
    if (!newName || newName === editingModule) {
      setEditingModule(null);
      return;
    }
    setModuleBusy(editingModule);
    setModuleError(null);
    try {
      const result = await renameModule(editingModule, newName);
      setModules(result.modules);
      setEditingModule(null);
    } catch (e) {
      setModuleError(errorText(e, 'Rename failed'));
    } finally {
      setModuleBusy(null);
    }
  }

  return (
    <div className="page" style={{ maxWidth: 700 }}>
      <div style={{ marginBottom: 20 }}>
        <div className="pageEyebrow">Settings</div>
        <h1 className="pageTitle">Settings</h1>
        <div className="pageMeta">Manage LLM/Jira credentials, modules, and your test case library.</div>
      </div>

      {loading || !config ? (
        <p className="pageMeta">Loading…</p>
      ) : (
        <>
          <div className={`card ${styles.card}`}>
            <div className={styles.cardTitle}>LLM Provider</div>
            <div className={styles.cardSub}>Keys are write-only — saved values are never shown back, only whether they're set.</div>

            <div className={styles.field}>
              <label className="label">Active provider</label>
              <select
                className="textInput"
                value={llmProvider}
                onChange={(e) => setLlmProvider(e.target.value as 'groq' | 'claude')}
              >
                <option value="groq">Groq</option>
                <option value="claude">Claude (Anthropic)</option>
              </select>
            </div>

            <hr className={styles.divider} />

            <div className={styles.labelRow}>
              <div className={styles.subHeading}>Groq</div>
              <Pill tone={config.groq_configured ? 'success' : 'neutral'}>{config.groq_configured ? 'Configured' : 'Not set'}</Pill>
            </div>
            <div className={styles.fieldGrid}>
              <div className={styles.field}>
                <label className="label">API key</label>
                <input
                  type="password"
                  className="textInput"
                  placeholder={config.groq_configured ? '•••••••• (leave blank to keep)' : 'gsk_…'}
                  value={groqApiKey}
                  onChange={(e) => setGroqApiKey(e.target.value)}
                  autoComplete="off"
                />
              </div>
              <div className={styles.field}>
                <label className="label">Model</label>
                <input type="text" className="textInput" value={groqModel} onChange={(e) => setGroqModel(e.target.value)} />
              </div>
            </div>
            <div className={styles.actionRow}>
              <Button variant="secondary" disabled={groqTesting || !groqApiKey || !groqModel} onClick={handleTestGroq}>
                {groqTesting ? 'Testing…' : 'Test connection'}
              </Button>
              {groqTestResult && (
                <span className={`${styles.statusMessage} ${groqTestResult.success ? styles.statusSuccess : styles.statusError}`}>
                  {groqTestResult.message}
                </span>
              )}
            </div>

            <hr className={styles.divider} />

            <div className={styles.labelRow}>
              <div className={styles.subHeading}>Claude (Anthropic)</div>
              <Pill tone={config.anthropic_configured ? 'success' : 'neutral'}>
                {config.anthropic_configured ? 'Configured' : 'Not set'}
              </Pill>
            </div>
            <div className={styles.fieldGrid}>
              <div className={styles.field}>
                <label className="label">API key</label>
                <input
                  type="password"
                  className="textInput"
                  placeholder={config.anthropic_configured ? '•••••••• (leave blank to keep)' : 'sk-ant-…'}
                  value={anthropicApiKey}
                  onChange={(e) => setAnthropicApiKey(e.target.value)}
                  autoComplete="off"
                />
              </div>
              <div className={styles.field}>
                <label className="label">Model</label>
                <input
                  type="text"
                  className="textInput"
                  value={anthropicModel}
                  onChange={(e) => setAnthropicModel(e.target.value)}
                />
              </div>
            </div>
            <div className={styles.actionRow}>
              <Button
                variant="secondary"
                disabled={anthropicTesting || !anthropicApiKey || !anthropicModel}
                onClick={handleTestAnthropic}
              >
                {anthropicTesting ? 'Testing…' : 'Test connection'}
              </Button>
              {anthropicTestResult && (
                <span
                  className={`${styles.statusMessage} ${anthropicTestResult.success ? styles.statusSuccess : styles.statusError}`}
                >
                  {anthropicTestResult.message}
                </span>
              )}
            </div>

            <div className={styles.actionRow}>
              <Button variant="primary" disabled={llmSaving} onClick={handleSaveLlm}>
                {llmSaving ? 'Saving…' : 'Save LLM settings'}
              </Button>
              {llmMessage && (
                <span className={`${styles.statusMessage} ${llmMessage.type === 'success' ? styles.statusSuccess : styles.statusError}`}>
                  {llmMessage.text}
                </span>
              )}
            </div>
          </div>

          <div className={`card ${styles.card}`}>
            <div className={styles.labelRow}>
              <div className={styles.cardTitle} style={{ marginBottom: 0 }}>
                Jira
              </div>
              <Pill tone={config.jira_configured ? 'success' : 'neutral'}>{config.jira_configured ? 'Configured' : 'Not set'}</Pill>
            </div>
            <div className={styles.cardSub}>Used to pull ticket details for generation and push approved cases as Jira issues.</div>

            <div className={styles.field}>
              <label className="label">Base URL</label>
              <input
                type="text"
                className="textInput"
                placeholder="https://yourteam.atlassian.net"
                value={jiraBaseUrl}
                onChange={(e) => setJiraBaseUrl(e.target.value)}
              />
            </div>
            <div className={styles.fieldGrid}>
              <div className={styles.field}>
                <label className="label">Account email</label>
                <input type="text" className="textInput" value={jiraEmail} onChange={(e) => setJiraEmail(e.target.value)} />
              </div>
              <div className={styles.field}>
                <label className="label">API token</label>
                <input
                  type="password"
                  className="textInput"
                  placeholder={config.jira_configured ? '•••••••• (leave blank to keep)' : 'Enter token'}
                  value={jiraApiToken}
                  onChange={(e) => setJiraApiToken(e.target.value)}
                  autoComplete="off"
                />
              </div>
            </div>
            <div className={styles.field}>
              <label className="label">Fallback project key (used for doc-sourced uploads)</label>
              <input
                type="text"
                className="textInput"
                placeholder="PROJ"
                value={jiraProjectKey}
                onChange={(e) => setJiraProjectKey(e.target.value)}
              />
            </div>

            <div className={styles.actionRow}>
              <Button
                variant="secondary"
                disabled={jiraTesting || !jiraBaseUrl || !jiraEmail || !jiraApiToken}
                onClick={handleTestJira}
              >
                {jiraTesting ? 'Testing…' : 'Test connection'}
              </Button>
              {jiraTestResult && (
                <span className={`${styles.statusMessage} ${jiraTestResult.success ? styles.statusSuccess : styles.statusError}`}>
                  {jiraTestResult.message}
                </span>
              )}
            </div>
            <div className={styles.actionRow}>
              <Button variant="primary" disabled={jiraSaving} onClick={handleSaveJira}>
                {jiraSaving ? 'Saving…' : 'Save Jira settings'}
              </Button>
              {jiraMessage && (
                <span
                  className={`${styles.statusMessage} ${jiraMessage.type === 'success' ? styles.statusSuccess : styles.statusError}`}
                >
                  {jiraMessage.text}
                </span>
              )}
            </div>
          </div>

          <div className={`card ${styles.card}`}>
            <div className={styles.cardTitle}>Modules ({modules.length})</div>
            <div className={styles.cardSub}>
              Modules tag runs and library entries. Ones already used by test cases can be renamed (cascades everywhere) but not
              deleted.
            </div>

            {moduleError && <div className={styles.moduleError}>{moduleError}</div>}

            <div className={styles.moduleList}>
              {modules.length === 0 ? (
                <span className="pageMeta">None yet — add one below.</span>
              ) : (
                modules.map((m) =>
                  editingModule === m ? (
                    <span key={m} className={styles.moduleEdit}>
                      <input
                        type="text"
                        className={styles.moduleEditInput}
                        value={editValue}
                        autoFocus
                        onChange={(e) => setEditValue(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') confirmRename();
                          if (e.key === 'Escape') setEditingModule(null);
                        }}
                      />
                      <button
                        type="button"
                        className={styles.moduleChipBtn}
                        disabled={moduleBusy === m}
                        onClick={confirmRename}
                        title="Confirm rename"
                      >
                        <CheckIcon size={12} />
                      </button>
                      <button
                        type="button"
                        className={styles.moduleChipBtn}
                        disabled={moduleBusy === m}
                        onClick={() => setEditingModule(null)}
                        title="Cancel"
                      >
                        <XIcon size={12} />
                      </button>
                    </span>
                  ) : (
                    <span key={m} className={styles.moduleChip}>
                      {m}
                      <button
                        type="button"
                        className={styles.moduleChipBtn}
                        disabled={moduleBusy === m}
                        onClick={() => startRename(m)}
                        title="Rename"
                      >
                        <PencilIcon size={11} />
                      </button>
                      <button
                        type="button"
                        className={styles.moduleChipBtn}
                        disabled={moduleBusy === m}
                        onClick={() => handleDeleteModule(m)}
                        title="Delete"
                      >
                        <XIcon size={12} />
                      </button>
                    </span>
                  ),
                )
              )}
            </div>

            <div className={styles.addModuleRow}>
              <input
                type="text"
                className={`textInput ${styles.addModuleInput}`}
                placeholder="New module name…"
                value={newModuleName}
                onChange={(e) => setNewModuleName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleAddModule();
                }}
              />
              <Button variant="secondary" disabled={addingModule || !newModuleName.trim()} onClick={handleAddModule}>
                {addingModule ? 'Adding…' : 'Add'}
              </Button>
            </div>
          </div>

          <ImportTestCasesCard onImported={refreshModules} />
        </>
      )}
    </div>
  );
}
