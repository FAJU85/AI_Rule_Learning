/**
 * Cloudflare Worker — Community Contribution Relay
 *
 * Architecture:
 * - Ingestion endpoint for anonymous gap telemetry
 * - Validates schema, size limits, and rate limits
 * - Scans for PII and prompt injection attacks on write path
 * - Writes sanitized contributions to private Cloudflare R2 bucket
 * - Never publishes directly; deferred to Aggregator Cron (k-anonymity >= 5)
 */

export default {
  async fetch(request, env, ctx) {
    // 1. CORS Preflight
    if (request.method === "OPTIONS") {
      return new Response(null, {
        status: 204,
        headers: {
          "Access-Control-Allow-Origin": "*",
          "Access-Control-Allow-Methods": "POST, OPTIONS",
          "Access-Control-Allow-Headers": "Content-Type, User-Agent",
        },
      });
    }

    const url = new URL(request.url);

    // Health check
    if (url.pathname === "/health" || url.pathname === "/") {
      return new Response(JSON.stringify({ status: "healthy", service: "community-relay" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (url.pathname !== "/api/contribute" && url.pathname !== "/api/templates") {
      return new Response(JSON.stringify({ error: "Not Found" }), {
        status: 404,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (request.method !== "POST") {
      return new Response(JSON.stringify({ error: "Method Not Allowed" }), {
        status: 405,
        headers: { "Content-Type": "application/json" },
      });
    }

    // 2. Size Limit Validation (Max 64KB)
    const contentLength = parseInt(request.headers.get("content-length") || "0", 10);
    if (contentLength > 64 * 1024) {
      return new Response(JSON.stringify({ error: "Payload Too Large: max 64KB allowed" }), {
        status: 413,
        headers: { "Content-Type": "application/json" },
      });
    }

    // 3. Client IP Rate Limiting (Heuristic or KV)
    const clientIP = request.headers.get("cf-connecting-ip") || "unknown";
    if (env.RATE_LIMIT_KV) {
      const minuteKey = `rate:${clientIP}:${Math.floor(Date.now() / 60000)}`;
      const currentCount = parseInt((await env.RATE_LIMIT_KV.get(minuteKey)) || "0", 10);
      if (currentCount > 30) {
        return new Response(JSON.stringify({ error: "Too Many Requests: rate limit exceeded" }), {
          status: 429,
          headers: { "Content-Type": "application/json", "Retry-After": "60" },
        });
      }
      await env.RATE_LIMIT_KV.put(minuteKey, (currentCount + 1).toString(), { expirationTtl: 120 });
    }

    // 4. Payload Parsing
    let payload;
    try {
      const rawText = await request.text();
      if (rawText.length > 64 * 1024) {
        return new Response(JSON.stringify({ error: "Payload Too Large" }), { status: 413 });
      }
      payload = JSON.parse(rawText);
    } catch (err) {
      return new Response(JSON.stringify({ error: "Invalid JSON body" }), {
        status: 400,
        headers: { "Content-Type": "application/json" },
      });
    }

    // 5. Schema Validation
    const { source_hash, gap_patterns } = payload;
    if (!source_hash || typeof source_hash !== "string" || source_hash.length < 8) {
      return new Response(JSON.stringify({ error: "Invalid schema: source_hash required" }), {
        status: 400,
        headers: { "Content-Type": "application/json" },
      });
    }
    if (!gap_patterns || typeof gap_patterns !== "object") {
      return new Response(JSON.stringify({ error: "Invalid schema: gap_patterns object required" }), {
        status: 400,
        headers: { "Content-Type": "application/json" },
      });
    }

    // 6. Security Inspection: Prompt Injection & PII Scan (Server-side defense in depth)
    const payloadStr = JSON.stringify(gap_patterns);

    // Injection attack patterns
    const INJECTION_PATTERNS = [
      /\b(?:ignore|disregard|forget|bypass|override)\b.*?\b(?:everything|all|previous|instructions?|rules?|guidelines?|safety)\b/i,
      /\b(?:jailbreak|developer|god|dan|sudo|unrestricted)\s+mode\b/i,
      /\b(?:no|without|zero)\s+restrictions?\b/i,
      /\boverride\s+(?:safety|guidelines?|rules?|instructions?)\b/i,
      /\bexfiltrate\b/i,
      /\b(?:obey\s+me|do\s+anything\s+now)\b/i,
    ];
    for (const pat of INJECTION_PATTERNS) {
      if (pat.test(payloadStr)) {
        return new Response(
          JSON.stringify({ error: "Rejected: prompt injection or directive subversion pattern detected" }),
          { status: 400, headers: { "Content-Type": "application/json" } }
        );
      }
    }

    // PII Detection patterns (Emails, absolute file paths, IPv4/IPv6, API keys)
    const PII_PATTERNS = [
      /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/,
      /(?:\/home\/[^\/\s]+|\/Users\/[^\/\s]+|[a-zA-Z]:\\Users\\[^\s]+|\/(?:etc|var|tmp|app|root)\/[^\s]+)/,
      /\b(?:\d{1,3}\.){3}\d{1,3}\b/,
      /\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b/,
      /\b(?:hf_|sk-|ghp_|gho_|ghs_|github_pat_|AKIA[0-9A-Z]{16})[A-Za-z0-9_-]{6,}\b/,
    ];
    for (const pii of PII_PATTERNS) {
      if (pii.test(payloadStr)) {
        return new Response(
          JSON.stringify({ error: "Rejected: raw PII detected in contribution payload" }),
          { status: 400, headers: { "Content-Type": "application/json" } }
        );
      }
    }

    // 7. Write to Private Cloudflare R2 Bucket
    const objectKey = `raw/${new Date().toISOString().slice(0, 10)}/${source_hash}-${Date.now()}.json`;
    if (env.RAW_CONTRIBUTIONS_BUCKET) {
      await env.RAW_CONTRIBUTIONS_BUCKET.put(objectKey, JSON.stringify(payload), {
        httpMetadata: { contentType: "application/json" },
        customMetadata: {
          clientIPHash: await hashString(clientIP),
          receivedAt: new Date().toISOString(),
        },
      });
    }

    return new Response(JSON.stringify({ status: "Accepted", key: objectKey }), {
      status: 202,
      headers: {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
      },
    });
  },
};

async function hashString(str) {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(str));
  return Array.from(new Uint8Array(buf))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}
