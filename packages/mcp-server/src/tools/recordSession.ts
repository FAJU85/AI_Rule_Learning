import { z } from 'zod'
import { appendJsonl } from '../storage/index.js'

const messageSchema = z.object({
  role: z.string().describe('The role of the message sender (e.g. user, assistant)'),
  content: z.string().describe('The content of the message'),
})

export const recordSessionInputSchema = z.object({
  session_id: z.string().min(1).describe('Unique identifier for this session'),
  messages: z.array(messageSchema).min(1).describe('Array of messages in the session'),
})

export type RecordSessionInput = z.infer<typeof recordSessionInputSchema>

export interface SessionRecord {
  session_id: string
  messages: Array<{ role: string; content: string }>
  recorded_at: string
  message_count: number
}

export async function recordSession(input: RecordSessionInput): Promise<object> {
  const { session_id, messages } = recordSessionInputSchema.parse(input)

  const record: SessionRecord = {
    session_id,
    messages,
    recorded_at: new Date().toISOString(),
    message_count: messages.length,
  }

  await appendJsonl('sessions.jsonl', record)

  return {
    session_id,
    recorded: true,
    message_count: messages.length,
    message: `Session "${session_id}" recorded successfully with ${messages.length} messages`,
  }
}
