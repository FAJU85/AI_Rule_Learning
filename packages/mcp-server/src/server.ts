import { Server } from '@modelcontextprotocol/sdk/server/index.js'
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js'
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  McpError,
  ErrorCode,
} from '@modelcontextprotocol/sdk/types.js'
import { z } from 'zod'
import {
  listRules,
  listRulesInputSchema,
  applyRules,
  applyRulesInputSchema,
  addRule,
  addRuleInputSchema,
  recordSession,
  recordSessionInputSchema,
  analyzeGaps,
  analyzeGapsInputSchema,
} from './tools/index.js'

function zodToJsonSchema(schema: z.ZodTypeAny): object {
  // Simple Zod-to-JSON-Schema converter for the tool definitions
  if (schema instanceof z.ZodObject) {
    const shape = schema.shape as Record<string, z.ZodTypeAny>
    const properties: Record<string, object> = {}
    const required: string[] = []

    for (const [key, value] of Object.entries(shape)) {
      properties[key] = zodToJsonSchema(value)
      if (!(value instanceof z.ZodOptional) && !(value instanceof z.ZodDefault)) {
        required.push(key)
      }
    }

    return { type: 'object', properties, required }
  }

  if (schema instanceof z.ZodDefault) {
    return zodToJsonSchema(schema._def.innerType as z.ZodTypeAny)
  }

  if (schema instanceof z.ZodOptional) {
    return zodToJsonSchema(schema.unwrap())
  }

  if (schema instanceof z.ZodString) {
    const desc = schema.description
    return desc ? { type: 'string', description: desc } : { type: 'string' }
  }

  if (schema instanceof z.ZodNumber) {
    const desc = schema.description
    return desc ? { type: 'number', description: desc } : { type: 'number' }
  }

  if (schema instanceof z.ZodBoolean) {
    const desc = schema.description
    return desc ? { type: 'boolean', description: desc } : { type: 'boolean' }
  }

  if (schema instanceof z.ZodArray) {
    const desc = schema.description
    const base = { type: 'array', items: zodToJsonSchema(schema.element) }
    return desc ? { ...base, description: desc } : base
  }

  return {}
}

export function startServer(): void {
  const server = new Server(
    {
      name: 'ai-rule-learning-mcp',
      version: '0.1.0',
    },
    {
      capabilities: {
        tools: {},
      },
    }
  )

  server.setRequestHandler(ListToolsRequestSchema, async () => {
    return {
      tools: [
        {
          name: 'list_rules',
          description:
            'List all personalisation rules stored in the AI Rule Learning system. Returns rule IDs, names, descriptions, active status, and effectiveness scores.',
          inputSchema: zodToJsonSchema(listRulesInputSchema),
        },
        {
          name: 'apply_rules',
          description:
            'Check which active rules are triggered by a piece of text. Returns the list of triggered rules with their names and descriptions so you can follow them in your response.',
          inputSchema: zodToJsonSchema(applyRulesInputSchema),
        },
        {
          name: 'add_rule',
          description:
            'Add a new personalisation rule to the system. Provide a name, description of the instruction, and keywords that should trigger the rule.',
          inputSchema: zodToJsonSchema(addRuleInputSchema),
        },
        {
          name: 'record_session',
          description:
            'Record a conversation session to help the system learn patterns and improve rule coverage over time.',
          inputSchema: zodToJsonSchema(recordSessionInputSchema),
        },
        {
          name: 'analyze_gaps',
          description:
            'Analyse recorded sessions to find conversation patterns that are not covered by any existing rule. Returns suggestions for new rules based on untriggered turns.',
          inputSchema: zodToJsonSchema(analyzeGapsInputSchema),
        },
      ],
    }
  })

  server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const { name, arguments: args } = request.params

    try {
      let result: object

      switch (name) {
        case 'list_rules':
          result = await listRules(args as Parameters<typeof listRules>[0])
          break
        case 'apply_rules':
          result = await applyRules(args as Parameters<typeof applyRules>[0])
          break
        case 'add_rule':
          result = await addRule(args as Parameters<typeof addRule>[0])
          break
        case 'record_session':
          result = await recordSession(args as Parameters<typeof recordSession>[0])
          break
        case 'analyze_gaps':
          result = await analyzeGaps(args as Parameters<typeof analyzeGaps>[0])
          break
        default:
          throw new McpError(ErrorCode.MethodNotFound, `Unknown tool: ${name}`)
      }

      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify(result, null, 2),
          },
        ],
      }
    } catch (err: unknown) {
      if (err instanceof McpError) throw err

      if (err instanceof z.ZodError) {
        throw new McpError(
          ErrorCode.InvalidParams,
          `Invalid parameters: ${err.errors.map((e) => `${e.path.join('.')}: ${e.message}`).join(', ')}`
        )
      }

      const message = err instanceof Error ? err.message : String(err)
      throw new McpError(ErrorCode.InternalError, `Tool execution failed: ${message}`)
    }
  })

  const transport = new StdioServerTransport()
  server.connect(transport).catch((err: unknown) => {
    const message = err instanceof Error ? err.message : String(err)
    console.error(`Failed to connect MCP server: ${message}`)
    process.exit(1)
  })
}
