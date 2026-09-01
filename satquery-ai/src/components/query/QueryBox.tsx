// Query Box component — natural language input with example queries

import { useState } from 'react';
import { Search, Lightbulb, ArrowRight } from 'lucide-react';

const EXAMPLE_QUERIES = [
  { label: 'Scene understanding', query: 'What is present in this scene?' },
  { label: 'Change detection', query: 'What changed between these two images?' },
  { label: 'Built-up analysis', query: 'Did the built-up area increase near this river between 2024 and 2026?' },
  { label: 'Water body detection', query: 'Identify the water bodies in this region.' },
  { label: 'SAR fusion', query: 'Compare the optical and SAR images and identify built-up areas.' },
  { label: 'Cloud scenario', query: 'What changed here? The second image seems hazy.' },
];

interface QueryBoxProps {
  onSubmit: (query: string) => void;
  disabled?: boolean;
  initialQuery?: string;
}

export default function QueryBox({ onSubmit, disabled, initialQuery = '' }: QueryBoxProps) {
  const [query, setQuery] = useState(initialQuery);

  const handleSubmit = () => {
    if (query.trim() && !disabled) onSubmit(query.trim());
  };

  return (
    <div className="space-y-4">
      {/* Main input */}
      <div className="relative">
        <div className="absolute left-4 top-1/2 -translate-y-1/2 text-rs-text-muted">
          <Search size={18} />
        </div>
        <textarea
          id="query-input"
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={e => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              handleSubmit();
            }
          }}
          disabled={disabled}
          rows={2}
          placeholder="Ask a question about your satellite imagery..."
          className="w-full pl-11 pr-32 py-4 text-sm border-2 border-rs-border rounded-xl bg-white
                     focus:outline-none focus:border-rs-navy placeholder:text-rs-text-muted
                     resize-none transition-colors disabled:bg-gray-50 disabled:text-gray-400
                     leading-relaxed"
        />
        <button
          onClick={handleSubmit}
          disabled={!query.trim() || disabled}
          className="absolute right-3 bottom-3 btn-primary text-sm px-4 py-2 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Analyze <ArrowRight size={14} />
        </button>
      </div>

      {/* Example queries */}
      <div>
        <div className="flex items-center gap-2 mb-2.5">
          <Lightbulb size={13} className="text-rs-text-muted" />
          <span className="text-xs text-rs-text-muted font-medium">Example queries</span>
        </div>
        <div className="flex flex-wrap gap-2">
          {EXAMPLE_QUERIES.map(({ label, query: q }) => (
            <button
              key={label}
              onClick={() => setQuery(q)}
              disabled={disabled}
              className="px-3 py-1.5 rounded-full text-xs border border-rs-border bg-white
                         hover:border-rs-navy hover:text-rs-navy hover:bg-navy-50
                         text-rs-text-secondary transition-all disabled:opacity-50"
            >
              {label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
