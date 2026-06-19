import { z } from 'zod'
import { readJsonl } from '../storage/index.js'

export const listRulesInputSchema = z.object({
  include_inactive: z.boolean().optional().default(false).describe('Include inactive rules in the response'),
})

export type ListRulesInput = z.infer<typeof listRulesInputSchema>

export interface Rule {
  rule_id: string
  name: string
  description: string
  keywords: string[]
  pattern?: string
  is_active: boolean
  effectiveness_score: number
  created_at: string
}

export async function listRules(input: ListRulesInput): Promise<object> {
  const { include_inactive } = listRulesInputSchema.parse(input)
  const rules = await readJsonl<Rule>('rules.jsonl')

  const filtered = include_inactive ? rules : rules.filter((r) => r.is_active !== false)

  const result = filtered.map((r) => ({
    rule_id: r.rule_id,
    name: r.name,
    description: r.description,
    is_active: r.is_active ?? true,
    effectiveness_score: r.effectiveness_score ?? 0,
  }))

  return {
    rules: result,
    total: result.length,
  }
}
