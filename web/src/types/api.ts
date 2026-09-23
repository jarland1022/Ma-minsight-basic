/** Shared API response shapes for the console. */

export type ConfigRow = {
  key: string;
  value: unknown;
  description?: string | null;
};

export type EventRow = {
  id: string;
  title?: string | null;
  status: string;
  risk_score: number;
  queue_priority: number;
  alert_count: number;
  last_alert_at?: string | null;
  concluded_at?: string | null;
  investigation_finished_at?: string | null;
  human_review_sent_at?: string | null;
  human_review_question?: string | null;
  human_review_dispatched?: boolean;
  human_review_is_system_error?: boolean;
  aggregate_host_name?: string | null;
  aggregate_user_name?: string | null;
};

export type AlertDetailRow = {
  alert_id: string;
  rule_name?: string | null;
  triage_route?: string | null;
  triage_score?: number | null;
  severity?: number | null;
  occurred_at?: string | null;
  src_ip?: string | null;
  src_geo?: string | null;
  user_name?: string | null;
  host_name?: string | null;
  request_url?: string | null;
};

export type DispositionRow = {
  id: string;
  investigation_id?: string | null;
  suggested_action?: string | null;
  status: string;
  confirmed_action?: string | null;
};

export type HumanReviewRow = {
  id: string;
  status: string;
  question?: string | null;
};

export type InvestigationRow = {
  id: string;
  status: string;
  started_at?: string | null;
  finished_at?: string | null;
  closure_retry_count?: number | null;
  hypothesis_template?: HypothesisTemplate | null;
  conclusion?: {
    verdict: string;
    confidence: number;
    reasoning?: string | null;
    human_query?: string | null;
    recommended_action?: string | null;
    evidence_closure_score?: number | null;
    refutation_coverage?: number | null;
    closure_passed?: boolean | null;
    closure_checks?: Record<string, unknown> | null;
    hypotheses_evaluated?: unknown[] | null;
    refutation_summary?: string | null;
  } | null;
  supervisor_audits?: SupervisorAuditRow[];
  disposition_simulations?: DispositionSimulationRow[];
};

export type SupervisorAuditRow = {
  id: string;
  audit_type: string;
  passed: boolean;
  findings?: Record<string, unknown> | null;
  supervisor_model?: string | null;
  created_at?: string | null;
};

export type HypothesisHint = {
  id?: string;
  description?: string;
  skill?: string;
  weight?: number;
};

export type HypothesisTemplate = {
  investigation_intent?: string;
  default_hypotheses?: { id?: string; label?: string; priority?: number }[];
  supporting_hints?: HypothesisHint[];
  refuting_hints?: HypothesisHint[];
};

export type EntityGraphNode = {
  entity_type: string;
  entity_key: string;
  display_name?: string | null;
  owner_team?: string | null;
};

export type EntityGraphEdge = {
  from_type: string;
  from_key: string;
  to_type: string;
  to_key: string;
  relation_type: string;
  confidence?: number | null;
};

export type EntityContextSnapshot = {
  seed_entity_type?: string | null;
  seed_entity_key?: string | null;
  summary?: string | null;
  node_count?: number | null;
  edge_count?: number | null;
  nodes?: EntityGraphNode[];
  edges?: EntityGraphEdge[];
};

export type MatchedPlaybook = {
  id: string;
  name: string;
  domain?: string | null;
  summary?: string | null;
  mitre_attack?: string[];
  investigation_steps?: string[];
  runtime_skills?: string[];
  human_questions?: string[];
};

export type EventDetail = {
  id: string;
  title?: string | null;
  status: string;
  risk_score: number;
  aggregate_host_name?: string | null;
  aggregate_user_name?: string | null;
  primary_category?: string | null;
  aggregate_category?: string | null;
  alert_details?: AlertDetailRow[];
  dispositions?: DispositionRow[];
  human_reviews?: HumanReviewRow[];
  investigations?: InvestigationRow[];
  entity_context_snapshot?: EntityContextSnapshot | null;
  matched_playbooks?: MatchedPlaybook[];
};

export type PendingDispositionRow = {
  id: string;
  suggested_action?: string | null;
  investigation_id?: string | null;
  event_id?: string | null;
  event_title?: string | null;
  event_status?: string | null;
  aggregate_host_name?: string | null;
  aggregate_user_name?: string | null;
  primary_category?: string | null;
  risk_score?: number | null;
  verdict?: string | null;
  created_at?: string | null;
};

export type PendingSimulationRow = {
  id: string;
  investigation_id?: string | null;
  action_type: string;
  action_params?: Record<string, unknown> | null;
  simulated_impact?: Record<string, unknown> | null;
  approval_status: string;
  event_id?: string | null;
  event_title?: string | null;
  aggregate_host_name?: string | null;
  aggregate_user_name?: string | null;
  affected_host_count?: number | null;
  estimated_downtime_minutes?: number | null;
  business_systems?: string[] | null;
  created_at?: string | null;
};

export type DispositionSimulationRow = {
  id: string;
  action_type: string;
  action_params?: Record<string, unknown> | null;
  approval_status: string;
  affected_host_count?: number | null;
  estimated_downtime_minutes?: number | null;
  summary?: string | null;
  created_at?: string | null;
};

export type RegressionRunRow = {
  id: string;
  run_at: string;
  passed: number;
  failed: number;
  total: number;
  model_name?: string | null;
};

export type HealthCheckRunRow = {
  id: string;
  scenario_id: string;
  run_at: string;
  passed: boolean;
};

export type Paginated<T> = {
  items: T[];
  total: number;
  page: number;
  page_size: number;
};

export type RegressionCaseRow = {
  id: string;
  name: string;
  expected_verdict: string;
  expected_skills: string[];
  tags?: string[];
  is_active: boolean;
};

export type HealthScenarioRow = {
  id: string;
  name: string;
  expected_stage: string;
  description?: string | null;
};

export type ListResponse<T> = {
  items: T[];
};

export type DiagnosticCheck = {
  id: string;
  label: string;
  status: "ok" | "warn" | "error" | "info" | "skip";
  message: string;
  detail?: string | null;
  suggestion?: string | null;
};

export type DataSourceStats = {
  alerts_in_db: number;
  cursor_last_occurred_at?: string | null;
  cursor_total_ingested: number;
  last_successful_run_at?: string | null;
  initial_lookback_hours?: number | null;
  indexer_url?: string | null;
  indexer_latest_at?: string | null;
  indexer_total_alerts?: number | null;
  window_start?: string | null;
  window_match_count?: number | null;
};

export type DataSourceDiagnostics = {
  data_source_id: string;
  name: string;
  adapter_type: string;
  is_active: boolean;
  overall_status: "ok" | "warn" | "error";
  checks: DiagnosticCheck[];
  stats: DataSourceStats;
  actions_available: string[];
};

export type IngestionDiagnosticsReport = {
  generated_at: string;
  overall_status: "ok" | "warn" | "error";
  sources: DataSourceDiagnostics[];
  summary: string;
  geolite2_ready?: boolean;
  geolite2_path?: string | null;
};

export type NoisyRuleRow = {
  rule_id?: string | null;
  rule_name?: string | null;
  alert_count: number;
  event_count: number;
  human_confirmed_fp: number;
  human_confirmed_attack: number;
  fp_ratio: number;
  suggestion?: string | null;
};

export type NoisyRulesResponse = {
  days: number;
  items: NoisyRuleRow[];
  note?: string;
};
