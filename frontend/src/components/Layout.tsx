import { useState, useEffect, useRef, type ReactNode } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { API_BASE_URL, getHealth } from '../lib/api';

type LayoutProps = {
  children: ReactNode;
};

export function Layout({ children }: LayoutProps) {
  const [healthStatus, setHealthStatus] = useState<'checking' | 'online' | 'offline'>('checking');
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [isHeaderVisible, setIsHeaderVisible] = useState(true);
  const lastScrollY = useRef(0);
  const location = useLocation();

  useEffect(() => {
    const handleScroll = () => {
      if (isMenuOpen) return;
      const currentScrollY = window.scrollY;
      if (currentScrollY > lastScrollY.current && currentScrollY > 80) {
        setIsHeaderVisible(false);
      } else {
        setIsHeaderVisible(true);
      }
      lastScrollY.current = currentScrollY;
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, [isMenuOpen]);

  useEffect(() => {
    let mounted = true;
    getHealth()
      .then(() => {
        if (mounted) setHealthStatus('online');
      })
      .catch(() => {
        if (mounted) setHealthStatus('offline');
      });
    return () => { mounted = false; };
  }, []);

  // Close menu on navigation
  useEffect(() => {
    setIsMenuOpen(false);
    window.scrollTo(0, 0);
  }, [location.pathname]);

  return (
    <div className="app-shell">
      <div className="ambient ambient-one" />
      <div className="ambient ambient-two" />
      <div className="grid-overlay" />

      <header className={`site-header wrapper ${isMenuOpen ? 'menu-open' : ''} ${!isHeaderVisible ? 'header-hidden' : ''}`}>
        <div className="brand-bar">
          <Link className="brand-lockup" to="/" aria-label="Recruit Riders Technologies home">
            <img src="/assets/brand/rrt-logo.svg" alt="Recruit Riders Technologies" className="brand-logo" />
          </Link>
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

        <nav className="topnav" aria-label="Primary">
          <a href="/#top">Home</a>
          <a href="/#workflow">Generate PDF</a>
          <a href="/download">Download PDF</a>
        </nav>

        <div className="topbar-actions">
          <div className={`status-pill ${healthStatus}`} aria-live="polite">
            <span className="status-dot" />
            Backend {healthStatus}
          </div>

          <a className="button primary small" href="https://www.recruitriders.com/" target="_blank" rel="noreferrer">
            Website
          </a>
        </div>
      </header>

      <main className="wrapper main-stack" id="main-content">
        {children}
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
              <a href="/#workflow">Generate PDF</a>
              <a href="/download">Download PDF</a>
            </div>
            <div className="link-group">
              <strong>Company</strong>
              <a href="https://www.recruitriders.com/about-us/" target="_blank" rel="noreferrer">About Us</a>
              <a href="https://www.recruitriders.com/" target="_blank" rel="noreferrer">Main Website</a>
              <a href="https://ups.cid.mybluehost.me/contact-us/">Contact Us</a>
            </div>
            <div className="link-group">
              <strong>Legal</strong>
              <a href="https://ups.cid.mybluehost.me/privacy-statement-us/">Privacy Policy</a>
              <a href="https://ups.cid.mybluehost.me/terms-and-conditions/">Terms and Conditions</a>
            </div>
          </div>
        </div>

        <div className="footer-bottom">
          <p>&copy; {new Date().getFullYear()} Recruit Riders Technologies. All rights reserved.</p>
          <div className="footer-secondary-links">
            <button 
              className="back-to-top" 
              onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
              aria-label="Back to top"
            >
              Back to Top ↑
            </button>
          </div>
        </div>
      </footer>
    </div>
  );
}
