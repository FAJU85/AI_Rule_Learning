/**
 * Cloudflare Worker — Community Telemetry Relay (TypeScript + Hono + Zod)
 *
 * Implements specifications from ARL-REM-2026-007 / ARL-SPRINT-001:
 * - Framework: Hono + Zod + @hono/zod-validator
 * - Endpoints: GET /health, POST /contribute, POST /admin/approve, POST /admin/reject
 * - Rate limiting: KV sliding-window per-IP limiter
 * - Security: Strict 64 KB ceiling, PII rejection, prompt injection rejection
 * - Provenance: Strict Zod validation of all mandatory fields
 * - Storage: Private staging R2 bucket (arl-learning-raw / arl-contributions)
 */

import { Hono } from 'hono';
import {
  MAX_PAYLOAD_BYTES,
  RATE_LIMIT_WINDOW_SEC,
  RATE_LIMIT_MAX_REQ,
  RETENTION_TTL_SECONDS,
  ContributionPayloadSchema,
  ContributionPayload,
  CanonicalRuleTelemetry,
} from '../schemas/index';

export interface Env {
  CONTRIBUTIONS_KV: KVNamespace;
  RATE_LIMIT_KV: KVNamespace;
  RAW_CONTRIBUTIONS_BUCKET: R2Bucket;
  PUBLIC_TEMPLATES_BUCKET: R2Bucket;
  ADMIN_KEY?: string;
  RETENTION_TTL_SECONDS?: string;
  DATA_RESIDENCY?: string;
}

const PII_PATTERNS = [
  { regex: /[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+/g, replacement: '[EMAIL_REDACTED]', label: 'Email address' },
  { regex: /\b(?:\d{1,3}\.){3}\d{1,3}\b/g, replacement: '[IP_REDACTED]', label: 'IPv4 address' },
  { regex: /\b(?:[0-9a-fA-F]{1,4}:){2,7}[0-9a-fA-F]{1,4}\b/g, replacement: '[IP_REDACTED]', label: 'IPv6 address' },
  {
    regex: /\b(?:sk-[a-zA-Z0-9_-]{12,}|hf_[a-zA-Z0-9]{12,}|gh[pousr]_[a-zA-Z0-9]{12,}|AKIA[0-9A-Z]{16})\b/g,
    replacement: '[TOKEN_REDACTED]',
    label: 'API/Bearer token',
  },
  { regex: /Bearer\s+[A-Za-z0-9\-._~+/]+=*/gi, replacement: 'Bearer [TOKEN_REDACTED]', label: 'Authorization header' },
  { regex: /\b\d{3}-\d{2}-\d{4}\b/g, replacement: '[SSN_REDACTED]', label: 'SSN' },
  { regex: /(?:\/Users\/|\/home\/|[A-Za-z]:\\Users\\)[^\s,"']+/g, replacement: '[PATH_REDACTED]', label: 'Local filesystem path' },
];

const INJECTION_PATTERNS = [
  /ignore\s+(all\s+)?(the\s+)?(previous|prior|above)\s+instructions/i,
  /disregard\s+(all\s+)?(the\s+)?(previous|prior|above)\s+(instructions|prompts)/i,
  /you\s+are\s+now\s+(in\s+)?(dan|jailbreak|developer|god)\s+mode/i,
  /bypass\s+(all\s+)?(safety|guardrails|filters|restrictions)/i,
  /reveal\s+(your\s+)?(system\s+prompt|initial\s+instructions)/i,
  /exfiltrate|send\s+all\s+user\s+data\s+to/i,
  /sudo\s+mode|disable\s+all\s+rules/i,
];

export function scrubPiiText(text: string): string {
  if (typeof text !== 'string') return '';
  let out = text;
  for (const { regex, replacement } of PII_PATTERNS) {
    out = out.replace(regex, replacement);
  }
  return out;
}

export function scrubPiiDeep(val: unknown): unknown {
  if (typeof val === 'string') return scrubPiiText(val);
  if (Array.isArray(val)) return val.map(scrubPiiDeep);
  if (val && typeof val === 'object') {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(val as Record<string, unknown>)) {
      out[scrubPiiText(k)] = scrubPiiDeep(v);
    }
    return out;
  }
  return val;
}

export function detectPromptInjection(text: string): boolean {
  if (!text || typeof text !== 'string') return false;
  for (const pat of INJECTION_PATTERNS) {
    if (pat.test(text)) return true;
  }
  return false;
}

const app = new Hono<{ Bindings: Env }>();

// 1. Health check
app.get('/health', (c) => {
  return c.json({
    status: 'healthy',
    service: 'ai-rule-learning-relay',
    version: '0.3.0',
    storage: 'Cloudflare R2 (arl-contributions / arl-learning-raw)',
    residency: c.env.DATA_RESIDENCY || 'EU/US Cloudflare Edge (GDPR Art. 44-49 SCCs)',
    timestamp: new Date().toISOString(),
  }, 200);
});

app.get('/api/health', (c) => {
  return c.json({
    status: 'healthy',
    service: 'ai-rule-learning-relay',
    version: '0.3.0',
    timestamp: new Date().toISOString(),
  }, 200);
});

app.options('/contribute', (c) => c.text('', 204, { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'GET, POST, OPTIONS', 'Access-Control-Allow-Headers': 'Content-Type, Authorization' }));
app.options('/api/contribute', (c) => c.text('', 204, { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'GET, POST, OPTIONS', 'Access-Control-Allow-Headers': 'Content-Type, Authorization' }));

const handleContribute = async (c: any) => {
  const req = c.req.raw;
  const contentLength = parseInt(req.headers.get('content-length') || '0', 10);
  if (contentLength > MAX_PAYLOAD_BYTES) {
    return c.json({ error: 'Payload Too Large', max_bytes: MAX_PAYLOAD_BYTES }, 413);
  }

  // Rate Limiting
  const clientIp = req.headers.get('cf-connecting-ip') || '127.0.0.1';
  if (c.env.RATE_LIMIT_KV) {
    const rateKey = `rl:${clientIp}`;
    const currentCount = parseInt((await c.env.RATE_LIMIT_KV.get(rateKey)) || '0', 10);
    if (currentCount >= RATE_LIMIT_MAX_REQ) {
      return c.json({ error: 'Rate limit exceeded. Try again in 60s.' }, 429);
    }
    await c.env.RATE_LIMIT_KV.put(rateKey, String(currentCount + 1), {
      expirationTtl: RATE_LIMIT_WINDOW_SEC,
    });
  }

  let rawText: string;
  try {
    rawText = await req.text();
  } catch {
    return c.json({ error: 'Failed to read request body' }, 400);
  }

  if (rawText.length > MAX_PAYLOAD_BYTES) {
    return c.json({ error: 'Payload Too Large', max_bytes: MAX_PAYLOAD_BYTES }, 413);
  }

  // Check for un-scrubbed PII presence
  for (const { regex, label } of PII_PATTERNS) {
    if (regex.test(rawText)) {
      return c.json({
        error: 'Rejected: Un-scrubbed PII detected in contribution payload',
        reason: `Payload contains un-scrubbed personal information: ${label}`,
      }, 400);
    }
  }

  // Check for prompt injection
  if (detectPromptInjection(rawText)) {
    return c.json({ error: 'Rejected: Prompt injection / safety override detected' }, 400);
  }

  let parsedJson: unknown;
  try {
    parsedJson = JSON.parse(rawText);
  } catch {
    return c.json({ error: 'Invalid JSON format' }, 400);
  }

  // Zod validation for mandatory provenance and contribution structure
  const validationResult = ContributionPayloadSchema.safeParse(parsedJson);
  if (!validationResult.success) {
    const issues = validationResult.error.issues;
    const missingFields = issues.map((i: { message: string }) => i.message).join('; ');
    return c.json({
      error: 'Missing or invalid provenance fields',
      reason: missingFields,
      issues: issues,
    }, 400);
  }

  const body = validationResult.data;
  const sanitized = scrubPiiDeep(body) as ContributionPayload;
  const nowIso = new Date().toISOString();

  const sanitizedRecord: CanonicalRuleTelemetry = {
    pattern: sanitized.pattern
      ? sanitized.pattern.slice(0, 120)
      : Object.keys(sanitized.gap_patterns || {})[0] || 'explicit_correction',
    category: sanitized.category ? sanitized.category.slice(0, 64) : 'robustness_consistency',
    example: sanitized.example ? sanitized.example.slice(0, 200) : 'Always verify input flags',
    confidence: sanitized.confidence !== undefined ? sanitized.confidence : 0.8,
    anonymous_id: sanitized.anonymous_id || `anon_${sanitized.source_hash.slice(0, 12)}`,
    source_hash: sanitized.source_hash,
    source_session_id: sanitized.source_session_id,
    extraction_version: sanitized.extraction_version,
    extracted_at: sanitized.extracted_at,
    review_status: sanitized.review_status || 'pending',
    reviewed_by: sanitized.reviewed_by || null,
    reviewed_at: sanitized.reviewed_at || null,
    qa_report_id: sanitized.qa_report_id,
  };

  const storageKey = `raw/${sanitizedRecord.source_hash}_${Date.now()}.json`;

  if (c.env.RAW_CONTRIBUTIONS_BUCKET) {
    await c.env.RAW_CONTRIBUTIONS_BUCKET.put(
      storageKey,
      JSON.stringify(sanitizedRecord, null, 2),
      {
        httpMetadata: { contentType: 'application/json' },
        customMetadata: {
          source_hash: sanitizedRecord.source_hash,
          category: sanitizedRecord.category,
          staged_at: nowIso,
        },
      }
    );
  }

  if (c.env.CONTRIBUTIONS_KV) {
    const ttlSec = parseInt(c.env.RETENTION_TTL_SECONDS || String(RETENTION_TTL_SECONDS), 10);
    await c.env.CONTRIBUTIONS_KV.put(
      `contrib:${sanitizedRecord.source_hash}:${Date.now()}`,
      JSON.stringify(sanitizedRecord),
      { expirationTtl: ttlSec }
    );
  }

  return c.json({
    status: 'Created',
    message: 'Contribution accepted and staged to private R2 bucket',
    storage_key: storageKey,
    residency: c.env.DATA_RESIDENCY || 'EU/US Cloudflare Edge (GDPR Art. 44-49 SCCs)',
  }, 201);
};

app.post('/contribute', handleContribute);
app.post('/api/contribute', handleContribute);

// 3. Admin endpoints for governance
app.post('/admin/approve', async (c) => {
  const auth = c.req.header('Authorization');
  if (c.env.ADMIN_KEY && auth !== `Bearer ${c.env.ADMIN_KEY}`) {
    return c.json({ error: 'Unauthorized' }, 401);
  }
  let body: { rule_id?: string; note?: string } = {};
  try {
    body = await c.req.json();
  } catch {}
  if (!body.rule_id) {
    return c.json({ error: 'rule_id is required' }, 400);
  }
  return c.json({ status: 'approved', rule_id: body.rule_id, approved_at: new Date().toISOString() }, 200);
});

app.post('/admin/reject', async (c) => {
  const auth = c.req.header('Authorization');
  if (c.env.ADMIN_KEY && auth !== `Bearer ${c.env.ADMIN_KEY}`) {
    return c.json({ error: 'Unauthorized' }, 401);
  }
  let body: { rule_id?: string; note?: string } = {};
  try {
    body = await c.req.json();
  } catch {}
  if (!body.rule_id) {
    return c.json({ error: 'rule_id is required' }, 400);
  }
  return c.json({ status: 'rejected', rule_id: body.rule_id, rejected_at: new Date().toISOString(), note: body.note }, 200);
});

export default app;
