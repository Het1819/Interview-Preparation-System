import { useMemo, type KeyboardEvent } from 'react';

type TagInputProps = {
  value: string[];
  customValue: string;
  onCustomValueChange: (value: string) => void;
  onAdd: (value: string) => void;
  onRemove: (value: string) => void;
};

const presets = ['Recruiter Screen', 'Technical Round 1', 'Hiring Manager', 'Behavioral'];

export function TagInput({ value, customValue, onCustomValueChange, onAdd, onRemove }: TagInputProps) {
  const remainingPresets = useMemo(() => presets.filter((item) => !value.includes(item)), [value]);

  function addCustomTag() {
    onAdd(customValue);
    onCustomValueChange('');
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Enter') {
      event.preventDefault();
      addCustomTag();
    }
  }

  return (
    <div className="field-stack">
      <div>
        <label className="field-label">Interview rounds</label>
        <p className="field-hint">These values are joined with semicolons before the request is sent to the backend.</p>
      </div>

      <div className="chip-row preset-row">
        {remainingPresets.map((item) => (
          <button key={item} type="button" className="chip-button" onClick={() => onAdd(item)}>
            + {item}
          </button>
        ))}
      </div>

      <div className="input-inline">
        <input
          value={customValue}
          onChange={(event) => onCustomValueChange(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Add a custom round"
        />
        <button type="button" className="button ghost small" onClick={addCustomTag}>
          Add
        </button>
      </div>

      <div className="chip-row selected-row">
        {value.length ? (
          value.map((item) => (
            <button key={item} type="button" className="chip selected-chip" onClick={() => onRemove(item)}>
              {item} ×
            </button>
          ))
        ) : (
          <span className="empty-inline">No interview rounds selected</span>
        )}
      </div>
    </div>
  );
}
