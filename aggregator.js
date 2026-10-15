/**
 * Cloudflare Worker — Community Rule Aggregator (Cron Trigger)
 *
 * Architecture:
 * - Reads all raw contributions from private Cloudflare R2 bucket
 * - Groups by gap_type across distinct source_hash values
 * - Enforces k-anonymity threshold: min_sources >= 5
 * - Strict content filtering: blocks code execution, URLs, base64 blobs, long triggers
 * - Publishes sanitized, verified templates.jsonl to public R2 bucket / CDN
 */

export default {
  async scheduled(event, env, ctx) {
    ctx.waitUntil(runAggregation(env));
  },

  async fetch(request, env, ctx) {
    // Manual trigger endpoint for admin or verification testing
    const url = new URL(request.url);
    if (url.pathname === "/aggregate" && request.method === "POST") {
      const authHeader = request.headers.get("Authorization");
      if (env.ADMIN_KEY && authHeader !== `Bearer ${env.ADMIN_KEY}`) {
        return new Response("Unauthorized", { status: 401 });
      }
      const summary = await runAggregation(env);
      return new Response(JSON.stringify(summary, null, 2), {
        headers: { "Content-Type": "application/json" },
      });
    }

    return new Response(JSON.stringify({ service: "community-aggregator", status: "ready" }), {
      headers: { "Content-Type": "application/json" },
    });
  },
};

async function runAggregation(env) {
  if (!env.RAW_CONTRIBUTIONS_BUCKET || !env.PUBLIC_TEMPLATES_BUCKET) {
    return { error: "R2 buckets not configured" };
  }

  // 1. List objects from raw contributions
  const listed = await env.RAW_CONTRIBUTIONS_BUCKET.list({ prefix: "raw/" });
  const records = [];

  for (const obj of listed.objects) {
    const file = await env.RAW_CONTRIBUTIONS_BUCKET.get(obj.key);
    if (file) {
      try {
        const text = await file.text();
        records.push(JSON.parse(text));
      } catch (err) {
        // Skip corrupted records
      }
    }
  }

  // 2. Aggregate by gap_type and compute unique sources (k-anonymity)
  const stats = {};
  for (const rec of records) {
    const sourceHash = rec.source_hash;
    const gapPatterns = rec.gap_patterns || {};

    for (const [gapType, instances] of Object.entries(gapPatterns)) {
      if (!stats[gapType]) {
        stats[gapType] = {
          count: 0,
          uniqueSources: new Set(),
          signals: {},
        };
      }
      stats[gapType].count += instances.length;
      if (sourceHash) {
        stats[gapType].uniqueSources.add(sourceHash);
      }
      for (const inst of instances) {
        const sig = (inst.signal || "").trim();
        if (sig && isValidSignal(sig)) {
          stats[gapType].signals[sig] = (stats[gapType].signals[sig] || 0) + 1;
        }
      }
    }
  }

  // 3. Filter templates meeting k-anonymity (min_sources >= 5) and content safety
  const MIN_SOURCES = 5;
  const verifiedTemplates = [];

  for (const [gapType, info] of Object.entries(stats)) {
    if (info.uniqueSources.size < MIN_SOURCES) {
      continue;
    }

    // Sort top signals
    const sortedSignals = Object.entries(info.signals)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 10)
      .map(([s]) => s);

    verifiedTemplates.push({
      gap_type: gapType,
      name: `community-${gapType.replace(/_/g, "-")}`,
      instruction: `Address detected ${gapType.replace(/_/g, " ")} pattern consistently across all interactions.`,
      triggers: sortedSignals,
      priority: 3,
      failure_layer: 2,
      failure_category: "robustness_consistency",
      source: "community_verified",
      unique_sources: info.uniqueSources.size,
      total_occurrences: info.count,
      published_at: new Date().toISOString(),
    });
  }

  // 4. Publish templates.jsonl and manifest.json to public R2
  const templatesJsonl = verifiedTemplates.map((t) => JSON.stringify(t)).join("\n") + "\n";
  await env.PUBLIC_TEMPLATES_BUCKET.put("templates.jsonl", templatesJsonl, {
    httpMetadata: { contentType: "application/x-jsonlines", cacheControl: "public, max-age=3600" },
  });

  const manifest = {
    version: "1.0.0",
    generated_at: new Date().toISOString(),
    template_count: verifiedTemplates.length,
    min_sources_threshold: MIN_SOURCES,
    sha256: await hashString(templatesJsonl),
  };

  await env.PUBLIC_TEMPLATES_BUCKET.put("manifest.json", JSON.stringify(manifest, null, 2), {
    httpMetadata: { contentType: "application/json", cacheControl: "public, max-age=3600" },
  });

  return {
    status: "Success",
    raw_records_processed: records.length,
    templates_published: verifiedTemplates.length,
    manifest,
  };
}

function isValidSignal(signal) {
  // Reject long free-form text
  if (signal.length > 120) return false;

  // Reject URLs
  if (/https?:\/\//i.test(signal)) return false;

  // Reject code execution or script patterns
  if (/\b(?:eval|exec|os\.system|subprocess|<script>|__import__)\b/i.test(signal)) return false;

  // Reject base64 blobs
  if (/[A-Za-z0-9+/=]{32,}/.test(signal)) return false;

  return true;
}

async function hashString(str) {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(str));
  return Array.from(new Uint8Array(buf))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}
