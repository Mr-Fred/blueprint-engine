export interface PillarScores {
  performance: number;
  scalability: number;
  security: number;
  reliability: number;
  maintainability: number;
  cost_efficiency: number;
}

export interface DebateRound {
  round_number: number;
  proposal_draft: string;
  critique: string;
  scores: PillarScores;
  judge_directive: string | null;
}

export interface RequirementsSchema {
  preferred_tech_stack?: string[];
  cloud_provider?: string | null;
  architectural_pattern?: string | null;
  target_rps?: number | null;
  budget_tier?: string | null;
  compliance_frameworks?: string[];
  core_use_cases?: string[];
}

export interface DebateState {
  project_id: string;
  concept: string;
  current_round: number;
  rounds_history: DebateRound[];
  grill_history?: {role: string, content: string}[];
  grill_completed?: boolean;
  requirements?: RequirementsSchema | null;
  intermission_paused?: boolean;
  intermission_action?: string | null;
  consensus_achieved: boolean;
  final_prd: string | null;
  final_architecture: string | null;
  final_topology?: string | null;
  final_risk_matrix?: string | null;
  final_artifacts?: Record<string, string>;
  caveman_mode?: boolean;
  epistemic_scratchpad?: {
    project_id: string;
    verified_facts?: { fact_id: string; statement: string; verifier: string }[];
  } | null;
  journey_trace?: {
    span_id: string;
    project_id: string;
    timestamp: string;
    span_name: string;
    agent_role: string;
    round_number?: number;
    duration_ms?: number;
    metadata?: Record<string, any>;
  }[];
}

export interface ProjectInfo {
  project_id: string;
  concept: string;
  status: string;
  consensus_achieved?: boolean;
  final_prd?: string | null;
  final_architecture?: string | null;
  final_topology?: string | null;
  final_risk_matrix?: string | null;
  final_artifacts?: Record<string, string>;
}

export interface LiveStreamChunk {
  agent: string | null;
  text: string;
}

export interface PendingInput {
  name: string;
  description: string;
}
