import { z } from 'zod'
import { readJsonl } from '../storage/index.js'
import type { Rule } from './listRules.js'

export const applyRulesInputSchema = z.object({
  text: z.string().min(1).describe('The text to check against active rules'),
})

export type ApplyRulesInput = z.infer<typeof applyRulesInputSchema>

export interface TriggeredRule {
  rule_id: string
  name: string
  description: string
}

function ruleMatchesText(rule: Rule, text: string): boolean {
  const lowerText = text.toLowerCase()

  // Check keyword matches
  if (rule.keywords && rule.keywords.length > 0) {
    for (const keyword of rule.keywords) {
      if (lowerText.includes(keyword.toLowerCase())) {
        return true
      }
    }
  }

  // Check pattern match
  if (rule.pattern) {
    try {
      const regex = new RegExp(rule.pattern, 'i')
      if (regex.test(text)) {
        return true
      }
    } catch {
      // Invalid regex — skip pattern matching for this rule
    }
  }

  return false
}

export async function applyRules(input: ApplyRulesInput): Promise<object> {
  const { text } = applyRulesInputSchema.parse(input)
  const rules = await readJsonl<Rule>('rules.jsonl')

  const activeRules = rules.filter((r) => r.is_active !== false)
  const triggered: TriggeredRule[] = []

  for (const rule of activeRules) {
    if (ruleMatchesText(rule, text)) {
      triggered.push({
        rule_id: rule.rule_id,
        name: rule.name,
        description: rule.description,
      })
    }
  }

  return {
    triggered_rules: triggered,
    total_triggered: triggered.length,
    total_active_rules: activeRules.length,
  }
}
