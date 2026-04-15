import { useEffect, useState } from 'react';
import {
  FileUp,
  ScanSearch,
  Target,
  BrainCircuit,
  PenLine,
  Briefcase,
  Code2,
  Users,
  Sparkles,
  Package,
  Printer,
  Rocket,
  type LucideIcon,
} from 'lucide-react';
import type { WorkflowResponse } from '../types/api';
import { API_BASE_URL } from '../lib/api';
import { toAbsoluteUrl } from '../lib/utils';

type ResultPanelProps = {
  result: WorkflowResponse | null;
  runDetails: Record<string, unknown> | null;
  isLoading: boolean;
  error: string | null;
};

type LoadingMsg = { Icon: LucideIcon; text: string };

const loadingMessages: LoadingMsg[] = [
  { Icon: FileUp,       text: 'Getting your files ready…' },
  { Icon: ScanSearch,   text: 'Reading through your resume…' },
  { Icon: Target,       text: 'Matching your skills to the job…' },
  { Icon: BrainCircuit, text: 'Our agents are thinking hard…' },
  { Icon: PenLine,      text: 'Crafting round-specific questions…' },
  { Icon: Briefcase,    text: 'Preparing recruiter screen notes…' },
  { Icon: Code2,        text: 'Running technical round analysis…' },
  { Icon: Users,        text: 'Building your hiring manager brief…' },
  { Icon: Sparkles,     text: 'Adding the finishing touches…' },
  { Icon: Package,      text: 'Assembling your interview pack…' },
  { Icon: Printer,      text: 'Generating your PDF…' },
  { Icon: Rocket,       text: 'Almost there, hang tight!' },
];

function LoadingMessages() {
  const [index, setIndex] = useState(0);
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    const interval = setInterval(() => {
      setVisible(false);
      setTimeout(() => {
        setIndex((i) => (i + 1) % loadingMessages.length);
        setVisible(true);
      }, 400);
    }, 2800);

    return () => clearInterval(interval);
  }, []);

  const { Icon, text } = loadingMessages[index];

  return (
    <div className={`loading-message ${visible ? 'msg-visible' : 'msg-hidden'}`}>
      <span className="loading-icon-wrap">
        <Icon size={20} strokeWidth={1.8} />
      </span>
      <span className="loading-text">{text}</span>
    </div>
  );
}

export function ResultPanel({ result, isLoading, error }: ResultPanelProps) {
  const pdfUrl = toAbsoluteUrl(API_BASE_URL, result?.pdf_download_url || result?.pdf_path || null);

  return (
    <aside className="surface result-panel" id="results">
      <div className="card-topline result-topline">
        <div>
          <p className="kicker">Result surface</p>
          <h3>Workflow output</h3>
        </div>
        <span className={`result-state ${isLoading ? 'running' : result?.success ? 'success' : result ? 'error' : 'idle'}`}>
          {isLoading ? 'Generating' : result?.success ? 'Success' : result ? 'Review' : 'Waiting'}
        </span>
      </div>

      {isLoading && (
        <div className="loader-block">
          <div className="spinner" />
          <div className="loader-steps">
            <strong>Preparing your interview pack</strong>
            <LoadingMessages />
          </div>
        </div>
      )}

      {error && (
        <div className="message-card error-card">
          <strong>Request failed</strong>
          <pre>{error}</pre>
        </div>
      )}

      {!result && !isLoading && !error && (
        <div className="empty-state clean-empty">
          <strong>No run yet</strong>
          <p>Fill in the workflow form and click <em>Run full workflow</em> to generate your interview preparation pack.</p>
        </div>
      )}

      {result && (
        <div className="result-stack">
          <div className="summary-grid">
            <div className="summary-card">
              <span>Run ID</span>
              <strong>{result.run_id}</strong>
            </div>
            <div className="summary-card">
              <span>Candidate</span>
              <strong>{result.candidate_name || 'Not returned'}</strong>
            </div>
            <div className="summary-card">
              <span>Company</span>
              <strong>{result.company || 'Not set'}</strong>
            </div>
            <div className="summary-card">
              <span>Role</span>
              <strong>{result.role || 'Not set'}</strong>
            </div>
          </div>

          <div className="message-card success-card">
            <strong>{result.message}</strong>
            <p>Recipient: {result.recipient_email || 'No email requested'}</p>
          </div>

          <div className="button-row stretch-row">
            {pdfUrl ? (
              <a className="button primary full-width" href={pdfUrl} target="_blank" rel="noreferrer">
                Download PDF
              </a>
            ) : (
              <button type="button" className="button primary full-width" disabled>
                PDF not available yet
              </button>
            )}
          </div>
        </div>
      )}
    </aside>
  );
}
