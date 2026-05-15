import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { DownloadViewer } from '../components/download/DownloadViewer';
import { Search, History, HelpCircle } from 'lucide-react';
import { SEO } from '../components/SEO';

export default function DownloadPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [inputValue, setInputValue] = useState(searchParams.get('runId') || '');
  const [activeRunId, setActiveRunId] = useState<string | null>(searchParams.get('runId'));

  // Sync state with URL params
  useEffect(() => {
    const rid = searchParams.get('runId');
    if (rid) {
      setActiveRunId(rid);
      setInputValue(rid);
    }
  }, [searchParams]);

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = inputValue.trim();
    if (trimmed) {
      setActiveRunId(trimmed);
      setSearchParams({ runId: trimmed });
    }
  }

  return (
    <div className="download-page-content">
      <SEO 
        title="Artifact Retrieval" 
        description="Retrieve and download your specialized interview preparation materials using your unique Run ID."
        canonical="https://recruitriders.com/download"
      />
      <section className="hero-section compact-hero">
        <div className="hero-copy">
          <p className="eyebrow">Artifact Retrieval</p>
          <h1>Download your interview packs by Run ID</h1>
          <p className="hero-text">
            Enter the unique identifier provided during your workflow execution to retrieve and download your specialized preparation materials.
          </p>
        </div>
      </section>

      <div className="download-grid">
        <div className="lookup-sidebar">
          <form className="surface lookup-card" onSubmit={handleSearch}>
            <div className="card-topline">
              <div>
                <p className="kicker">Lookup tool</p>
                <h3>Search by ID</h3>
              </div>
              <Search size={18} className="muted-icon" />
            </div>

            <div className="input-stack">
              <label htmlFor="run-id-input" className="field-label">Enter Run ID</label>
              <div className="lookup-input-group">
                <input
                  id="run-id-input"
                  type="text"
                  placeholder="e.g. 12345678_123456"
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                />
                <button type="submit" className="button primary">
                  Retrieve
                </button>
              </div>
              <p className="lookup-hint">IDs are typically in YYYYMMDD_HHMMSS format.</p>
            </div>
          </form>

          <div className="surface info-card">
            <div className="card-topline">
              <div className="icon-heading">
                <History size={18} className="accent-icon" />
                <strong>Where is my ID?</strong>
              </div>
            </div>
            <p className="small-text">
              Your Run ID was displayed in the results panel immediately after you ran the workflow. It was also included in the metadata of any emails sent.
            </p>
          </div>
        </div>

        <div className="download-viewer-container">
          {activeRunId ? (
            <DownloadViewer runId={activeRunId} />
          ) : (
            <div className="surface empty-viewer-state">
              <div className="empty-state-content">
                <div className="empty-icon-circle">
                  <Search size={32} />
                </div>
                <h3>Ready for retrieval</h3>
                <p>Enter a Run ID in the search box to view and download your interview materials.</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
