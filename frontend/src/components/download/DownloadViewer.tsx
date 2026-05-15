/**
 * DownloadViewer
 *
 * Accepts a run_id and renders a styled download card pointing directly
 * to the GET /downloads/{run_id} endpoint, verifying it exists first.
 *
 * Usage:
 *   <DownloadViewer runId="20260511_185209" />
 */
import { useEffect, useState } from 'react';
import { FileText, Loader2, AlertCircle } from 'lucide-react';
import { API_BASE_URL } from '../../lib/api';

// ── main component ────────────────────────────────────────────────────────────

type Props = {
  /** Run ID returned by the workflow, e.g. "20260511_185209" */
  runId: string | null | undefined;
};

type State =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'success'; downloadUrl: string }
  | { status: 'error'; message: string };

export function DownloadViewer({ runId }: Props) {
  const [state, setState] = useState<State>({ status: 'idle' });

  useEffect(() => {
    if (!runId) {
      setState({ status: 'idle' });
      return;
    }

    let cancelled = false;
    setState({ status: 'loading' });

    const downloadUrl = `${API_BASE_URL}/downloads/${encodeURIComponent(runId.trim())}`;

    fetch(downloadUrl, { method: 'GET', headers: { accept: 'application/json, application/pdf' } })
      .then(async (res) => {
        if (cancelled) return;
        if (!res.ok) {
          let errMsg = 'File not found or server error';
          try {
            const data = await res.json();
            errMsg = data?.detail || data?.message || errMsg;
          } catch (e) {
            // ignore
          }
          // Enforce a cleaner message for 404s or the backend's broken english
          if (res.status === 404 || errMsg === 'There is no run id exists with this number.') {
            errMsg = 'No files found for this Run ID. Please check the ID and try again.';
          }
          setState({ status: 'error', message: errMsg });
        } else {
          setState({ status: 'success', downloadUrl });
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setState({ status: 'error', message: err.message });
        }
      });

    return () => {
      cancelled = true;
    };
  }, [runId]);

  // ── idle ──────────────────────────────────────────────────────────────────
  if (!runId || state.status === 'idle') {
    return (
      <div className="download-viewer empty-state clean-empty">
        <strong>No run selected</strong>
        <p>Run a workflow to generate downloadable files.</p>
      </div>
    );
  }

  // ── loading ───────────────────────────────────────────────────────────────
  if (state.status === 'loading') {
    return (
      <div className="download-viewer download-loading" aria-live="polite">
        <Loader2 size={22} className="spin-icon" strokeWidth={1.8} />
        <span>Fetching downloads for <strong>{runId}</strong>…</span>
      </div>
    );
  }

  // ── error ─────────────────────────────────────────────────────────────────
  if (state.status === 'error') {
    return (
      <div className="download-viewer message-card error-card" role="alert" aria-live="assertive" style={{ marginTop: '24px' }}>
        <span className="download-error-icon">
          <AlertCircle size={18} strokeWidth={1.8} />
        </span>
        <div>
          <strong>Could not load downloads</strong>
          <pre>{state.message}</pre>
        </div>
      </div>
    );
  }

  // ── success ───────────────────────────────────────────────────────────────
  return (
    <section className="download-viewer surface" aria-label={`Downloads for run ${runId}`}>
      <div className="card-topline result-topline">
        <div>
          <p className="kicker">Run downloads</p>
          <h3>Files for <span className="download-run-id">{runId}</span></h3>
        </div>
        <span className="result-state success">
          <span className="status-dot" />
          Ready
        </span>
      </div>

      <div className="download-file-card download-file-card--highlight">
        <div className="download-file-icon">
          <FileText size={20} strokeWidth={1.8} />
        </div>
        <div className="download-file-info">
          <strong className="download-file-name">Interview Pack PDF</strong>
          <span className="download-file-meta">application/pdf</span>
        </div>
        <a
          href={state.downloadUrl}
          download
          target="_blank"
          rel="noreferrer"
          className="button primary small download-btn"
          aria-label="Download interview pack PDF"
        >
          Download
        </a>
      </div>
    </section>
  );
}
