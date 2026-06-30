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

export interface DebateState {
  project_id: string;
  concept: string;
  current_round: number;
  rounds_history: DebateRound[];
  grill_history?: {role: string, content: string}[];
  consensus_achieved: boolean;
  final_prd: string | null;
  final_architecture: string | null;
}

export interface ProjectInfo {
  project_id: string;
  concept: string;
  status: string;
}

export interface LiveStreamChunk {
  agent: string | null;
  text: string;
}

export interface PendingInput {
  name: string;
  description: string;
}
