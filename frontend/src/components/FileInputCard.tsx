import { useRef, type ChangeEvent } from 'react';

type FileInputCardProps = {
  label: string;
  hint: string;
  accept: string;
  file: File | null;
  onChange: (file: File | null) => void;
};

export function FileInputCard({ label, hint, accept, file, onChange }: FileInputCardProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);

  function handleFileSelect(event: ChangeEvent<HTMLInputElement>) {
    const selected = event.target.files?.[0] || null;
    onChange(selected);
  }

  function openPicker() {
    inputRef.current?.click();
  }

  return (
    <div className="file-card">
      <div className="file-card-header">
        <div>
          <p className="field-label">{label}</p>
          <p className="field-hint">{hint}</p>
        </div>
        <button type="button" className="button ghost small" onClick={openPicker}>
          {file ? 'Replace' : 'Choose'}
        </button>
      </div>

      <button type="button" className={`dropzone ${file ? 'is-selected' : ''}`} onClick={openPicker}>
        <span className="dropzone-icon">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
            <polyline points="17 8 12 3 7 8"></polyline>
            <line x1="12" y1="3" x2="12" y2="15"></line>
          </svg>
        </span>
        <div className="dropzone-copy">
          <strong>{file ? file.name : 'Drag in or choose a file'}</strong>
          <span>{file ? `${(file.size / 1024 / 1024).toFixed(2)} MB selected` : 'One file only. Supported formats match the backend endpoint.'}</span>
        </div>
      </button>

      <input ref={inputRef} type="file" accept={accept} className="sr-only" onChange={handleFileSelect} />
    </div>
  );
}
