// Agent Trace Panel — live animated step-by-step execution trace with provenance badges

import { useState } from 'react';
import {
  CheckCircle2, AlertTriangle, XCircle, Loader2,
  Clock, ChevronDown, ChevronRight, Zap, Info, ShieldAlert
} from 'lucide-react';
import type { LiveTraceItem, ToolStatus, ExecutionMode } from '../../types';

interface TracePanelProps {
  items: LiveTraceItem[];
  queryUnderstanding?: { taskType: string; target: string; reasoning: string };
  strategyMessage?: string;
  planUpdateMessage?: string;
  lowEvidenceAlert?: {
    evidenceStrength: number;
    message: string;
    secondaryStatus: string;
    secondaryReason: string;
  } | null;
}

function StatusIcon({ status }: { status: ToolStatus }) {
  switch (status) {
    case 'success': return <CheckCircle2 size={16} className="text-green-600" />;
    case 'warning': return <AlertTriangle size={16} className="text-orange-500" />;
    case 'error': return <XCircle size={16} className="text-red-500" />;
    case 'running': return <Loader2 size={16} className="text-blue-500 animate-spin" />;
    case 'pending': return <Clock size={16} className="text-gray-300" />;
    default: return <Clock size={16} className="text-gray-300" />;
  }
}

function ConfidenceBar({ value }: { value: number }) {
  const color = value >= 0.75 ? 'bg-green-500' : value >= 0.5 ? 'bg-amber-500' : 'bg-red-500';
  return (
    <div className="flex items-center gap-2 mt-1">
      <div className="confidence-bar flex-1">
        <div
          className={`confidence-bar-fill ${color}`}
          style={{ width: `${value * 100}%` }}
        />
      </div>
      <span className="text-xs font-mono text-rs-text-secondary w-10 text-right">
        {(value * 100).toFixed(0)}%
      </span>
    </div>
  );
}

// ── Provenance Badge ─────────────────────────────────────────────────────────

interface ProvenanceBadgeProps {
  executionMode?: ExecutionMode;
  algorithm?: string;
  evidenceExcludable?: boolean;
}

function ProvenanceBadge({ executionMode, algorithm, evidenceExcludable }: ProvenanceBadgeProps) {
  if (!executionMode) return null;

  const configs: Record<ExecutionMode, { label: string; color: string; title: string }> = {
    LIVE_ALGORITHM: {
      label: 'LIVE',
      color: 'bg-teal-100 text-teal-800 border border-teal-300',
      title: `Real CPU algorithm running on actual pixels. Algorithm: ${algorithm || 'unknown'}`,
    },
    LIVE_MODEL: {
      label: 'LIVE MODEL',
      color: 'bg-blue-100 text-blue-800 border border-blue-300',
      title: `Live ML model inference. Algorithm: ${algorithm || 'unknown'}`,
    },
    REMOTE_MODEL: {
      label: 'GPU',
      color: 'bg-purple-100 text-purple-800 border border-purple-300',
      title: `Remote GPU model inference. Algorithm: ${algorithm || 'unknown'}`,
    },
    PRECOMPUTED_MODEL_OUTPUT: {
      label: 'PRECOMPUTED',
      color: 'bg-blue-50 text-blue-700 border border-blue-200',
      title: `Pre-run GPU model output (verified asset). Algorithm: ${algorithm || 'unknown'}`,
    },
    SIMULATED: {
      label: 'DEMO',
      color: 'bg-amber-100 text-amber-800 border border-amber-300',
      title: `Simulated/demo result — not real pixel computation. ${evidenceExcludable ? 'Excluded from evidence scoring.' : ''}`,
    },
  };

  const cfg = configs[executionMode];
  if (!cfg) return null;

  return (
    <span
      className={`inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider ${cfg.color}`}
      title={cfg.title}
    >
      {cfg.label}
    </span>
  );
}

// ── Excluded badge ─────────────────────────────────────────────────────────

function ExcludedBadge() {
  return (
    <span
      className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider bg-red-50 text-red-700 border border-red-200"
      title="This result is excluded from evidence scoring (e.g. UNRELIABLE_REGISTRATION or SIMULATED mode)"
    >
      ⊘ EXCLUDED
    </span>
  );
}

// ── Warnings expander ──────────────────────────────────────────────────────

function WarningsList({ warnings }: { warnings: string[] }) {
  const [open, setOpen] = useState(false);
  if (!warnings || warnings.length === 0) return null;
  return (
    <div className="mt-1">
      <button
        onClick={e => { e.stopPropagation(); setOpen(o => !o); }}
        className="text-[10px] text-amber-600 hover:text-amber-700 font-medium flex items-center gap-1"
      >
        <AlertTriangle size={9} />
        {warnings.length} warning{warnings.length > 1 ? 's' : ''}
        {open ? <ChevronDown size={9} /> : <ChevronRight size={9} />}
      </button>
      {open && (
        <ul className="mt-1 ml-3 space-y-0.5 list-disc list-outside text-[10px] text-amber-700">
          {warnings.slice(0, 5).map((w, i) => (
            <li key={i}>{w}</li>
          ))}
          {warnings.length > 5 && <li>…{warnings.length - 5} more</li>}
        </ul>
      )}
    </div>
  );
}

// ── Trace row ──────────────────────────────────────────────────────────────

function TraceItemRow({ item, index }: { item: LiveTraceItem; index: number }) {
  const [expanded, setExpanded] = useState(false);
  const hasDetail = item.status === 'success' || item.status === 'warning';
  const isAuto = item.is_auto_inserted;
  const isExcluded = item.evidence_excludable === true;
  const isUnreliableReg =
    item.registration_quality === 'FAILED' ||
    (item.result?.unreliable_registration === true);

  return (
    <div
      className="animate-trace-appear border-b border-gray-50 last:border-0"
      style={{ animationDelay: `${index * 60}ms` }}
    >
      <div
        className={`flex items-start gap-3 py-2.5 px-1 ${hasDetail ? 'cursor-pointer hover:bg-gray-50 rounded-lg' : ''}`}
        onClick={() => hasDetail && setExpanded(!expanded)}
      >
        {/* Status icon */}
        <div className="mt-0.5 flex-shrink-0">
          <StatusIcon status={item.status} />
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className={`text-sm font-semibold ${
              item.status === 'running' ? 'text-blue-700' :
              item.status === 'success' ? 'text-rs-text-primary' :
              item.status === 'warning' ? 'text-orange-700' :
              item.status === 'error' ? 'text-red-700' :
              'text-rs-text-muted'
            }`}>
              {item.step_name}
            </span>

            {/* Provenance badge */}
            <ProvenanceBadge
              executionMode={item.execution_mode}
              algorithm={item.algorithm}
              evidenceExcludable={item.evidence_excludable}
            />

            {/* Excluded badge */}
            {isExcluded && item.status !== 'pending' && item.status !== 'running' && (
              <ExcludedBadge />
            )}

            {/* Auto-inserted badge */}
            {isAuto && (
              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-bold bg-orange-100 text-orange-700 border border-orange-200 uppercase">
                <Zap size={9} /> AUTO-INSERTED
              </span>
            )}

            {/* Unreliable registration warning */}
            {isUnreliableReg && (
              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-bold bg-red-100 text-red-700 border border-red-200 uppercase">
                UNRELIABLE_REG
              </span>
            )}

            {item.execution_time_ms && item.execution_time_ms > 0 ? (
              <span className="text-[10px] text-rs-text-muted font-mono ml-auto">{item.execution_time_ms}ms</span>
            ) : null}
          </div>

          {/* Algorithm label */}
          {item.algorithm && item.execution_mode === 'LIVE_ALGORITHM' && (
            <p className="text-[10px] text-teal-700 font-mono mt-0.5 flex items-center gap-1">
              <span className="opacity-60">algo:</span> {item.algorithm}
            </p>
          )}

          <p className="text-xs text-rs-text-secondary mt-0.5 leading-snug">{item.description}</p>

          {item.status === 'running' && (
            <div className="flex items-center gap-2 mt-1.5">
              <div className="flex gap-1">
                {[0, 1, 2].map(i => (
                  <span
                    key={i}
                    className="w-1.5 h-1.5 rounded-full bg-blue-500"
                    style={{ animation: `runningDot 1.2s ease-in-out ${i * 0.2}s infinite` }}
                  />
                ))}
              </div>
              <span className="text-xs text-blue-600 font-medium">Running…</span>
            </div>
          )}

          {item.message && item.status !== 'running' && item.status !== 'pending' && (
            <p className={`text-xs mt-1 font-medium ${
              item.status === 'success' ? 'text-green-700' :
              item.status === 'warning' ? 'text-orange-700' :
              item.status === 'error' ? 'text-red-700' : 'text-rs-text-secondary'
            }`}>
              {item.message}
            </p>
          )}

          {item.confidence !== undefined && item.confidence > 0 && item.status !== 'running' && (
            <ConfidenceBar value={item.confidence} />
          )}

          {/* Warnings */}
          {item.warnings && item.status !== 'running' && (
            <WarningsList warnings={item.warnings} />
          )}
        </div>

        {hasDetail && (
          <div className="mt-1 flex-shrink-0 text-rs-text-muted">
            {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          </div>
        )}
      </div>

      {/* Expanded detail */}
      {expanded && hasDetail && item.result && (
        <div className="ml-7 mb-2 pl-3 border-l-2 border-gray-100">
          <div className="bg-gray-50 rounded-lg p-2.5 space-y-1">
            {Object.entries(item.result)
              .filter(([k]) => !['note', 'visual_output', 'limitations'].includes(k))
              .slice(0, 8)
              .map(([k, v]) => (
                <div key={k} className="flex gap-2 text-xs">
                  <span className="text-rs-text-muted font-medium min-w-[120px] flex-shrink-0">
                    {k.replace(/_/g, ' ')}
                  </span>
                  <span className={`font-mono break-all ${
                    k === 'unreliable_registration' && v === true ? 'text-red-700 font-bold' :
                    k === 'changed_area_pct' && v === null ? 'text-red-600 italic' :
                    'text-rs-text-primary'
                  }`}>
                    {v === null ? 'null (excluded)' :
                     typeof v === 'object' ? JSON.stringify(v) : String(v)}
                  </span>
                </div>
              ))}
            {item.result.note && (
              <div className="flex items-start gap-1 mt-1 pt-1 border-t border-gray-200">
                <Info size={10} className="text-rs-text-muted mt-0.5 flex-shrink-0" />
                <p className="text-[10px] text-rs-text-muted italic">{String(item.result.note)}</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default function TracePanel({ items, queryUnderstanding, strategyMessage, planUpdateMessage, lowEvidenceAlert }: TracePanelProps) {
  return (
    <div className="space-y-1">
      {/* Query Understanding */}
      {queryUnderstanding && (
        <div className="flex items-start gap-3 py-2.5 px-1 border-b border-gray-50 animate-trace-appear">
          <CheckCircle2 size={16} className="text-green-600 mt-0.5 flex-shrink-0" />
          <div>
            <span className="text-sm font-semibold text-rs-text-primary">Query Understood</span>
            <p className="text-xs text-rs-text-secondary mt-0.5">{queryUnderstanding.reasoning}</p>
            <div className="flex flex-wrap gap-1.5 mt-1.5">
              <span className="badge badge-navy text-[10px]">{queryUnderstanding.taskType.replace(/_/g, ' ')}</span>
              <span className="badge badge-teal text-[10px]">target: {queryUnderstanding.target}</span>
            </div>
          </div>
        </div>
      )}

      {/* Strategy */}
      {strategyMessage && (
        <div className="flex items-start gap-3 py-2.5 px-1 border-b border-gray-50 animate-trace-appear" style={{animationDelay: '100ms'}}>
          <CheckCircle2 size={16} className="text-green-600 mt-0.5 flex-shrink-0" />
          <div>
            <span className="text-sm font-semibold text-rs-text-primary">Strategy Selected</span>
            <p className="text-xs text-rs-text-secondary mt-0.5">{strategyMessage}</p>
          </div>
        </div>
      )}

      {/* Plan update alert */}
      {planUpdateMessage && (
        <div className="flex items-start gap-3 py-3 px-3 rounded-xl bg-orange-50 border border-orange-200 my-2 animate-fade-in">
          <Zap size={16} className="text-rs-orange mt-0.5 flex-shrink-0" />
          <div>
            <span className="text-sm font-bold text-orange-800">Workflow Updated</span>
            <p className="text-xs text-orange-700 mt-0.5">{planUpdateMessage}</p>
          </div>
        </div>
      )}

      {/* Low Evidence alert */}
      {lowEvidenceAlert && (
        <div className="flex items-start gap-3 py-3 px-3 rounded-xl bg-red-50 border border-red-200 my-2 animate-fade-in">
          <ShieldAlert size={16} className="text-red-600 mt-0.5 flex-shrink-0" />
          <div>
            <span className="text-sm font-bold text-red-800">
              Low Evidence — Strength {(lowEvidenceAlert.evidenceStrength * 100).toFixed(0)}%
            </span>
            <p className="text-xs text-red-700 mt-0.5">{lowEvidenceAlert.message}</p>
            <p className="text-[10px] text-red-600 mt-1 font-mono uppercase tracking-wide">
              {lowEvidenceAlert.secondaryStatus}
            </p>
            {lowEvidenceAlert.secondaryReason && (
              <p className="text-[10px] text-red-600 mt-0.5 italic">{lowEvidenceAlert.secondaryReason}</p>
            )}
          </div>
        </div>
      )}

      {/* Tool steps */}
      {items.map((item, i) => (
        <TraceItemRow key={`${item.tool_name}-${i}`} item={item} index={i} />
      ))}

      {/* Empty state */}
      {items.length === 0 && !queryUnderstanding && (
        <div className="py-8 text-center text-rs-text-muted">
          <Clock size={24} className="mx-auto mb-2 opacity-40" />
          <p className="text-sm">Agent trace will appear here</p>
        </div>
      )}
    </div>
  );
}
