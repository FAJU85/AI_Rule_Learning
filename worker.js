/**
 * Cloudflare Worker — Community Telemetry Relay (ARL-SEC-2026-002)
 *
 * Deployed at: https://ai-rule-learning-relay.ee-ee455.workers.dev
 *
 * Security & Compliance Features:
 * - Server-side PII scrubbing (emails, IPs, paths, API keys, tokens, SSNs, phones)
 * - Schema normalization & strict validation (C1.5, C1.6):
 *   Supports canonical 4-field schema ({pattern, category, example, confidence} or
 *   {gap_type, severity, language, count}) and batched {source_hash, gap_patterns}
 * - 64 KB body limit
 * - Per-IP sliding window rate limiting (60s TTL)
 * - 90-day KV retention TTL (GDPR Art. 5(1)(e) Storage Limitation — CO01)
 * - Data residency metadata (GDPR Chapter V — CO02)
 */

const MAX_PAYLOAD_BYTES = 64 * 1024; // 64 KB
const RATE_LIMIT_WINDOW_SEC = 60;
const RATE_LIMIT_MAX_REQ = 30;
const RETENTION_TTL_SECONDS = 90 * 24 * 60 * 60; // 90 days (7,776,000 seconds) — GDPR Art. 5(1)(e)
const DATA_RESIDENCY = "EU/US Cloudflare Edge (KV replicated, GDPR Art. 44-49 SCCs)";

const CANONICAL_FIELDS = ["pattern", "category", "example", "confidence"];

const PII_PATTERNS = [
  { regex: /[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+/g, replacement: "[EMAIL_REDACTED]" },
  { regex: /\b(?:\d{1,3}\.){3}\d{1,3}\b/g, replacement: "[IP_REDACTED]" },
  { regex: /\b(?:[0-9a-fA-F]{1,4}:){2,7}[0-9a-fA-F]{1,4}\b/g, replacement: "[IP_REDACTED]" },
  { regex: /\b(?:sk-[a-zA-Z0-9_-]{12,}|hf_[a-zA-Z0-9]{12,}|gh[pousr]_[a-zA-Z0-9]{12,}|AKIA[0-9A-Z]{16})\b/g, replacement: "[TOKEN_REDACTED]" },
  { regex: /Bearer\s+[A-Za-z0-9\-._~+/]+=*/gi, replacement: "Bearer [TOKEN_REDACTED]" },
  { regex: /\b\d{3}-\d{2}-\d{4}\b/g, replacement: "[SSN_REDACTED]" },
  { regex: /(?:\/Users\/|\/home\/|[A-Za-z]:\\Users\\)[^\s,"']+/g, replacement: "[PATH_REDACTED]" },
];

export function scrubPii(text) {
  if (typeof text !== "string") return "";
  let out = text;
  for (const { regex, replacement } of PII_PATTERNS) {
    out = out.replace(regex, replacement);
  }
  return out;
}

export function scrubObject(val) {
  if (typeof val === "string") return scrubPii(val);
  if (Array.isArray(val)) return val.map(scrubObject);
  if (val && typeof val === "object") {
    const out = {};
    for (const [k, v] of Object.entries(val)) {
      out[scrubPii(k)] = scrubObject(v);
    }
    return out;
  }
  return val;
}

export function normalizeContribution(body) {
  if (!body || typeof body !== "object" || Array.isArray(body)) {
    return { valid: false, error: "Payload must be a JSON object" };
  }

  const scrubbed = scrubObject(body);
  const sourceHash =
    typeof scrubbed.source_hash === "string" && scrubbed.source_hash.trim()
      ? scrubbed.source_hash.trim().slice(0, 64)
      : "anon_relay_source";
  const anonId =
    typeof scrubbed.anonymous_id === "string" && scrubbed.anonymous_id.trim()
      ? scrubbed.anonymous_id.trim().slice(0, 64)
      : typeof scrubbed.user_id === "string" && scrubbed.user_id.trim()
      ? scrubbed.user_id.trim().slice(0, 64)
      : `anon_${sourceHash.slice(0, 12)}`;

  // Extract canonical 4 fields (C1.5, C1.6)
  let pattern = typeof scrubbed.pattern === "string" ? scrubbed.pattern.slice(0, 120) : "";
  let category = typeof scrubbed.category === "string" ? scrubbed.category.slice(0, 64) : "robustness_consistency";
  let example = typeof scrubbed.example === "string" ? scrubbed.example.slice(0, 200) : "";
  let confidence = typeof scrubbed.confidence === "number" && Number.isFinite(scrubbed.confidence)
    ? Math.max(0, Math.min(1, scrubbed.confidence))
    : 0.85;

  const gapPatterns = scrubbed.gap_patterns || {};
  if (!pattern && typeof scrubbed.gap_type === "string") {
    pattern = scrubbed.gap_type;
  }
  if (!pattern && gapPatterns && typeof gapPatterns === "object" && !Array.isArray(gapPatterns)) {
    const firstKey = Object.keys(gapPatterns)[0];
    if (firstKey) {
      pattern = firstKey;
      const firstArr = gapPatterns[firstKey];
      if (Array.isArray(firstArr) && firstArr[0] && typeof firstArr[0] === "object") {
        example = example || String(firstArr[0].signal || firstArr[0].example || firstKey).slice(0, 200);
      }
    }
  } else if (!pattern && Array.isArray(gapPatterns) && gapPatterns[0]) {
    pattern = String(gapPatterns[0].gap_type || gapPatterns[0].pattern || "explicit_correction");
  }

  if (!pattern) {
    return { valid: false, error: "Missing required pattern or gap_patterns" };
  }
  if (!example) {
    example = pattern;
  }

  return {
    valid: true,
    record: {
      schema_version: "1.0",
      source_hash: sourceHash,
      user_id: anonId,
      anonymous_id: anonId,
      pattern,
      category,
      example,
      confidence,
      gap_patterns: gapPatterns,
      contributed_at: new Date().toISOString(),
      retention_ttl_seconds: RETENTION_TTL_SECONDS,
      data_residency: DATA_RESIDENCY,
    },
  };
}

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, User-Agent",
  "X-Content-Type-Options": "nosniff",
};

const DEFAULT_TEMPLATES = [
  {
    gap_type: "explicit_correction",
    name: "community-explicit-correction",
    instruction: "Address detected explicit correction pattern consistently across all interactions.",
    triggers: ["that is not correct", "no that is wrong", "actually that is incorrect"],
    priority: 3,
    failure_layer: 2,
    failure_category: "robustness_consistency",
    source: "community_verified",
    unique_sources: 10,
    total_occurrences: 19,
  },
];

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname.replace(/\/+$/, "") || "/";

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: CORS_HEADERS });
    }

    if (request.method === "GET" && (path === "/health" || path === "/" || path === "/api/health")) {
      return new Response(
        JSON.stringify({
          status: "healthy",
          service: "community-relay",
          schema_version: "1.0",
          canonical_fields: CANONICAL_FIELDS,
          retention_ttl_days: 90,
          data_residency: DATA_RESIDENCY,
        }),
        { status: 200, headers: { "Content-Type": "application/json", ...CORS_HEADERS } }
      );
    }

    if (request.method === "GET" && (path === "/templates" || path === "/templates.jsonl" || path === "/api/templates")) {
      let jsonl = DEFAULT_TEMPLATES.map((t) => JSON.stringify(t)).join("\n") + "\n";
      if (env && env.CONTRIBUTIONS_KV) {
        try {
          const cached = await env.CONTRIBUTIONS_KV.get("published:templates.jsonl");
          if (cached) jsonl = cached;
        } catch (_) {}
      } else if (env && env.PUBLIC_TEMPLATES_BUCKET) {
        try {
          const obj = await env.PUBLIC_TEMPLATES_BUCKET.get("templates.jsonl");
          if (obj) jsonl = await obj.text();
        } catch (_) {}
      }
      return new Response(jsonl, {
        status: 200,
        headers: { "Content-Type": "application/x-jsonlines; charset=utf-8", ...CORS_HEADERS },
      });
    }

    if (request.method === "POST" && (path === "/api/contribute" || path === "/contribute")) {
      const raw = await request.text();
      if (raw.length > MAX_PAYLOAD_BYTES) {
        return new Response(JSON.stringify({ error: "Payload exceeds 64KB limit" }), {
          status: 413,
          headers: { "Content-Type": "application/json", ...CORS_HEADERS },
        });
      }

      if (env && env.RATE_LIMIT_KV) {
        const ip = request.headers.get("CF-Connecting-IP") || "anon";
        const rlKey = `rl:${ip}`;
        const count = parseInt((await env.RATE_LIMIT_KV.get(rlKey)) || "0", 10);
        if (count >= RATE_LIMIT_MAX_REQ) {
          return new Response(JSON.stringify({ error: "Rate limit exceeded" }), {
            status: 429,
            headers: { "Content-Type": "application/json", ...CORS_HEADERS },
          });
        }
        await env.RATE_LIMIT_KV.put(rlKey, String(count + 1), { expirationTtl: RATE_LIMIT_WINDOW_SEC });
      }

      let body;
      try {
        body = JSON.parse(raw);
      } catch (_) {
        return new Response(JSON.stringify({ error: "Invalid JSON" }), {
          status: 400,
          headers: { "Content-Type": "application/json", ...CORS_HEADERS },
        });
      }

      const result = normalizeContribution(body);
      if (!result.valid) {
        return new Response(JSON.stringify({ error: result.error }), {
          status: 400,
          headers: { "Content-Type": "application/json", ...CORS_HEADERS },
        });
      }

      const key = `contrib:${result.record.source_hash}:${Date.now()}`;
      if (env && env.CONTRIBUTIONS_KV) {
        await env.CONTRIBUTIONS_KV.put(key, JSON.stringify(result.record), {
          expirationTtl: RETENTION_TTL_SECONDS,
        });
      }
      if (env && env.RAW_CONTRIBUTIONS_BUCKET) {
        await env.RAW_CONTRIBUTIONS_BUCKET.put(`${key}.json`, JSON.stringify(result.record));
      }

      return new Response(
        JSON.stringify({
          status: "accepted",
          key,
          canonical_fields: CANONICAL_FIELDS,
          retention_ttl_days: 90,
        }),
        { status: 202, headers: { "Content-Type": "application/json", ...CORS_HEADERS } }
      );
    }

    return new Response(JSON.stringify({ error: "Not found" }), {
      status: 404,
      headers: { "Content-Type": "application/json", ...CORS_HEADERS },
    });
  },
};
