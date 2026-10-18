/**
 * Cloudflare Worker Telemetry & Governance Schemas (Zod + TypeScript)
 *
 * Implements specifications from ARL-REM-2026-007 / ARL-SPRINT-001:
 * - 7 mandatory provenance fields
 * - Zod validation schemas for Hono endpoints
 * - k-anonymity and GDPR Art. 5(1)(e) retention policies
 */

import { z } from 'zod';

export const MAX_PAYLOAD_BYTES = 64 * 1024; // 64 KB maximum payload limit
export const RATE_LIMIT_WINDOW_SEC = 60;
export const RATE_LIMIT_MAX_REQ = 30;
export const RETENTION_TTL_SECONDS = 90 * 24 * 60 * 60; // 90 days (7,776,000s)
export const MIN_SOURCES_THRESHOLD = 5; // k-anonymity quorum floor

export const ProvenanceSchema = z.object({
  source_session_id: z.string({ required_error: 'source_session_id is required' }).min(1, 'source_session_id is required'),
  extraction_version: z.string({ required_error: 'extraction_version is required' }).min(1, 'extraction_version is required'),
  extracted_at: z.string({ required_error: 'extracted_at is required' }).min(1, 'extracted_at is required'),
  review_status: z.enum(['pending', 'approved', 'rejected'], {
    required_error: 'review_status is required',
  }),
  reviewed_by: z.string().nullable().optional(),
  reviewed_at: z.string().nullable().optional(),
  qa_report_id: z.string({ required_error: 'qa_report_id is required' }).min(1, 'qa_report_id is required'),
});

export type Provenance = z.infer<typeof ProvenanceSchema>;

export const ContributionPayloadSchema = z.object({
  source_hash: z.string({ required_error: 'source_hash is required' }).min(1, 'source_hash is required'),
  source_session_id: z.string({ required_error: 'source_session_id is required' }).min(1, 'source_session_id is required'),
  extraction_version: z.string({ required_error: 'extraction_version is required' }).min(1, 'extraction_version is required'),
  extracted_at: z.string({ required_error: 'extracted_at is required' }).min(1, 'extracted_at is required'),
  review_status: z.enum(['pending', 'approved', 'rejected']).default('pending'),
  reviewed_by: z.string().nullable().optional(),
  reviewed_at: z.string().nullable().optional(),
  qa_report_id: z.string({ required_error: 'qa_report_id is required' }).min(1, 'qa_report_id is required'),
  anonymous_id: z.string().optional(),
  gap_type: z.string().optional(),
  pattern: z.string().max(250).optional(),
  category: z.string().optional(),
  example: z.string().max(500).optional(),
  confidence: z.number().min(0).max(1).optional(),
  gap_patterns: z.record(
    z.array(
      z.object({
        type: z.string().optional(),
        signal: z.string().optional(),
        snippet: z.string().optional(),
        severity: z.number().optional(),
        turn: z.number().optional(),
      })
    )
  ).optional(),
  total_gaps: z.number().optional(),
  contributed_at: z.string().optional(),
});

export type ContributionPayload = z.infer<typeof ContributionPayloadSchema>;

export interface CanonicalRuleTelemetry {
  pattern: string;
  category: string;
  example: string;
  confidence: number;
  anonymous_id: string;
  source_hash: string;
  source_session_id?: string;
  extraction_version?: string;
  extracted_at?: string;
  review_status?: 'pending' | 'approved' | 'rejected';
  reviewed_by?: string | null;
  reviewed_at?: string | null;
  qa_report_id?: string;
}

export interface ManifestRecord {
  version: string;
  aggregated_at: string;
  min_sources_threshold: number;
  total_contributions_evaluated: number;
  quarantine_dropped_count: number;
  qa_dropped_count: number;
  templates_published_count: number;
  manifest_hash: string;
}

export interface PublishedTemplate {
  gap_type: string;
  category: string;
  instruction: string;
  sample_signal: string;
  confidence: number;
  unique_sources_count: number;
  verified_at: string;
}
