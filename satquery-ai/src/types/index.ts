// SatQuery AI — TypeScript Type Definitions

export type TaskType =
  | 'single_image'
  | 'bi_temporal_change'
  | 'sar_optical'
  | 'cloud_analysis'
  | 'object_detection'
  | 'unknown';

export type ToolStatus = 'pending' | 'running' | 'success' | 'warning' | 'error' | 'skipped';
export type EvidenceStatus = 'consistent' | 'conflicting' | 'insufficient' | 'pending';
export type ConfidenceLevel = 'high' | 'medium' | 'low';

export type ExecutionMode =
  | 'LIVE_ALGORITHM'
  | 'LIVE_MODEL'
  | 'REMOTE_MODEL'
  | 'PRECOMPUTED_MODEL_OUTPUT'
  | 'SIMULATED';

export type InputProvenance =
  | 'REAL_SATELLITE_DATA'
  | 'BENCHMARK_DATA'
  | 'SYNTHETIC_DATA'
  | 'DEMO_ASSET'
  | 'USER_UPLOAD'
  | 'UNKNOWN';

export type RegistrationQuality = 'SUCCESS' | 'PARTIAL' | 'FAILED' | 'NOT_ATTEMPTED' | 'NOT_REQUIRED';

// Evidence strength breakdown (from evidence.py)
export interface EvidenceFactor {
  score: number;
  reason: string;
  weight: number;
}

export interface EvidenceBreakdown {
  data_quality?: EvidenceFactor;
  algorithm_confidence?: EvidenceFactor;
  registration_quality?: EvidenceFactor;
  cross_method_agreement?: EvidenceFactor;
}

export interface ImageMetadata {
  image_id: string;
  filename: string;
  sensor: string;
  acquisition_date: string;
  image_type: string;
  resolution_m: number;
  width_px: number;
  height_px: number;
  cloud_coverage_pct: number;
  cloud_status: string;
  processing_status: string;
  coordinates?: string;
  base64_thumbnail?: string;
}

export interface ToolResult {
  tool_name: string;
  status: ToolStatus;
  confidence: number;
  result: Record<string, unknown>;
  visual_output?: string;
  visual_type?: string;
  metadata?: Record<string, unknown>;
  execution_time_ms: number;
  message: string;
  is_demo: boolean;
  // Provenance
  execution_mode?: ExecutionMode;
  input_provenance?: InputProvenance;
  algorithm?: string;
  registration_quality?: RegistrationQuality;
  evidence_excludable?: boolean;
  warnings?: string[];
}

export interface TraceStep {
  step_index: number;
  step_name: string;
  description: string;
  status: ToolStatus;
  tool_name?: string;
  tool_result?: ToolResult;
  timestamp?: string;
  is_auto_inserted?: boolean;
}

export interface VisualOutput {
  type: string;
  label: string;
  b64: string;
}

export interface AnalysisSession {
  analysis_id: string;
  query: string;
  task_type: TaskType;
  intent: string;
  plan: string[];
  trace: TraceStep[];
  tool_results: ToolResult[];
  confidence: number;
  confidence_level: ConfidenceLevel;
  evidence_status: EvidenceStatus;
  reanalysis_count: number;
  final_answer: string;
  evidence_points: string[];
  conflicts: unknown[];
  visual_outputs: VisualOutput[];
  status: string;
  error_message?: string;
  created_at: string;
  completed_at?: string;
  is_demo: boolean;
  // Evidence breakdown
  evidence_breakdown?: EvidenceBreakdown;
  evidence_formula?: string;
  evidence_interpretation?: string;
  low_evidence?: boolean;
  secondary_evidence_status?: string;
  has_real_images?: boolean;
}

export interface DemoScenario {
  scenario_id: string;
  title: string;
  description: string;
  default_query: string;
  task_type: TaskType;
  tags: string[];
  images: ImageMetadata[];
}

// SSE Event types
export interface SSEEvent {
  type: string;
  [key: string]: unknown;
}

export interface SessionCreatedEvent extends SSEEvent {
  type: 'session_created';
  analysis_id: string;
}

export interface StepEvent extends SSEEvent {
  type: 'step';
  step: string;
  status: 'running' | 'done';
  message: string;
  detail?: Record<string, unknown>;
}

export interface ToolStartEvent extends SSEEvent {
  type: 'tool_start';
  step_index: number;
  tool_name: string;
  step_name: string;
  description: string;
  is_auto_inserted: boolean;
}

export interface ToolDoneEvent extends SSEEvent {
  type: 'tool_done';
  step_index: number;
  tool_name: string;
  step_name: string;
  status: ToolStatus;
  confidence: number;
  message: string;
  result: Record<string, unknown>;
  visual_output?: string;
  visual_type?: string;
  metadata?: Record<string, unknown>;
  execution_time_ms: number;
  is_auto_inserted: boolean;
}

export interface PlanUpdatedEvent extends SSEEvent {
  type: 'plan_updated';
  message: string;
  new_plan: string[];
  new_steps: StepDescription[];
  inserted_tool: string;
}

export interface ThumbnailsEvent extends SSEEvent {
  type: 'thumbnails';
  thumbnails: string[];
}

export interface CompletedEvent extends SSEEvent {
  type: 'completed';
  analysis_id: string;
  confidence: number;
  confidence_level: ConfidenceLevel;
  evidence_status: EvidenceStatus;
  final_answer: string;
  evidence_points: string[];
  visual_outputs: VisualOutput[];
  conflicts: unknown[];
  // Evidence breakdown fields
  evidence_breakdown?: EvidenceBreakdown;
  evidence_formula?: string;
  evidence_interpretation?: string;
  low_evidence?: boolean;
  secondary_evidence_status?: string;
  has_real_images?: boolean;
}

// Low evidence SSE event
export interface LowEvidenceEvent extends SSEEvent {
  type: 'low_evidence';
  evidence_strength: number;
  threshold: number;
  message: string;
  secondary_evidence_status: string;
  secondary_evidence_reason: string;
}

export interface StepDescription {
  step_index: number;
  tool_name: string;
  step_name: string;
  description: string;
  is_auto_inserted: boolean;
}

// Internal UI state for live trace
export interface LiveTraceItem {
  step_index: number;
  tool_name: string;
  step_name: string;
  description: string;
  status: ToolStatus;
  confidence?: number;
  message?: string;
  result?: Record<string, unknown>;
  visual_output?: string;
  visual_type?: string;
  metadata?: Record<string, unknown>;
  execution_time_ms?: number;
  is_auto_inserted: boolean;
  // Provenance fields for badge system
  execution_mode?: ExecutionMode;
  input_provenance?: InputProvenance;
  algorithm?: string;
  registration_quality?: RegistrationQuality;
  evidence_excludable?: boolean;
  warnings?: string[];
}
