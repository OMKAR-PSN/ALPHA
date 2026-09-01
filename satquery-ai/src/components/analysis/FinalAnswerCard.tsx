// Final Answer Card — with "WHY THIS ANSWER?" Evidence Trail button

import { useState } from 'react';
import { CheckCircle2, Quote, Info, Shield } from 'lucide-react';
import type { EvidenceStatus, ConfidenceLevel, LiveTraceItem, VisualOutput } from '../../types';
import EvidenceTrailModal from '../evidence/EvidenceTrailModal';

interface ImageMeta {
  sensor: string;
  acquisition_date: string;
  resolution_m: number;
  cloud_coverage_pct: number;
  image_type: string;
  cloud_status: string;
}

interface FinalAnswerCardProps {
  query: string;
  answer: string;
  confidence: number;
  confidenceLevel: ConfidenceLevel;
  evidenceStatus: EvidenceStatus;
  evidencePoints: string[];
  analysisId?: string;
  // For evidence trail
  traceItems?: LiveTraceItem[];
  images?: ImageMeta[];
  visualOutputs?: VisualOutput[];
}

export default function FinalAnswerCard({
  query, answer, confidence, confidenceLevel, evidenceStatus, evidencePoints,
  analysisId = 'demo-0000',
  traceItems = [],
  images = [],
  visualOutputs = [],
}: FinalAnswerCardProps) {
  const [trailOpen, setTrailOpen] = useState(false);

  const confColor = confidence >= 0.75
    ? 'text-green-700 bg-green-50 border-green-200'
    : confidence >= 0.5
    ? 'text-amber-700 bg-amber-50 border-amber-200'
    : 'text-red-700 bg-red-50 border-red-200';

  return (
    <>
      <div className="panel overflow-hidden">
        {/* Header */}
        <div className="bg-rs-navy px-5 py-4">
          <p className="text-navy-300 text-xs font-semibold uppercase tracking-widest mb-1">Your Query</p>
          <p className="text-white font-medium text-sm italic">"{query}"</p>
        </div>

        <div className="p-5 space-y-4">
          {/* Answer */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <div className="w-6 h-6 rounded-full bg-green-100 flex items-center justify-center">
                <CheckCircle2 size={14} className="text-green-600" />
              </div>
              <span className="font-bold text-sm text-rs-text-primary uppercase tracking-wide">Final Answer</span>
            </div>

            <div className="relative pl-4 border-l-2 border-rs-teal">
              <Quote size={14} className="absolute -top-1 -left-0.5 text-rs-teal opacity-50" />
              <p className="text-sm text-rs-text-primary leading-relaxed">{answer}</p>
            </div>
          </div>

          {/* Confidence + evidence row */}
          <div className="grid grid-cols-2 gap-3">
            <div className={`p-3 rounded-xl border ${confColor}`}>
              <p className="text-[10px] font-bold uppercase tracking-widest mb-1 opacity-70">Confidence</p>
              <p className="text-2xl font-extrabold font-mono">{(confidence * 100).toFixed(0)}%</p>
              <p className="text-xs font-semibold uppercase mt-0.5 opacity-80">{confidenceLevel}</p>
            </div>

            <div className={`p-3 rounded-xl border ${
              evidenceStatus === 'consistent'
                ? 'bg-green-50 border-green-200 text-green-800'
                : evidenceStatus === 'conflicting'
                ? 'bg-orange-50 border-orange-200 text-orange-800'
                : 'bg-gray-50 border-gray-200 text-gray-600'
            }`}>
              <p className="text-[10px] font-bold uppercase tracking-widest mb-1 opacity-70">Evidence</p>
              <div className="flex items-center gap-1.5">
                <CheckCircle2 size={16} />
                <span className="text-sm font-bold uppercase">{evidenceStatus}</span>
              </div>
            </div>
          </div>

          {/* Evidence points */}
          {evidencePoints.length > 0 && (
            <div className="space-y-1.5">
              <p className="text-[10px] font-bold uppercase tracking-widest text-rs-text-muted">Grounded in</p>
              {evidencePoints.map((p, i) => (
                <div key={i} className="flex items-center gap-2 text-xs text-rs-text-secondary">
                  <CheckCircle2 size={12} className="text-green-500 flex-shrink-0" />
                  {p}
                </div>
              ))}
            </div>
          )}

          {/* ── WHY THIS ANSWER? button ── */}
          <button
            onClick={() => setTrailOpen(true)}
            className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl
                       bg-rs-navy text-white text-sm font-bold tracking-wide
                       hover:bg-navy-800 active:scale-[0.98] transition-all group"
          >
            <Shield size={15} className="text-rs-teal group-hover:scale-110 transition-transform" />
            WHY THIS ANSWER?
            <span className="text-navy-400 text-xs font-normal">· Evidence Trail</span>
          </button>

          {/* Demo disclaimer */}
          <div className="flex items-start gap-2 p-2.5 rounded-lg bg-amber-50 border border-amber-100">
            <Info size={13} className="text-amber-600 flex-shrink-0 mt-0.5" />
            <p className="text-[11px] text-amber-700">
              <strong>Demo mode:</strong> All results are simulated for architecture demonstration.
            </p>
          </div>
        </div>
      </div>

      {/* Evidence Trail Modal */}
      <EvidenceTrailModal
        open={trailOpen}
        onClose={() => setTrailOpen(false)}
        query={query}
        analysisId={analysisId}
        timestamp={new Date().toISOString()}
        images={images}
        traceItems={traceItems}
        finalAnswer={answer}
        confidence={confidence}
        confidenceLevel={confidenceLevel}
        evidenceStatus={evidenceStatus}
        evidencePoints={evidencePoints}
        visualOutputs={visualOutputs}
      />
    </>
  );
}
