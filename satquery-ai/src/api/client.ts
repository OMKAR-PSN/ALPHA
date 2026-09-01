// SatQuery AI — API Client
// Handles all communication with the FastAPI backend, including SSE streaming.

import type {
  DemoScenario, SSEEvent, CompletedEvent, LiveTraceItem,
  VisualOutput, ConfidenceLevel, EvidenceStatus,
} from '../types';

const BASE_URL = 'http://localhost:8000';

// ─── Demo Scenarios ───────────────────────────────────────────────────────────

export async function fetchDemoScenarios(): Promise<DemoScenario[]> {
  const res = await fetch(`${BASE_URL}/api/demo/scenarios`);
  if (!res.ok) throw new Error('Failed to fetch demo scenarios');
  const data = await res.json();
  return data.scenarios;
}

// ─── Analysis result state ─────────────────────────────────────────────────

export interface AnalysisResult {
  analysisId: string;
  confidence: number;
  confidenceLevel: ConfidenceLevel;
  evidenceStatus: EvidenceStatus;
  finalAnswer: string;
  evidencePoints: string[];
  visualOutputs: VisualOutput[];
  conflicts: unknown[];
  // Evidence breakdown from evidence.py
  evidenceBreakdown?: Record<string, unknown>;
  evidenceFormula?: string;
  evidenceInterpretation?: string;
  lowEvidence?: boolean;
  secondaryEvidenceStatus?: string;
  hasRealImages?: boolean;
}

// ─── SSE Streaming Analysis ────────────────────────────────────────────────

export interface AnalysisCallbacks {
  onSessionCreated?: (id: string) => void;
  onQueryUnderstood?: (detail: Record<string, unknown>, message: string) => void;
  onStrategySelected?: (detail: Record<string, unknown>, message: string) => void;
  onToolStart?: (item: Omit<LiveTraceItem, 'status'>) => void;
  onToolDone?: (item: LiveTraceItem) => void;
  onPlanUpdated?: (message: string, newPlan: string[]) => void;
  onThumbnails?: (thumbnails: string[]) => void;
  onLowEvidence?: (evidenceStrength: number, message: string, secondaryStatus: string, secondaryReason: string) => void;
  onCompleted?: (result: AnalysisResult) => void;
  onError?: (error: string) => void;
}

export async function runAnalysis(
  query: string,
  demoScenario: string | null,
  callbacks: AnalysisCallbacks,
): Promise<void> {
  const payload = {
    query,
    demo_scenario: demoScenario,
    image_ids: [],
  };

  let response: Response;
  try {
    response = await fetch(`${BASE_URL}/api/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  } catch (e) {
    callbacks.onError?.('Cannot connect to backend. Make sure the FastAPI server is running on port 8000.');
    return;
  }

  if (!response.ok || !response.body) {
    callbacks.onError?.(`Server error: ${response.status}`);
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() ?? '';

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue;
      const jsonStr = line.slice(6).trim();
      if (!jsonStr) continue;

      let event: SSEEvent;
      try {
        event = JSON.parse(jsonStr);
      } catch {
        continue;
      }

      handleEvent(event, callbacks);
    }
  }
}

function handleEvent(event: SSEEvent, callbacks: AnalysisCallbacks) {
  switch (event.type) {
    case 'session_created':
      callbacks.onSessionCreated?.(event.analysis_id as string);
      break;

    case 'step': {
      const step = event.step as string;
      const status = event.status as string;
      const message = event.message as string;
      const detail = event.detail as Record<string, unknown> | undefined;
      if (step === 'query_understanding' && status === 'done') {
        callbacks.onQueryUnderstood?.(detail ?? {}, message);
      } else if (step === 'strategy_selection' && status === 'done') {
        callbacks.onStrategySelected?.(detail ?? {}, message);
      }
      break;
    }

    case 'tool_start': {
      callbacks.onToolStart?.({
        step_index: event.step_index as number,
        tool_name: event.tool_name as string,
        step_name: event.step_name as string,
        description: event.description as string,
        is_auto_inserted: event.is_auto_inserted as boolean,
      });
      break;
    }

    case 'tool_done': {
      callbacks.onToolDone?.({
        step_index: event.step_index as number,
        tool_name: event.tool_name as string,
        step_name: event.step_name as string,
        description: event.description as string,
        status: event.status as LiveTraceItem['status'],
        confidence: event.confidence as number,
        message: event.message as string,
        result: event.result as Record<string, unknown>,
        visual_output: event.visual_output as string | undefined,
        visual_type: event.visual_type as string | undefined,
        metadata: event.metadata as Record<string, unknown> | undefined,
        execution_time_ms: event.execution_time_ms as number,
        is_auto_inserted: event.is_auto_inserted as boolean,
        // Provenance fields
        execution_mode: event.execution_mode as LiveTraceItem['execution_mode'],
        input_provenance: event.input_provenance as LiveTraceItem['input_provenance'],
        algorithm: event.algorithm as string | undefined,
        registration_quality: event.registration_quality as LiveTraceItem['registration_quality'],
        evidence_excludable: event.evidence_excludable as boolean | undefined,
        warnings: event.warnings as string[] | undefined,
      });
      break;
    }

    case 'plan_updated':
      callbacks.onPlanUpdated?.(
        event.message as string,
        event.new_plan as string[],
      );
      break;

    case 'thumbnails':
      callbacks.onThumbnails?.(event.thumbnails as string[]);
      break;

    case 'low_evidence':
      callbacks.onLowEvidence?.(
        event.evidence_strength as number,
        event.message as string,
        event.secondary_evidence_status as string,
        event.secondary_evidence_reason as string,
      );
      break;

    case 'completed': {
      const c = event as unknown as CompletedEvent;
      callbacks.onCompleted?.({
        analysisId: c.analysis_id,
        confidence: c.confidence,
        confidenceLevel: c.confidence_level,
        evidenceStatus: c.evidence_status,
        finalAnswer: c.final_answer,
        evidencePoints: c.evidence_points,
        visualOutputs: c.visual_outputs,
        conflicts: c.conflicts,
        evidenceBreakdown: c.evidence_breakdown as Record<string, unknown> | undefined,
        evidenceFormula: c.evidence_formula,
        evidenceInterpretation: c.evidence_interpretation,
        lowEvidence: c.low_evidence,
        secondaryEvidenceStatus: c.secondary_evidence_status,
        hasRealImages: c.has_real_images,
      });
      break;
    }
  }
}

export async function runDemoScenario(
  scenarioId: string,
  query: string | null,
  callbacks: AnalysisCallbacks,
): Promise<void> {
  const payload = { scenario_id: scenarioId, query };

  let response: Response;
  try {
    response = await fetch(`${BASE_URL}/api/demo/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  } catch {
    callbacks.onError?.('Cannot connect to backend. Make sure the FastAPI server is running on port 8000.');
    return;
  }

  if (!response.ok || !response.body) {
    callbacks.onError?.(`Server error: ${response.status}`);
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() ?? '';
    for (const line of lines) {
      if (!line.startsWith('data: ')) continue;
      const jsonStr = line.slice(6).trim();
      if (!jsonStr) continue;
      try { handleEvent(JSON.parse(jsonStr), callbacks); } catch { /* skip */ }
    }
  }
}
