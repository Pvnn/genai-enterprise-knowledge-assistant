/**
 * Admin Dashboard Type Definitions
 */

export interface QueryActivity {
  query_id: string;
  raw_query: string;
  created_at: string;
  confidence_score: number | null;
  answered_or_refused: boolean | null;
  feedback_thumbs_up_down: boolean | null;
  feedback_comment: string | null;
}

export interface AdminAnalyticsData {
  total_queries: number;
  answered_queries: number;
  refused_queries: number;
  avg_confidence: number;
  positive_feedback_count: number;
  negative_feedback_count: number;
  csat_percent: number;
  total_documents: number;
  total_chunks: number;
  total_members: number;
  recent_activity: QueryActivity[];
  department_distribution: Record<string, number>;
}

export interface SectionNode {
  title?: string;
  level?: number;
  subsections?: SectionNode[];
  chunks?: string[];
  [key: string]: unknown;
}

export interface AdminDocument {
  id: string;
  tenant_id: string;
  title: string;
  department: string | null;
  doc_type: string | null;
  effective_date: string | null;
  version_status: "current" | "superseded" | string;
  source_path: string | null;
  summary: string | null;
  section_tree: Record<string, unknown> | unknown[] | null;
  ingestion_status: "pending" | "processing" | "done" | "failed" | string;
  chunk_count: number;
}

export interface AdminUser {
  id: string;
  tenant_id: string;
  email: string;
  role: "admin" | "member" | string;
}

export interface GlossaryEntry {
  id?: string;
  term: string;
  expansion: string;
}
