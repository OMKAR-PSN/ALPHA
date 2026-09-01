// EvidenceTrailModal.tsx
// Full-screen slide-in overlay: "WHY THIS ANSWER?"
// Shows the complete reasoning chain a judge needs to trust the result.

import { useEffect, useRef } from 'react';
import {
  X, CheckCircle2, AlertTriangle, Clock, Database,
  Layers, Shield, Quote, Info, Zap, BarChart3, FileText
} from 'lucide-react';
import type { LiveTraceItem, VisualOutput } from '../../types';

interface ImageMeta {
  sensor: string;
  acquisition_date: string;
  resolution_m: number;
  cloud_coverage_pct: number;
  image_type: string;
  cloud_status: string;
}

interface EvidenceTrailProps {
  open: boolean;
  onClose: () => void;

  // Query
  query: string;
  analysisId: string;
  timestamp?: string;

  // Images
  images: ImageMeta[];

  // Trace
  traceItems: LiveTraceItem[];

  // Results
  finalAnswer: string;
  confidence: number;
  confidenceLevel: string;
  evidenceStatus: string;
  evidencePoints: string[];

  // Visuals (optional thumbnails)
  visualOutputs: VisualOutput[];
}

function ConfidenceBar({ value, color = 'bg-rs-teal' }: { value: number; color?: string }) {
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-1000 ${color}`}
          style={{ width: `${value * 100}%` }}
        />
      </div>
      <span className="text-xs font-bold font-mono w-10 text-right text-rs-text-primary">
        {(value * 100).toFixed(0)}%
      </span>
    </div>
  );
}

function SectionHeader({ icon: Icon, label }: { icon: React.ElementType; label: string }) {
  return (
    <div className="flex items-center gap-2 pb-2 border-b border-gray-100 mb-3">
      <Icon size={14} className="text-rs-text-muted" />
      <span className="text-[10px] font-bold uppercase tracking-widest text-rs-text-muted">{label}</span>
    </div>
  );
}

export default function EvidenceTrailModal({
  open, onClose,
  query, analysisId, timestamp,
  images, traceItems,
  finalAnswer, confidence, confidenceLevel, evidenceStatus, evidencePoints,
  visualOutputs,
}: EvidenceTrailProps) {
  const overlayRef = useRef<HTMLDivElement>(null);

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [onClose]);

  // Prevent body scroll when open
  useEffect(() => {
    document.body.style.overflow = open ? 'hidden' : '';
    return () => { document.body.style.overflow = ''; };
  }, [open]);

  if (!open) return null;

  const confColor = confidence >= 0.75 ? 'bg-green-500' : confidence >= 0.5 ? 'bg-amber-400' : 'bg-red-500';
  const confTextColor = confidence >= 0.75 ? 'text-green-700' : confidence >= 0.5 ? 'text-amber-700' : 'text-red-700';
  const confBg = confidence >= 0.75 ? 'bg-green-50 border-green-200' : confidence >= 0.5 ? 'bg-amber-50 border-amber-200' : 'bg-red-50 border-red-200';

  const totalMs = traceItems.reduce((s, t) => s + (t.execution_time_ms || 0), 0);
  const successCount = traceItems.filter(t => t.status === 'success' || t.status === 'warning').length;
  const autoInserted = traceItems.filter(t => t.is_auto_inserted);

  // Find optical + SAR images
  const opticalImages = images.filter(i => i.image_type === 'Optical');
  const sarImages = images.filter(i => i.image_type === 'SAR');

  // Find change map
  const changeMap = visualOutputs.find(v => v.type === 'change_map');

  return (
    <>
      {/* Backdrop */}
      <div
        ref={overlayRef}
        className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm"
        onClick={e => e.target === overlayRef.current && onClose()}
        style={{ animation: 'fadeIn 0.2s ease' }}
      />

      {/* Slide-up panel */}
      <div
        className="fixed inset-x-0 bottom-0 top-12 z-50 flex items-end justify-center pointer-events-none"
      >
        <div
          className="w-full max-w-4xl bg-white rounded-t-2xl shadow-2xl pointer-events-auto flex flex-col"
          style={{
            maxHeight: 'calc(100vh - 56px)',
            animation: 'slideUpModal 0.35s cubic-bezier(0.32, 0.72, 0, 1)',
          }}
        >
          {/* ── Header ── */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-rs-border bg-rs-navy rounded-t-2xl flex-shrink-0">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-white/10 flex items-center justify-center">
                <Shield size={16} className="text-rs-teal" />
              </div>
              <div>
                <h2 className="text-white font-bold text-sm">Why This Answer?</h2>
                <p className="text-navy-300 text-xs font-mono">
                  Evidence Trail · ID {analysisId.slice(0, 8)}
                  {timestamp && ` · ${new Date(timestamp).toLocaleTimeString()}`}
                </p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="w-8 h-8 rounded-lg bg-white/10 hover:bg-white/20 flex items-center justify-center text-white/70 hover:text-white transition-all"
            >
              <X size={16} />
            </button>
          </div>

          {/* ── Scrollable body ── */}
          <div className="overflow-y-auto flex-1 p-6">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-5">

              {/* ─── Column 1: Query + Images ─── */}
              <div className="space-y-5">

                {/* USER QUERY */}
                <div className="panel p-4">
                  <SectionHeader icon={Quote} label="User Query" />
                  <div className="pl-3 border-l-2 border-rs-teal">
                    <p className="text-sm text-rs-text-primary italic leading-relaxed">"{query}"</p>
                  </div>
                </div>

                {/* DATA USED */}
                <div className="panel p-4">
                  <SectionHeader icon={Database} label="Data Used" />
                  <div className="space-y-2">
                    {images.map((img, i) => (
                      <div key={i} className="p-2.5 rounded-lg bg-gray-50 border border-gray-100">
                        <div className="flex items-center justify-between mb-1">
                          <span className={`badge text-[10px] font-bold ${img.image_type === 'SAR' ? 'badge-navy' : 'badge-teal'}`}>
                            {img.image_type}
                          </span>
                          <span className={`text-[10px] font-medium ${
                            img.cloud_status === 'Clear' || img.cloud_status === 'N/A (SAR)'
                              ? 'text-green-600' : 'text-orange-600'
                          }`}>
                            {img.cloud_status}
                          </span>
                        </div>
                        <p className="text-xs font-semibold text-rs-text-primary">{img.sensor}</p>
                        <p className="text-[11px] text-rs-text-muted font-mono">{img.acquisition_date}</p>
                        <p className="text-[10px] text-rs-text-muted">{img.resolution_m}m · Cloud {img.cloud_coverage_pct}%</p>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Stats summary */}
                <div className="grid grid-cols-2 gap-2">
                  <div className="p-3 rounded-xl bg-navy-50 border border-navy-100 text-center">
                    <p className="text-2xl font-extrabold text-rs-navy">{successCount}</p>
                    <p className="text-[10px] text-rs-text-muted uppercase tracking-wide">Tools Run</p>
                  </div>
                  <div className="p-3 rounded-xl bg-teal-50 border border-teal-100 text-center">
                    <p className="text-2xl font-extrabold text-rs-teal">{totalMs}</p>
                    <p className="text-[10px] text-rs-text-muted uppercase tracking-wide">Total ms</p>
                  </div>
                  {autoInserted.length > 0 && (
                    <div className="col-span-2 p-2.5 rounded-xl bg-orange-50 border border-orange-200 flex items-center gap-2">
                      <Zap size={13} className="text-rs-orange flex-shrink-0" />
                      <p className="text-[11px] text-orange-700 font-medium">
                        {autoInserted.length} step{autoInserted.length > 1 ? 's' : ''} auto-inserted by controller
                      </p>
                    </div>
                  )}
                </div>
              </div>

              {/* ─── Column 2: Tool Execution Trace ─── */}
              <div className="panel p-4">
                <SectionHeader icon={Layers} label="Tools Executed (in order)" />
                <div className="space-y-1.5">
                  {traceItems.map((item, i) => (
                    <div
                      key={i}
                      className={`flex items-start gap-2.5 p-2 rounded-lg border ${
                        item.status === 'success' ? 'bg-green-50 border-green-100'
                        : item.status === 'warning' ? 'bg-orange-50 border-orange-100'
                        : item.status === 'error' ? 'bg-red-50 border-red-100'
                        : 'bg-gray-50 border-gray-100'
                      }`}
                    >
                      <div className="flex-shrink-0 mt-0.5">
                        {item.status === 'success' ? <CheckCircle2 size={13} className="text-green-600" />
                         : item.status === 'warning' ? <AlertTriangle size={13} className="text-orange-500" />
                         : <Clock size={13} className="text-gray-400" />}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1.5">
                          <span className="text-xs font-semibold text-rs-text-primary truncate">
                            {item.step_name}
                          </span>
                          {item.is_auto_inserted && (
                            <span className="badge text-[9px] font-bold bg-orange-100 text-orange-700 border-orange-200 uppercase px-1 py-0 flex-shrink-0">
                              ⚡ auto
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-2 mt-0.5">
                          {item.confidence !== undefined && item.confidence > 0 && (
                            <ConfidenceBar value={item.confidence} color={confColor} />
                          )}
                          {item.execution_time_ms && item.execution_time_ms > 0 && (
                            <span className="text-[10px] text-rs-text-muted font-mono flex-shrink-0">
                              {item.execution_time_ms}ms
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* ─── Column 3: Evidence + Answer ─── */}
              <div className="space-y-5">

                {/* EVIDENCE */}
                <div className="panel p-4">
                  <SectionHeader icon={Shield} label="Evidence" />

                  {/* Cross-modal */}
                  <div className="space-y-2 mb-3">
                    {opticalImages.length > 0 && (
                      <div>
                        <div className="flex justify-between mb-0.5">
                          <span className="text-[11px] font-semibold text-rs-text-secondary">Optical</span>
                          <span className="text-[11px] text-rs-text-muted">{opticalImages[0]?.sensor}</span>
                        </div>
                        <ConfidenceBar value={0.82} color="bg-blue-500" />
                      </div>
                    )}
                    {sarImages.length > 0 && (
                      <div>
                        <div className="flex justify-between mb-0.5">
                          <span className="text-[11px] font-semibold text-rs-text-secondary">SAR</span>
                          <span className="text-[11px] text-rs-text-muted">{sarImages[0]?.sensor}</span>
                        </div>
                        <ConfidenceBar value={0.85} color="bg-purple-500" />
                      </div>
                    )}
                  </div>

                  <div className={`flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-semibold border ${
                    evidenceStatus === 'consistent'
                      ? 'bg-green-50 border-green-200 text-green-800'
                      : 'bg-orange-50 border-orange-200 text-orange-800'
                  }`}>
                    {evidenceStatus === 'consistent'
                      ? <><CheckCircle2 size={13} /> Cross-modal agreement: HIGH</>
                      : <><AlertTriangle size={13} /> Cross-modal disagreement detected</>
                    }
                  </div>

                  {evidencePoints.length > 0 && (
                    <div className="mt-3 space-y-1">
                      {evidencePoints.map((p, i) => (
                        <div key={i} className="flex items-center gap-1.5 text-[11px] text-rs-text-secondary">
                          <CheckCircle2 size={11} className="text-green-500 flex-shrink-0" />
                          {p}
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Change map thumbnail */}
                {changeMap && (
                  <div className="panel overflow-hidden">
                    <div className="px-3 pt-3">
                      <SectionHeader icon={BarChart3} label="Change Map" />
                    </div>
                    <img
                      src={`data:image/png;base64,${changeMap.b64}`}
                      alt="Change Map"
                      className="w-full object-cover"
                      style={{ height: '120px' }}
                    />
                    <p className="text-[10px] text-rs-text-muted text-center py-1.5">
                      Red/orange = detected change · Green = stable
                    </p>
                  </div>
                )}

                {/* FINAL ANSWER */}
                <div className={`panel p-4 border-2 ${confBg}`}>
                  <SectionHeader icon={FileText} label="Final Answer" />
                  <p className="text-xs text-rs-text-primary leading-relaxed mb-3">{finalAnswer}</p>
                  <div className="flex items-center justify-between">
                    <div>
                      <p className={`text-2xl font-extrabold font-mono ${confTextColor}`}>
                        {(confidence * 100).toFixed(0)}%
                      </p>
                      <p className={`text-[10px] font-bold uppercase ${confTextColor}`}>
                        {confidenceLevel} confidence
                      </p>
                    </div>
                    <div className={`flex items-center gap-1.5 px-3 py-2 rounded-lg font-semibold text-xs ${
                      evidenceStatus === 'consistent'
                        ? 'bg-green-100 text-green-800'
                        : 'bg-orange-100 text-orange-800'
                    }`}>
                      <CheckCircle2 size={13} />
                      Result Verified
                    </div>
                  </div>
                </div>

                {/* Demo disclaimer */}
                <div className="flex items-start gap-2 p-2.5 rounded-lg bg-amber-50 border border-amber-100">
                  <Info size={12} className="text-amber-600 flex-shrink-0 mt-0.5" />
                  <p className="text-[10px] text-amber-700">
                    <strong>Demo mode:</strong> All analysis results are simulated for architecture demonstration.
                  </p>
                </div>
              </div>

            </div>
          </div>
        </div>
      </div>

      <style>{`
        @keyframes fadeIn { from { opacity: 0 } to { opacity: 1 } }
        @keyframes slideUpModal {
          from { transform: translateY(40px); opacity: 0; }
          to   { transform: translateY(0);   opacity: 1; }
        }
      `}</style>
    </>
  );
}
