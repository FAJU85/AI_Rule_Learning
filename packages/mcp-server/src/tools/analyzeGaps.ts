import { z } from 'zod'
import { readJsonl } from '../storage/index.js'
import type { Rule } from './listRules.js'
import type { SessionRecord } from './recordSession.js'

export const analyzeGapsInputSchema = z.object({
  top_n: z
    .number()
    .int()
    .min(1)
    .max(20)
    .optional()
    .default(5)
    .describe('Number of top gap suggestions to return'),
})

export type AnalyzeGapsInput = z.infer<typeof analyzeGapsInputSchema>

function extractContextWords(text: string): string[] {
  // Tokenize text into significant words (ignore stop words and short words)
  const stopWords = new Set([
    'the', 'a', 'an', 'is', 'it', 'in', 'on', 'at', 'to', 'for', 'of', 'and',
    'or', 'but', 'not', 'with', 'this', 'that', 'i', 'you', 'we', 'they',
    'he', 'she', 'be', 'do', 'have', 'will', 'can', 'would', 'could', 'should',
    'my', 'your', 'our', 'their', 'its', 'are', 'was', 'were', 'been', 'has',
    'had', 'did', 'does', 'am', 'by', 'from', 'as', 'if', 'then', 'so',
  ])

  return text
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, ' ')
    .split(/\s+/)
    .filter((w) => w.length > 3 && !stopWords.has(w))
}

function messageMatchesAnyRule(content: string, rules: Rule[]): boolean {
  const lower = content.toLowerCase()
  for (const rule of rules) {
    if (rule.is_active === false) continue
    for (const kw of rule.keywords ?? []) {
      if (lower.includes(kw.toLowerCase())) return true
    }
    if (rule.pattern) {
      try {
        if (new RegExp(rule.pattern, 'i').test(content)) return true
      } catch {
        // skip invalid patterns
      }
    }
  }
  return false
}

export async function analyzeGaps(input: AnalyzeGapsInput): Promise<object> {
  const { top_n } = analyzeGapsInputSchema.parse(input)

  const [sessions, rules] = await Promise.all([
    readJsonl<SessionRecord>('sessions.jsonl'),
    readJsonl<Rule>('rules.jsonl'),
  ])

  if (sessions.length === 0) {
    return {
      suggestions: [],
      message: 'No sessions recorded yet. Use record_session to capture conversations.',
      sessions_analyzed: 0,
      untriggered_turns: 0,
    }
  }

  // Collect all user turns that triggered no rule
  const wordFrequency: Map<string, number> = new Map()
  let untriggeredCount = 0
  let totalUserTurns = 0

  for (const session of sessions) {
    for (const message of session.messages) {
      if (message.role !== 'user') continue
      totalUserTurns++

      if (!messageMatchesAnyRule(message.content, rules)) {
        untriggeredCount++
        const words = extractContextWords(message.content)
        for (const word of words) {
          wordFrequency.set(word, (wordFrequency.get(word) ?? 0) + 1)
        }
      }
    }
  }

  // Sort by frequency and take top N
  const sorted = [...wordFrequency.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, top_n)

  const suggestions = sorted.map(([word, count]) => ({
    keyword: word,
    frequency: count,
    suggestion: `Consider adding a rule with keyword "${word}" (appeared ${count} time${count !== 1 ? 's' : ''} in untriggered turns)`,
  }))

  return {
    suggestions,
    sessions_analyzed: sessions.length,
    total_user_turns: totalUserTurns,
    untriggered_turns: untriggeredCount,
    coverage_rate:
      totalUserTurns > 0
        ? `${(((totalUserTurns - untriggeredCount) / totalUserTurns) * 100).toFixed(1)}%`
        : 'N/A',
  }
}
