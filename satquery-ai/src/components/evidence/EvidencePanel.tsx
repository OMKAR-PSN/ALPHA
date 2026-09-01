// Evidence Check Panel — real evidence strength breakdown from evidence.py

import { CheckCircle2, AlertTriangle, Info, FlaskConical, ShieldCheck } from 'lucide-react';
import type { EvidenceStatus, EvidenceBreakdown } from '../../types';

interface EvidencePanelProps {
  evidenceStatus: EvidenceStatus;
  evidencePoints: string[];
  confidence: number;
  conflicts?: unknown[];
  // Real evidence breakdown from evidence.py
  evidenceBreakdown?: EvidenceBreakdown;
  evidenceFormula?: string;
  evidenceInterpretation?: string;
  hasRealImages?: boolean;
}

function ConfBar({ value, color }: { value: number; color: string }) {
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
        <div className={`h-full rounded-full transition-all duration-700 ${color}`} style={{ width: `${Math.max(0, Math.min(1, value)) * 100}%` }} />
      </div>
      <span className="text-xs font-bold font-mono w-10 text-right">{(Math.max(0, Math.min(1, value)) * 100).toFixed(0)}%</span>
    </div>
  );
}

// ── Evidence breakdown from evidence.py ──────────────────────────────────────

function BreakdownFactor({
  label, score, reason, weight
}: { label: string; score: number | null; reason: string; weight: number }) {
  const barColor = score === null ? 'bg-gray-300' :
    score >= 0.75 ? 'bg-green-500' : score >= 0.5 ? 'bg-amber-500' : 'bg-red-500';
  return (
    <div className="p-2.5 rounded-lg bg-white border border-rs-border">
      <div className="flex items-center justify-between mb-1">
        <span className="text-[11px] font-semibold text-rs-text-secondary uppercase tracking-wide">
          {label}
        </span>
        <span className="text-[10px] text-rs-text-muted font-mono">weight {(weight * 100).toFixed(0)}%</span>
      </div>
      {score !== null ? (
        <ConfBar value={score} color={barColor} />
      ) : (
        <p className="text-[10px] text-rs-text-muted italic">Not applicable — weight redistributed</p>
      )}
      <p className="text-[10px] text-rs-text-muted mt-1 leading-snug">{reason}</p>
    </div>
  );
}

function RealEvidenceBreakdown({
  breakdown, formula, interpretation
}: {
  breakdown: EvidenceBreakdown;
  formula?: string;
  interpretation?: string;
}) {
  const factors: { key: keyof EvidenceBreakdown; label: string }[] = [
    { key: 'data_quality', label: 'Data Quality' },
    { key: 'algorithm_confidence', label: 'Algorithm Confidence' },
    { key: 'registration_quality', label: 'Registration Quality' },
    { key: 'cross_method_agreement', label: 'Cross-Method Agreement' },
  ];

  return (
    <div className="space-y-2 mt-3">
      <div className="flex items-center gap-1.5 mb-2">
        <FlaskConical size={12} className="text-teal-600" />
        <p className="text-[11px] font-bold text-teal-800 uppercase tracking-wider">
          Evidence Strength Breakdown
        </p>
        <span className="ml-auto text-[9px] bg-teal-100 text-teal-700 border border-teal-200 px-1.5 py-0.5 rounded font-bold uppercase">
          LIVE_ALGORITHM
        </span>
      </div>

      {factors.map(({ key, label }) => {
        const factor = breakdown[key];
        if (!factor) return null;
        return (
          <BreakdownFactor
            key={key}
            label={label}
            score={factor.score ?? null}
            reason={factor.reason || ''}
            weight={factor.weight ?? 0}
          />
        );
      })}

      {formula && (
        <div className="mt-2 p-2 rounded bg-gray-50 border border-gray-100">
          <p className="text-[9px] text-rs-text-muted font-mono leading-relaxed break-all">{formula}</p>
        </div>
      )}

      {interpretation && (
        <p className="text-xs text-rs-text-secondary font-medium italic mt-1">{interpretation}</p>
      )}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function EvidencePanel({
  evidenceStatus,
  evidencePoints,
  confidence,
  conflicts = [],
  evidenceBreakdown,
  evidenceFormula,
  evidenceInterpretation,
  hasRealImages = false,
}: EvidencePanelProps) {
  const isConsistent = evidenceStatus === 'consistent';
  const isConflicting = evidenceStatus === 'conflicting';

  return (
    <div className="space-y-4">

      {/* Evidence Status Banner */}
      <div className={`rounded-xl p-4 border ${
        isConsistent
          ? 'bg-green-50 border-green-200'
          : isConflicting
          ? 'bg-orange-50 border-orange-200'
          : 'bg-gray-50 border-gray-200'
      }`}>
        <div className="flex items-center gap-2 mb-2">
          {isConsistent ? (
            <CheckCircle2 size={18} className="text-green-600" />
          ) : isConflicting ? (
            <AlertTriangle size={18} className="text-orange-600" />
          ) : (
            <Info size={18} className="text-gray-400" />
          )}
          <span className={`font-bold text-sm uppercase tracking-wide ${
            isConsistent ? 'text-green-800' : isConflicting ? 'text-orange-800' : 'text-gray-600'
          }`}>
            {isConsistent ? 'Consistent Evidence' : isConflicting ? 'Conflicting Evidence' : 'Pending'}
          </span>

          {/* Real images badge */}
          {hasRealImages && (
            <span className="ml-auto flex items-center gap-1 text-[10px] bg-teal-100 text-teal-700 border border-teal-200 px-1.5 py-0.5 rounded font-bold uppercase">
              <ShieldCheck size={9} /> Real Images
            </span>
          )}
        </div>
        {isConflicting && (
          <p className="text-xs text-orange-700">Cross-tool disagreement detected. Controller triggered additional analysis.</p>
        )}
        {!hasRealImages && (
          <p className="text-[10px] text-rs-text-muted italic mt-1">
            Demo mode — real CPU algorithms will run when actual satellite images are uploaded.
          </p>
        )}
      </div>

      {/* Real evidence breakdown (when available) */}
      {evidenceBreakdown && (
        <RealEvidenceBreakdown
          breakdown={evidenceBreakdown}
          formula={evidenceFormula}
          interpretation={evidenceInterpretation}
        />
      )}

      {/* Evidence points */}
      {evidencePoints.length > 0 && (
        <div className="space-y-2">
          <p className="section-label">Evidence Sources</p>
          {evidencePoints.map((point, i) => {
            const isLive = point.startsWith('[LIVE]');
            const isDemo = point.startsWith('[DEMO]');
            return (
              <div key={i} className="flex items-center gap-2 text-xs text-rs-text-secondary">
                {isLive ? (
                  <span className="w-3 h-3 rounded-full bg-teal-500 flex-shrink-0" title="LIVE_ALGORITHM" />
                ) : isDemo ? (
                  <span className="w-3 h-3 rounded-full bg-amber-400 flex-shrink-0" title="SIMULATED" />
                ) : (
                  <CheckCircle2 size={13} className="text-green-500 flex-shrink-0" />
                )}
                <span className={isLive ? 'text-teal-700 font-medium' : isDemo ? 'text-amber-700' : ''}>
                  {point}
                </span>
              </div>
            );
          })}
          {/* Legend */}
          <div className="flex gap-3 mt-1 text-[10px] text-rs-text-muted">
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-teal-500" /> LIVE algorithm</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-amber-400" /> DEMO / simulated</span>
          </div>
        </div>
      )}

      {/* Overall confidence */}
      <div className="p-3 rounded-lg bg-navy-50 border border-navy-100">
        <p className="text-xs font-semibold text-rs-navy mb-2 uppercase tracking-wide">
          Evidence Strength Score
          {evidenceBreakdown && (
            <span className="ml-2 text-[9px] font-normal text-teal-600 normal-case italic">from evidence_strength_calculator_v1</span>
          )}
        </p>
        <div className="flex items-center gap-3">
          <div className="flex-1 h-2.5 bg-navy-200 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-1000 ${
                confidence >= 0.75 ? 'bg-green-500' : confidence >= 0.5 ? 'bg-amber-500' : 'bg-red-500'
              }`}
              style={{ width: `${confidence * 100}%` }}
            />
          </div>
          <span className="text-lg font-extrabold text-rs-navy font-mono">{(confidence * 100).toFixed(0)}%</span>
        </div>
        <p className={`text-xs mt-1 font-medium ${
          confidence >= 0.75 ? 'text-green-700' : confidence >= 0.5 ? 'text-amber-700' : 'text-red-700'
        }`}>
          {confidence >= 0.75 ? 'HIGH — Result is reliable' : confidence >= 0.5 ? 'MEDIUM — Use with caution' : 'LOW — Insufficient evidence'}
        </p>
      </div>
    </div>
  );
}
