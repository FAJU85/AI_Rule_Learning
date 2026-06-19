export interface ScoreHistoryEntry {
  score: number
  date: string
}

export interface Rule {
  rule_id: string
  name: string
  description: string
  keywords: string[]
  pattern?: string
  is_active: boolean
  trust_level: 'high' | 'medium' | 'low'
  effectiveness_score: number
  times_triggered: number
  success_count: number
  score_history: ScoreHistoryEntry[]
  created_at: string
  owner?: string
  category?: string
  tags?: string[]
}

export interface KpiData {
  maturity_level: number
  maturity_name: string
  compliance_health: number
  pending_rules: number
  active_rules: number
  avg_effectiveness: number
}
