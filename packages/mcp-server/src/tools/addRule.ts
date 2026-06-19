import { z } from 'zod'
import { appendJsonl } from '../storage/index.js'
import type { Rule } from './listRules.js'

export const addRuleInputSchema = z.object({
  name: z.string().min(1).describe('Short name for the rule'),
  description: z.string().min(1).describe('Full description of what the rule instructs'),
  keywords: z
    .array(z.string().min(1))
    .min(1)
    .describe('List of keywords that trigger this rule when found in text'),
  pattern: z.string().optional().describe('Optional regex pattern to match against text'),
})

export type AddRuleInput = z.infer<typeof addRuleInputSchema>

function generateUUID(): string {
  // Use crypto.randomUUID if available (Node 14.17+), otherwise fallback
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID()
  }
  // Fallback UUID v4 implementation
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0
    const v = c === 'x' ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })
}

export async function addRule(input: AddRuleInput): Promise<object> {
  const { name, description, keywords, pattern } = addRuleInputSchema.parse(input)

  const rule: Rule = {
    rule_id: generateUUID(),
    name,
    description,
    keywords,
    ...(pattern !== undefined ? { pattern } : {}),
    is_active: true,
    effectiveness_score: 0,
    created_at: new Date().toISOString(),
  }

  await appendJsonl('rules.jsonl', rule)

  return {
    rule_id: rule.rule_id,
    name: rule.name,
    message: `Rule "${name}" created successfully`,
  }
}
