// Analysis Page — Full workspace with AOI, Evidence Trail, PDF Export, Query History

import { useState, useEffect, useRef } from 'react';
import {
  Play, RotateCcw, AlertCircle, Loader2,
  LayoutPanelLeft, Activity, Satellite, Map, Clock,
  FileDown, ChevronRight, ChevronDown
} from 'lucide-react';
import type { DemoScenario, LiveTraceItem, VisualOutput, ConfidenceLevel, EvidenceStatus, EvidenceBreakdown } from '../types';
import { fetchDemoScenarios, runAnalysis, runDemoScenario, type AnalysisResult } from '../api/client';
import QueryBox from '../components/query/QueryBox';
import SceneSelector, { ImageMetaPanel } from '../components/query/SceneSelector';
import TracePanel from '../components/trace/TracePanel';
import EvidencePanel from '../components/evidence/EvidencePanel';
import VisualOutputsGrid from '../components/visualization/VisualOutputs';
import FinalAnswerCard from '../components/analysis/FinalAnswerCard';
import AOIMapSelector, { type AOISelection } from '../components/map/AOIMapSelector';
import QueryHistoryPanel from '../components/history/QueryHistoryPanel';
import { useQueryHistory } from '../hooks/useQueryHistory';
import { generateAnalysisReport } from '../utils/reportGenerator';

type Phase = 'setup' | 'running' | 'done' | 'error';
type LeftTab = 'scene' | 'map' | 'history';

interface AnalysisPageProps {
  initialScenario?: string | null;
}

export default function AnalysisPage({ initialScenario = null }: AnalysisPageProps) {
  // ── State ─────────────────────────────────────────────────────────────────
  const [scenarios, setScenarios] = useState<DemoScenario[]>([]);
  const [selectedScenario, setSelectedScenario] = useState<string | null>(initialScenario);
  const [thumbnails, setThumbnails] = useState<string[]>([]);
  const [query, setQuery] = useState('');
  const [phase, setPhase] = useState<Phase>('setup');
  const [error, setError] = useState('');
  const [leftTab, setLeftTab] = useState<LeftTab>('scene');
  const [aoiSelection, setAoiSelection] = useState<AOISelection | null>(null);
  const [exportingPdf, setExportingPdf] = useState(false);

  // Trace
  const [queryUnderstanding, setQueryUnderstanding] = useState<{taskType: string; target: string; reasoning: string} | null>(null);
  const [strategyMessage, setStrategyMessage] = useState('');
  const [planUpdateMessage, setPlanUpdateMessage] = useState('');
  const [traceItems, setTraceItems] = useState<LiveTraceItem[]>([]);

  // Results
  const [analysisId, setAnalysisId] = useState('demo-0000-0000');
  const [confidence, setConfidence] = useState(0);
  const [confidenceLevel, setConfidenceLevel] = useState<ConfidenceLevel>('low');
  const [evidenceStatus, setEvidenceStatus] = useState<EvidenceStatus>('pending');
  const [finalAnswer, setFinalAnswer] = useState('');
  const [evidencePoints, setEvidencePoints] = useState<string[]>([]);
  const [visualOutputs, setVisualOutputs] = useState<VisualOutput[]>([]);
  const [evidenceBreakdown, setEvidenceBreakdown] = useState<EvidenceBreakdown | undefined>(undefined);
  const [evidenceFormula, setEvidenceFormula] = useState<string | undefined>(undefined);
  const [evidenceInterpretation, setEvidenceInterpretation] = useState<string | undefined>(undefined);
  const [hasRealImages, setHasRealImages] = useState(false);
  // Low-evidence alert
  const [lowEvidenceAlert, setLowEvidenceAlert] = useState<{
    evidenceStrength: number; message: string;
    secondaryStatus: string; secondaryReason: string;
  } | null>(null);

  const traceEndRef = useRef<HTMLDivElement>(null);
  const { history, addEntry, clearHistory } = useQueryHistory();

  // ── Load scenarios ─────────────────────────────────────────────────────────
  useEffect(() => {
    fetchDemoScenarios().then(s => {
      setScenarios(s);
      if (!selectedScenario && s.length > 0) setSelectedScenario(s[0].scenario_id);
    });
  }, []);

  useEffect(() => {
    if (phase === 'running') traceEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }, [traceItems.length]);

  useEffect(() => {
    if (selectedScenario) {
      const s = scenarios.find(x => x.scenario_id === selectedScenario);
      if (s) setQuery(s.default_query);
    }
  }, [selectedScenario, scenarios]);

  const currentScenario = scenarios.find(s => s.scenario_id === selectedScenario);

  // ── Reset ─────────────────────────────────────────────────────────────────
  const reset = () => {
    setPhase('setup');
    setTraceItems([]);
    setQueryUnderstanding(null);
    setStrategyMessage('');
    setPlanUpdateMessage('');
    setFinalAnswer('');
    setEvidencePoints([]);
    setVisualOutputs([]);
    setThumbnails([]);
    setError('');
    setConfidence(0);
    setEvidenceStatus('pending');
    setLowEvidenceAlert(null);
    setEvidenceBreakdown(undefined);
    setEvidenceFormula(undefined);
    setEvidenceInterpretation(undefined);
    setHasRealImages(false);
  };

  // ── Run Analysis ──────────────────────────────────────────────────────────
  const handleAnalyze = async (q: string) => {
    reset();
    // Inject AOI into query if selected
    const enrichedQuery = aoiSelection ? `${q} [AOI: ${aoiSelection.name}]` : q;
    setQuery(enrichedQuery);
    setPhase('running');

    const callbacks = {
      onSessionCreated: (id: string) => setAnalysisId(id),
      onQueryUnderstood: (detail: Record<string, unknown>, _msg: string) => {
        setQueryUnderstanding({
          taskType: String(detail.task_type || ''),
          target: String(detail.target || ''),
          reasoning: String(detail.reasoning || ''),
        });
      },
      onStrategySelected: (_detail: Record<string, unknown>, msg: string) => setStrategyMessage(msg),
      onToolStart: (item: Omit<LiveTraceItem, 'status'>) => {
        setTraceItems(prev => prev.find(x => x.tool_name === item.tool_name) ? prev : [...prev, { ...item, status: 'running' as const }]);
      },
      onToolDone: (item: LiveTraceItem) => {
        setTraceItems(prev => {
          const idx = prev.findIndex(x => x.tool_name === item.tool_name);
          if (idx >= 0) { const n = [...prev]; n[idx] = item; return n; }
          return [...prev, item];
        });
      },
      onPlanUpdated: (msg: string, _plan: string[]) => setPlanUpdateMessage(msg),
      onThumbnails: (thumbs: string[]) => setThumbnails(thumbs),
      onLowEvidence: (strength: number, msg: string, secStatus: string, secReason: string) => {
        setLowEvidenceAlert({ evidenceStrength: strength, message: msg, secondaryStatus: secStatus, secondaryReason: secReason });
      },
      onCompleted: (result: AnalysisResult) => {
        setConfidence(result.confidence);
        setConfidenceLevel(result.confidenceLevel);
        setEvidenceStatus(result.evidenceStatus);
        setFinalAnswer(result.finalAnswer);
        setEvidencePoints(result.evidencePoints);
        setVisualOutputs(result.visualOutputs);
        setEvidenceBreakdown(result.evidenceBreakdown as EvidenceBreakdown | undefined);
        setEvidenceFormula(result.evidenceFormula);
        setEvidenceInterpretation(result.evidenceInterpretation);
        setHasRealImages(result.hasRealImages ?? false);
        setPhase('done');

        // Save to history
        addEntry({
          query: enrichedQuery,
          scenarioId: selectedScenario,
          confidence: result.confidence,
          confidenceLevel: result.confidenceLevel,
          finalAnswer: result.finalAnswer,
          aoiName: aoiSelection?.name,
        });
      },
      onError: (err: string) => { setError(err); setPhase('error'); },
    };

    if (selectedScenario) {
      await runDemoScenario(selectedScenario, enrichedQuery, callbacks);
    } else {
      await runAnalysis(enrichedQuery, null, callbacks);
    }
  };

  // ── PDF Export ────────────────────────────────────────────────────────────
  const handleExportPDF = async () => {
    setExportingPdf(true);
    try {
      await generateAnalysisReport({
        query,
        analysisId,
        aoiName: aoiSelection?.name,
        images: currentScenario?.images ?? [],
        traceItems,
        finalAnswer,
        confidence,
        confidenceLevel,
        evidenceStatus,
        evidencePoints,
        visualOutputs,
      });
    } finally {
      setExportingPdf(false);
    }
  };

  // ── Replay from history ───────────────────────────────────────────────────
  const handleReplay = (entry: (typeof history)[0]) => {
    if (entry.scenarioId) setSelectedScenario(entry.scenarioId);
    handleAnalyze(entry.query);
    setLeftTab('scene');
  };

  const progress = phase === 'done' ? 100
    : phase === 'running'
    ? Math.min(90, (traceItems.filter(t => t.status === 'success' || t.status === 'warning').length / Math.max(traceItems.length, 1)) * 100)
    : 0;

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-rs-bg">

      {/* ── Top bar ── */}
      <div className="bg-white border-b border-rs-border sticky top-14 z-40">
        <div className="max-w-screen-2xl mx-auto px-4 py-2.5 flex items-center gap-4">
          <div className="flex items-center gap-2">
            <Activity size={15} className="text-rs-teal" />
            <span className="font-semibold text-sm text-rs-text-primary">Analysis Workspace</span>
          </div>
          {phase === 'running' && (
            <div className="flex items-center gap-2 text-xs text-blue-600 font-medium">
              <Loader2 size={13} className="animate-spin" />Agent running…
            </div>
          )}
          {phase === 'done' && (
            <div className="flex items-center gap-2 text-xs text-green-600 font-medium">
              <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
              Complete · {(confidence * 100).toFixed(0)}% confidence
            </div>
          )}
          {aoiSelection && (
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-teal-50 border border-teal-200 text-xs text-rs-teal font-medium">
              <Map size={11} /> {aoiSelection.name}
            </div>
          )}
          <div className="ml-auto flex items-center gap-2">
            {/* PDF Export */}
            {phase === 'done' && (
              <button
                onClick={handleExportPDF}
                disabled={exportingPdf}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-rs-navy text-white text-xs font-semibold hover:bg-navy-800 transition-all disabled:opacity-60"
              >
                {exportingPdf
                  ? <Loader2 size={12} className="animate-spin" />
                  : <FileDown size={12} />
                }
                {exportingPdf ? 'Generating…' : 'Export PDF'}
              </button>
            )}
            {phase !== 'setup' && (
              <button onClick={reset} className="btn-ghost text-xs py-1.5 px-3">
                <RotateCcw size={12} /> New Analysis
              </button>
            )}
          </div>
        </div>
        {/* Progress */}
        {(phase === 'running' || phase === 'done') && (
          <div className="h-0.5 bg-gray-100 overflow-hidden">
            <div
              className={`h-full transition-all duration-500 ${phase === 'done' ? 'bg-green-400' : 'bg-rs-teal'}`}
              style={{ width: `${progress}%` }}
            />
          </div>
        )}
      </div>

      <div className="max-w-screen-2xl mx-auto px-4 py-5">
        <div className="grid grid-cols-1 xl:grid-cols-12 gap-5">

          {/* ── LEFT: Tabs (Scene / Map / History) ── */}
          <div className="xl:col-span-3 space-y-4">

            {/* Tab bar */}
            <div className="flex rounded-xl overflow-hidden border border-rs-border bg-white">
              {([
                { id: 'scene', icon: Satellite, label: 'Scene' },
                { id: 'map',   icon: Map,       label: 'Map AOI' },
                { id: 'history', icon: Clock,   label: 'History', badge: history.length > 0 ? history.length : undefined },
              ] as const).map(({ id, icon: Icon, label, badge }) => (
                <button
                  key={id}
                  onClick={() => setLeftTab(id)}
                  className={`flex-1 flex items-center justify-center gap-1.5 py-2.5 text-xs font-semibold transition-all relative ${
                    leftTab === id
                      ? 'bg-rs-navy text-white'
                      : 'text-rs-text-secondary hover:bg-gray-50'
                  }`}
                >
                  <Icon size={13} />
                  {label}
                  {badge !== undefined && (
                    <span className="absolute top-1 right-1 w-4 h-4 rounded-full bg-rs-orange text-white text-[9px] font-bold flex items-center justify-center">
                      {badge}
                    </span>
                  )}
                </button>
              ))}
            </div>

            {/* Scene Tab */}
            {leftTab === 'scene' && (
              <>
                <div className="panel">
                  <div className="panel-header">
                    <span className="panel-title">Demo Scenario</span>
                    <span className="badge badge-orange text-[10px]">Demo</span>
                  </div>
                  <div className="p-3">
                    <SceneSelector
                      scenarios={scenarios}
                      selectedId={selectedScenario}
                      onSelect={id => { setSelectedScenario(id); reset(); }}
                    />
                  </div>
                </div>
                {currentScenario && (
                  <div className="panel">
                    <div className="panel-header">
                      <span className="panel-title">Input Images</span>
                      <span className="text-xs text-rs-text-muted">{currentScenario.images.length} image{currentScenario.images.length > 1 ? 's' : ''}</span>
                    </div>
                    <div className="p-3">
                      <ImageMetaPanel images={currentScenario.images} thumbnails={thumbnails} />
                    </div>
                  </div>
                )}
              </>
            )}

            {/* Map Tab */}
            {leftTab === 'map' && (
              <div className="panel">
                <div className="panel-header">
                  <span className="panel-title">Area of Interest</span>
                  {aoiSelection && <span className="badge badge-teal text-[10px]">Selected</span>}
                </div>
                <div className="p-3">
                  <p className="text-xs text-rs-text-secondary mb-3 leading-snug">
                    Select a region on the map. The AOI will be injected into your query automatically.
                  </p>
                  <AOIMapSelector
                    selectedAOI={aoiSelection}
                    onAOISelected={setAoiSelection}
                  />
                </div>
              </div>
            )}

            {/* History Tab */}
            {leftTab === 'history' && (
              <div className="panel">
                <div className="panel-header">
                  <span className="panel-title">Recent Analyses</span>
                  <span className="text-xs text-rs-text-muted">{history.length}/{10}</span>
                </div>
                <div className="p-3">
                  <QueryHistoryPanel
                    history={history}
                    onReplay={handleReplay}
                    onClear={clearHistory}
                  />
                </div>
              </div>
            )}
          </div>

          {/* ── CENTER: Query + Visuals + Answer ── */}
          <div className="xl:col-span-5 space-y-4">

            {/* Query box */}
            <div className="panel">
              <div className="panel-header">
                <span className="panel-title">Natural-Language Query</span>
                {aoiSelection && (
                  <span className="flex items-center gap-1 text-xs text-rs-teal font-medium">
                    <Map size={11} /> AOI active
                  </span>
                )}
              </div>
              <div className="p-4">
                <QueryBox
                  onSubmit={handleAnalyze}
                  disabled={phase === 'running'}
                  initialQuery={currentScenario?.default_query || ''}
                  key={selectedScenario}
                />
                {aoiSelection && (
                  <div className="mt-2 flex items-center gap-2 text-xs text-rs-teal bg-teal-50 rounded-lg px-3 py-2 border border-teal-100">
                    <Map size={11} className="flex-shrink-0" />
                    AOI will be appended: <strong className="ml-1">{aoiSelection.name}</strong>
                  </div>
                )}
              </div>
            </div>

            {/* Error */}
            {phase === 'error' && (
              <div className="flex items-start gap-3 p-4 rounded-xl bg-red-50 border border-red-200">
                <AlertCircle size={18} className="text-red-600 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="font-semibold text-red-800 text-sm">Connection Error</p>
                  <p className="text-red-700 text-xs mt-1">{error}</p>
                  <p className="text-red-600 text-xs mt-2 font-mono">
                    python -m uvicorn backend.main:app --reload --port 8000
                  </p>
                </div>
              </div>
            )}

            {/* Visual outputs */}
            {(phase === 'running' || phase === 'done') && (
              <div className="panel">
                <div className="panel-header">
                  <span className="panel-title">Visual Outputs</span>
                  {phase === 'running' && <Loader2 size={13} className="text-rs-text-muted animate-spin" />}
                </div>
                <div className="p-4">
                  {visualOutputs.length > 0 ? (
                    <VisualOutputsGrid outputs={visualOutputs} />
                  ) : (
                    <div className="space-y-2">
                      <div className="shimmer w-full h-28 rounded-xl" />
                      <p className="text-xs text-center text-rs-text-muted">Generating analysis outputs…</p>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Final Answer with Evidence Trail */}
            {phase === 'done' && finalAnswer && (
              <FinalAnswerCard
                query={query}
                answer={finalAnswer}
                confidence={confidence}
                confidenceLevel={confidenceLevel}
                evidenceStatus={evidenceStatus}
                evidencePoints={evidencePoints}
                analysisId={analysisId}
                traceItems={traceItems}
                images={currentScenario?.images ?? []}
                visualOutputs={visualOutputs}
              />
            )}

            {/* Setup placeholder */}
            {phase === 'setup' && (
              <div className="panel p-8 text-center">
                <div className="w-12 h-12 rounded-2xl bg-teal-50 flex items-center justify-center mx-auto mb-4">
                  <Play size={22} className="text-rs-teal" />
                </div>
                <p className="font-semibold text-rs-text-primary mb-2">Ready to Analyze</p>
                <p className="text-sm text-rs-text-secondary">
                  Select a scenario or draw an AOI, then ask your question.
                </p>
                <div className="mt-4 space-y-1.5 text-left max-w-xs mx-auto">
                  {[
                    ['1', 'Scene / Map AOI — choose your region'],
                    ['2', 'Type your question'],
                    ['3', 'Watch the agent trace run live'],
                    ['4', 'Click "WHY THIS ANSWER?" for full evidence'],
                    ['5', 'Export PDF report'],
                  ].map(([n, t]) => (
                    <div key={n} className="flex items-center gap-3 text-xs text-rs-text-secondary">
                      <span className="w-5 h-5 rounded-full bg-navy-100 text-rs-navy font-bold flex items-center justify-center flex-shrink-0 text-[10px]">{n}</span>
                      {t}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* ── RIGHT: Trace + Evidence ── */}
          <div className="xl:col-span-4 space-y-4">

            {/* Agent Trace */}
            <div className="panel">
              <div className="panel-header">
                <div className="flex items-center gap-2">
                  <LayoutPanelLeft size={14} className="text-rs-text-muted" />
                  <span className="panel-title">Agent Execution Trace</span>
                </div>
                {phase === 'running' && (
                  <span className="flex items-center gap-1.5 text-xs text-blue-600 font-medium">
                    <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" /> Live
                  </span>
                )}
                {phase === 'done' && (
                  <span className="text-xs text-green-600 font-medium">Complete</span>
                )}
              </div>
              <div className="p-3 max-h-96 overflow-y-auto">
                <TracePanel
                  items={traceItems}
                  queryUnderstanding={queryUnderstanding ?? undefined}
                  strategyMessage={strategyMessage}
                  planUpdateMessage={planUpdateMessage}
                  lowEvidenceAlert={lowEvidenceAlert}
                />
                <div ref={traceEndRef} />
              </div>
            </div>

            {/* Evidence Panel */}
            {phase === 'done' && (
              <div className="panel animate-fade-in">
                <div className="panel-header">
                  <span className="panel-title">Evidence Check</span>
                </div>
                <div className="p-4">
                  <EvidencePanel
                    evidenceStatus={evidenceStatus}
                    evidencePoints={evidencePoints}
                    confidence={confidence}
                    evidenceBreakdown={evidenceBreakdown}
                    evidenceFormula={evidenceFormula}
                    evidenceInterpretation={evidenceInterpretation}
                    hasRealImages={hasRealImages}
                  />
                </div>
              </div>
            )}

            {/* How-it-works (setup only) */}
            {phase === 'setup' && (
              <div className="panel p-4">
                <p className="section-label mb-3">New Features</p>
                <div className="space-y-2">
                  {[
                    { icon: Map, label: 'Map AOI', desc: 'Draw a region on the satellite map' },
                    { icon: ChevronRight, label: 'Evidence Trail', desc: '"WHY THIS ANSWER?" button on result' },
                    { icon: FileDown, label: 'PDF Export', desc: 'Full analysis report download' },
                    { icon: Clock, label: 'Query History', desc: 'Last 10 analyses with replay' },
                  ].map(({ icon: Icon, label, desc }) => (
                    <div key={label} className="flex items-start gap-2.5 text-xs">
                      <div className="w-6 h-6 rounded-lg bg-navy-50 flex items-center justify-center flex-shrink-0 mt-0.5">
                        <Icon size={12} className="text-rs-navy" />
                      </div>
                      <div>
                        <span className="font-semibold text-rs-text-primary">{label}</span>
                        <span className="text-rs-text-muted ml-1">— {desc}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

        </div>
      </div>
    </div>
  );
}
