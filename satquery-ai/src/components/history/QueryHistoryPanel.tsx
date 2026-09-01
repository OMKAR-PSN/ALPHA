// QueryHistoryPanel.tsx — Collapsible recent queries sidebar

import { Clock, ChevronRight, Trash2, RotateCcw } from 'lucide-react';
import type { HistoryEntry } from '../../hooks/useQueryHistory';

interface QueryHistoryPanelProps {
  history: HistoryEntry[];
  onReplay: (entry: HistoryEntry) => void;
  onClear: () => void;
}

const CONF_COLORS: Record<string, string> = {
  high: 'badge-green bg-green-100 text-green-700',
  medium: 'badge-orange bg-amber-100 text-amber-700',
  low: 'badge-red bg-red-100 text-red-700',
};

function timeAgo(ts: number): string {
  const diff = Date.now() - ts;
  const m = Math.floor(diff / 60000);
  if (m < 1) return 'just now';
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

export default function QueryHistoryPanel({ history, onReplay, onClear }: QueryHistoryPanelProps) {
  if (history.length === 0) {
    return (
      <div className="py-6 text-center">
        <Clock size={22} className="mx-auto mb-2 text-rs-text-muted opacity-40" />
        <p className="text-xs text-rs-text-muted">No recent analyses</p>
      </div>
    );
  }

  return (
    <div className="space-y-1.5">
      {history.map(entry => (
        <div
          key={entry.id}
          className="group flex items-start gap-2.5 p-3 rounded-xl border border-rs-border bg-white hover:border-navy-200 hover:shadow-sm transition-all cursor-pointer"
          onClick={() => onReplay(entry)}
        >
          <div className="w-7 h-7 rounded-lg bg-navy-50 flex items-center justify-center flex-shrink-0 mt-0.5">
            <Clock size={13} className="text-rs-navy" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-semibold text-rs-text-primary leading-snug line-clamp-2">
              {entry.query}
            </p>
            {entry.aoiName && (
              <p className="text-[10px] text-rs-teal mt-0.5">📍 {entry.aoiName}</p>
            )}
            <div className="flex items-center gap-2 mt-1.5">
              <span className={`badge text-[10px] px-1.5 py-0.5 rounded-full font-bold ${CONF_COLORS[entry.confidenceLevel] || CONF_COLORS.medium}`}>
                {(entry.confidence * 100).toFixed(0)}%
              </span>
              <span className="text-[10px] text-rs-text-muted">{timeAgo(entry.timestamp)}</span>
            </div>
          </div>
          <div className="flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
            <RotateCcw size={13} className="text-rs-text-muted" />
          </div>
        </div>
      ))}

      {/* Clear button */}
      <button
        onClick={e => { e.stopPropagation(); onClear(); }}
        className="w-full flex items-center justify-center gap-2 py-2 text-xs text-rs-text-muted hover:text-red-500 transition-colors"
      >
        <Trash2 size={12} />
        Clear history
      </button>
    </div>
  );
}
