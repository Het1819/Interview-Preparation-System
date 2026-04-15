import { useEffect, useMemo, useState, useRef, type FormEvent } from 'react';
import { FileInputCard } from './components/FileInputCard';
import { ResultPanel } from './components/ResultPanel';
import { TagInput } from './components/TagInput';
import { API_BASE_URL, getHealth, getRun, runWorkflow } from './lib/api';
import type { WorkflowFormState } from './types/api';

const allowedFileTypes = '.pdf,.doc,.docx,.txt,.jpg,.jpeg,.png';

const initialState: WorkflowFormState = {
  resume: null,
  jd: null,
  interviewRounds: [],
  customRound: '',
  answerLength: 'answer_medium',
  company: '',
  role: '',
  sendEmail: false,
  toEmail: ''
};

const trustLogos = [
  { name: 'Amazon', src: '/assets/logos/amazon.png' },
  { name: 'Google', src: '/assets/logos/google.png' },
  { name: 'Microsoft', src: '/assets/logos/microsoft.png' },
  { name: 'Meta', src: '/assets/logos/meta.png' },
  { name: 'Netflix', src: '/assets/logos/netflix.png' },
  { name: 'Adobe', src: '/assets/logos/adobe.png' },
  { name: 'Uber', src: '/assets/logos/uber.png' },
  { name: 'Stripe', src: '/assets/logos/stripe.png' },
  { name: 'Shopify', src: '/assets/logos/shopify.png' }
];

const featureCards = [
  {
    title: 'Resume and JD intelligence',
    text: 'Upload the two core inputs and let the workflow prepare a sharper, more role-aligned interview pack.'
  },
  {
    title: 'Round-wise preparation',
    text: 'Generate recruiter, technical, behavioral, and hiring manager questions in one clean request flow.'
  },
  {
    title: 'Download or email output',
    text: 'Open the generated PDF instantly or route it directly to a recipient when needed.'
  }
];

const companyCards = [
  {
    title: 'Team energy',
    text: 'Human support, strong coordination, and practical guidance for candidates moving through hiring cycles.',
    image: '/assets/company/team.jpeg'
  },
  {
    title: 'Focused workspace',
    text: 'A cleaner environment, built around clarity, execution, and recruiter support.',
    image: '/assets/company/office-1.jpg'
  },
  {
    title: 'Studio-like setup',
    text: 'A premium visual layer that feels closer to a modern service brand than a generic portal.',
    image: '/assets/company/office-2.jpg'
  }
];

export default function App() {
  const [form, setForm] = useState<WorkflowFormState>(initialState);
  const [healthStatus, setHealthStatus] = useState<'checking' | 'online' | 'offline'>('checking');
  const [healthPayload, setHealthPayload] = useState<string>('Checking backend connection...');
  const [result, setResult] = useState<any | null>(null);
  const [runDetails, setRunDetails] = useState<Record<string, unknown> | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [isHeaderVisible, setIsHeaderVisible] = useState(true);
  const lastScrollY = useRef(0);

  useEffect(() => {
    const handleScroll = () => {
      // Keep header visible if mobile menu is open
      if (isMenuOpen) return;

      const currentScrollY = window.scrollY;
      // Scroll down past 80px: hide header
      if (currentScrollY > lastScrollY.current && currentScrollY > 80) {
        setIsHeaderVisible(false);
      } else {
        // Scroll up: show header
        setIsHeaderVisible(true);
      }
      lastScrollY.current = currentScrollY;
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, [isMenuOpen]);

  // Scroll-reveal via IntersectionObserver
  useEffect(() => {
    const els = document.querySelectorAll('.reveal, .reveal-stagger');
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add('visible');
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.08 }
    );
    els.forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    let mounted = true;

    getHealth()
      .then((payload) => {
        if (!mounted) return;
        setHealthStatus('online');
        setHealthPayload(JSON.stringify(payload));
      })
      .catch((err: unknown) => {
        if (!mounted) return;
        setHealthStatus('offline');
        setHealthPayload(err instanceof Error ? err.message : 'Failed to reach backend');
      });

    return () => {
      mounted = false;
    };
  }, []);

  const joinedRounds = useMemo(() => form.interviewRounds.join('; '), [form.interviewRounds]);

  function patchForm<K extends keyof WorkflowFormState>(key: K, value: WorkflowFormState[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function addRound(value: string) {
    const cleaned = value.trim();
    if (!cleaned) return;

    setForm((current) => {
      if (current.interviewRounds.includes(cleaned)) return current;
      return { ...current, interviewRounds: [...current.interviewRounds, cleaned] };
    });
  }

  function removeRound(value: string) {
    setForm((current) => ({
      ...current,
      interviewRounds: current.interviewRounds.filter((item) => item !== value)
    }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsLoading(true);
    setError(null);
    setResult(null);
    setRunDetails(null);

    try {
      const response = await runWorkflow(form);
      setResult(response);

      if (response.run_id) {
        try {
          const details = await getRun(response.run_id);
          setRunDetails(details);
        } catch {
          setRunDetails(null);
        }
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Something went wrong');
    } finally {
      setIsLoading(false);
    }
  }

  function resetForm() {
    setForm(initialState);
    setResult(null);
    setRunDetails(null);
    setError(null);
  }

  return (
    <div className="app-shell">
      <div className="ambient ambient-one" />
      <div className="ambient ambient-two" />
      <div className="grid-overlay" />

      <header className={`site-header wrapper ${isMenuOpen ? 'menu-open' : ''} ${!isHeaderVisible ? 'header-hidden' : ''}`}>
        <div className="brand-bar">
          <a className="brand-lockup" href="#top" aria-label="Recruit Riders Technologies home">
            <img src="/assets/brand/rrt-logo.svg" alt="Recruit Riders Technologies" className="brand-logo" />
          </a>
          <button
            className="mobile-menu-toggle"
            onClick={() => setIsMenuOpen(!isMenuOpen)}
            aria-label="Toggle navigation menu"
          >
            {isMenuOpen ? (
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M18 6L6 18M6 6l12 12" />
              </svg>
            ) : (
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            )}
          </button>
        </div>

        <nav className="topnav" aria-label="Primary" onClick={() => setIsMenuOpen(false)}>
          <a href="#top">Home</a>
          <a href="#workflow">Workflow</a>
          <a href="#results">Results</a>
          <a href="#company">Company</a>
        </nav>

        <div className="topbar-actions">
          <div className={`status-pill ${healthStatus}`}>
            <span className="status-dot" />
            Backend {healthStatus}
          </div>
          <a className="button ghost small" href={API_BASE_URL} target="_blank" rel="noreferrer">
            API
          </a>
          <a className="button primary small" href="https://www.recruitriders.com/" target="_blank" rel="noreferrer">
            Website
          </a>
        </div>
      </header>

      <main className="wrapper main-stack">
        <section className="hero-section" id="top">
          <div className="hero-copy">
            <p className="eyebrow">Automated Candidate Preparation</p>
            <h1>Accelerate interview success with an intelligent preparation workflow.</h1>
            <p className="hero-text">
              Upload your resume and job description to instantly generate highly targeted interview packs. Experience a seamless and premium product flow that aligns your candidates with their precise hiring cycles.
            </p>

            <div className="hero-actions">
              <a className="button primary" href="#workflow">
                Run workflow
              </a>
              <a className="button ghost" href="#company">
                Explore company
              </a>
            </div>

            <div className="hero-stats">
              <article className="metric-card">
                <span className="metric-value">90k+</span>
                <span className="metric-label">Applications processed</span>
                <p>Operational support and workflow discipline that keeps candidate movement fast and structured.</p>
              </article>
              <article className="metric-card">
                <span className="metric-value">50+</span>
                <span className="metric-label">Offers secured</span>
                <p>Focused interview preparation designed around fit, clarity, and role-specific execution.</p>
              </article>
            </div>
          </div>

          <div className="hero-visual">
            <div className="hero-visual-card main-visual">
              <div className="visual-copy">
                <span className="eyebrow subtle">Interview prep workflow</span>
                <strong>Resume + JD + Rounds + PDF Delivery</strong>
                <p>Everything is executed securely through our advanced processing engine, generating high-conversion study materials instantly.</p>
              </div>
              <img src="/hero-illustration.svg" alt="Interview workflow dashboard illustration" />
            </div>

            <div className="hero-visual-row">
              <div className="hero-mini-card image-card">
                <img src="/assets/company/office-2.jpg" alt="Recruit Riders workspace" />
                <div className="image-overlay">
                  <strong>Modern workspace</strong>
                  <span>Clean, focused, and service-oriented.</span>
                </div>
              </div>
              <div className="hero-mini-card text-card">
                <span className="eyebrow subtle">Execution Strategy</span>
                <strong>Structured, focused, confident</strong>
                <p>Advanced routing, smart question curation, and streamlined support to guide candidates through the hiring process.</p>
              </div>
            </div>
          </div>
        </section>

        <section className="trust-band section-card reveal">
          <div className="section-heading compact-heading">
            <p className="eyebrow">Trusted visual language</p>
            <h2>Built to feel modern, credible, and enterprise-ready</h2>
          </div>

          <div className="logo-marquee">
            <div className="logo-track">
              {[...trustLogos, ...trustLogos].map((logo, index) => (
                <div className="logo-chip" key={`${logo.name}-${index}`}>
                  <img src={logo.src} alt={`${logo.name} logo`} />
                  <span>{logo.name}</span>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="features-grid reveal-stagger">
          {featureCards.map((card) => (
            <article key={card.title} className="feature-card section-card">
              <span className="feature-index">0{featureCards.indexOf(card) + 1}</span>
              <h3>{card.title}</h3>
              <p>{card.text}</p>
            </article>
          ))}
        </section>

        <section className="workflow-layout reveal" id="workflow">
          <div className="workflow-column">
            <div className="section-heading">
              <p className="eyebrow">Workflow execution</p>
              <h2>Generate specialized interview materials in seconds</h2>
              <p>
                Configure the request by uploading required documents, selecting interview rounds, choosing answer depth,
                and enabling optional direct-to-candidate email routing.
              </p>
            </div>

            <form className="workflow-card section-card" onSubmit={handleSubmit}>
              <div className="card-topline">
                <div>
                  <p className="eyebrow subtle">POST /workflow/run</p>
                  <h3>Interview preparation request</h3>
                </div>
                <span className="chip-badge">Multipart upload</span>
              </div>

              <div className="form-grid">
                <FileInputCard
                  label="Resume file"
                  hint="PDF, DOC, DOCX, TXT, JPG, JPEG, PNG"
                  accept={allowedFileTypes}
                  file={form.resume}
                  onChange={(file) => patchForm('resume', file)}
                />

                <FileInputCard
                  label="Job description file"
                  hint="Upload the exact JD you want the workflow to target."
                  accept={allowedFileTypes}
                  file={form.jd}
                  onChange={(file) => patchForm('jd', file)}
                />
              </div>

              <TagInput
                value={form.interviewRounds}
                customValue={form.customRound}
                onCustomValueChange={(value) => patchForm('customRound', value)}
                onAdd={addRound}
                onRemove={removeRound}
              />

              <div className="input-grid">
                <label>
                  <span className="field-label">Answer length</span>
                  <select
                    value={form.answerLength}
                    onChange={(event) => patchForm('answerLength', event.target.value as WorkflowFormState['answerLength'])}
                  >
                    <option value="answer_small">Small</option>
                    <option value="answer_medium">Medium</option>
                    <option value="answer_large">Large</option>
                  </select>
                </label>

                <label>
                  <span className="field-label">Company</span>
                  <input value={form.company} onChange={(event) => patchForm('company', event.target.value)} placeholder="Optional" />
                </label>

                <label>
                  <span className="field-label">Role</span>
                  <input value={form.role} onChange={(event) => patchForm('role', event.target.value)} placeholder="Optional" />
                </label>

                <label>
                  <span className="field-label">Recipient email</span>
                  <input
                    type="email"
                    value={form.toEmail}
                    onChange={(event) => patchForm('toEmail', event.target.value)}
                    placeholder="name@example.com"
                    disabled={!form.sendEmail}
                  />
                </label>
              </div>

              <label className="toggle-row">
                <input
                  type="checkbox"
                  checked={form.sendEmail}
                  onChange={(event) => patchForm('sendEmail', event.target.checked)}
                />
                <span>Send generated PDF to recipient email</span>
              </label>

              <div className="preview-box">
                <span className="field-label">Request preview</span>
                <code>{joinedRounds || 'No rounds selected yet'}</code>
              </div>

              <div className="button-row">
                <button type="submit" className="button primary" disabled={isLoading}>
                  {isLoading ? 'Running workflow...' : 'Run full workflow'}
                </button>
                <button type="button" className="button ghost" onClick={resetForm} disabled={isLoading}>
                  Reset
                </button>
                <a className="button ghost" href="https://www.trustpilot.com/review/recruitriders.com" target="_blank" rel="noreferrer">
                  Review us
                </a>
              </div>
            </form>

            <section className="info-strip section-card">
              <article>
                <strong>Intelligent matching</strong>
                <p>Analyzes core documentation to map experiences directly to the employer's exact criteria.</p>
              </article>
              <article>
                <strong>Comprehensive output</strong>
                <p>Delivers organized, round-specific interview questions directly to your candidates via PDF.</p>
              </article>
            </section>
          </div>

          <ResultPanel result={result} runDetails={runDetails} isLoading={isLoading} error={error} />
        </section>

        <section className="company-panel reveal" id="company">
          <div className="section-heading company-heading">
            <p className="eyebrow">Company story</p>
            <h2>Your catalyst for professional advancement and career success</h2>
            <p>
              Recruit Riders creates a premium, structured environment for candidates to prepare confidently, providing deep insights tailored exactly to the roles they seek.
            </p>
          </div>

          <div className="company-layout">
            <article className="company-copy section-card">
              <span className="eyebrow subtle">Vision</span>
              <h3>Helping candidates move with clarity, support, and better preparation</h3>
              <p>
                Recruit Riders Technologies focuses on practical career guidance, structured preparation, and targeted job support
                so candidates can move through the hiring process with more confidence.
              </p>
              <p>
                We provide a professional, enterprise-grade platform that bridges the gap between raw talent and the rigorous demands of modern technical interviews.
              </p>
              <ul className="company-points">
                <li>Personalized job and role guidance</li>
                <li>Interview preparation aligned to real openings</li>
                <li>Premium presentation for both candidates and recruiters</li>
                <li>Cleaner bridge between brand and backend workflow</li>
              </ul>
            </article>

            <div className="gallery-grid">
              {companyCards.map((card) => (
                <article key={card.title} className="gallery-card">
                  <img src={card.image} alt={card.title} />
                  <div className="gallery-overlay">
                    <strong>{card.title}</strong>
                    <p>{card.text}</p>
                  </div>
                </article>
              ))}
              <article className="gallery-card gradient-card">
                <div className="gradient-copy">
                  <span className="eyebrow subtle">Proven results</span>
                  <strong>Maximize interview conversion rates</strong>
                  <p>
                    Leverage our targeted pipelines, strategic insights, and advanced preparation modules to close hiring loops faster.
                  </p>
                </div>
              </article>
            </div>
          </div>
        </section>
      </main>

      <footer className="site-footer wrapper">
        <div className="footer-top">
          <div className="footer-brand">
            <img src="/assets/brand/rrt-logo.svg" alt="Recruit Riders Technologies" className="brand-logo" />
            <p>Your catalyst for career success. Sharper, faster, and more targeted interview preparation workflows.</p>
          </div>
          
          <div className="footer-links">
            <div className="link-group">
              <strong>Product</strong>
              <a href="#workflow">Run Workflow</a>
              <a href="#results">View Results</a>
              <a href={API_BASE_URL} target="_blank" rel="noreferrer">API Access</a>
            </div>
            <div className="link-group">
              <strong>Company</strong>
              <a href="#company">About Us</a>
              <a href="https://www.recruitriders.com/" target="_blank" rel="noreferrer">Main Website</a>
              <a href="mailto:support@recruitriders.com">Support</a>
            </div>
            <div className="link-group">
              <strong>Legal</strong>
              <a href="#">Privacy Policy</a>
              <a href="#">Terms of Service</a>
            </div>
          </div>
        </div>
        
        <div className="footer-bottom">
          <p>&copy; {new Date().getFullYear()} Recruit Riders Technologies. All rights reserved.</p>
        </div>
      </footer>
    </div>
  );
}
