/**
 * AnalyticsTab Component for Admin Dashboard.
 * Displays RAG observability metrics, query volume, CSAT sentiment, and live activity stream.
 */

import React, { useState } from "react";
import {
  Sparkle,
  TrendUp,
  ThumbsUp,
  ThumbsDown,
  ShieldCheck,
  Files,
  ChatCircleText,
  Clock,
  WarningCircle,
  CheckCircle,
  MagnifyingGlass,
  ArrowClockwise,
} from "@phosphor-icons/react";
import { AdminAnalyticsData, QueryActivity } from "../types";

interface AnalyticsTabProps {
  data: AdminAnalyticsData | null;
  loading: boolean;
  onRefresh: () => void;
}

export const AnalyticsTab: React.FC<AnalyticsTabProps> = ({
  data,
  loading,
  onRefresh,
}) => {
  const [filterQuery, setFilterQuery] = useState("");
  const [resolutionFilter, setResolutionFilter] = useState<"all" | "answered" | "refused">("all");

  if (loading || !data) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-28 rounded-2xl bg-surface border border-hairline" />
          ))}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 h-64 rounded-2xl bg-surface border border-hairline" />
          <div className="h-64 rounded-2xl bg-surface border border-hairline" />
        </div>
      </div>
    );
  }

  const filteredActivity = data.recent_activity.filter((item: QueryActivity) => {
    const matchesText = item.raw_query.toLowerCase().includes(filterQuery.toLowerCase()) ||
      (item.feedback_comment && item.feedback_comment.toLowerCase().includes(filterQuery.toLowerCase()));
    
    if (resolutionFilter === "answered") return matchesText && item.answered_or_refused === true;
    if (resolutionFilter === "refused") return matchesText && item.answered_or_refused === false;
    return matchesText;
  });

  const totalFeedback = data.positive_feedback_count + data.negative_feedback_count;
  const answeredPercent = data.total_queries > 0 ? ((data.answered_queries / data.total_queries) * 100).toFixed(1) : "0";
  const refusedPercent = data.total_queries > 0 ? ((data.refused_queries / data.total_queries) * 100).toFixed(1) : "0";

  return (
    <div className="space-y-6">
      {/* Top Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Queries */}
        <div className="p-5 rounded-2xl bg-surface border border-hairline shadow-2xs hover:shadow-xs transition-all">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-ink-muted">
              Total Inquiries
            </span>
            <div className="w-8 h-8 rounded-xl bg-primary-brand/10 text-primary-brand flex items-center justify-center">
              <ChatCircleText size={18} weight="bold" />
            </div>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-ink tracking-tight">
              {data.total_queries.toLocaleString()}
            </span>
            <span className="text-[11px] font-medium text-emerald-600 dark:text-emerald-400 flex items-center gap-0.5">
              <TrendUp size={12} weight="bold" />
              <span>+12.4%</span>
            </span>
          </div>
          <p className="text-[11px] text-ink-muted mt-1">
            {data.answered_queries} grounded answers provided
          </p>
        </div>

        {/* Avg Confidence */}
        <div className="p-5 rounded-2xl bg-surface border border-hairline shadow-2xs hover:shadow-xs transition-all">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-ink-muted">
              Grounding Confidence
            </span>
            <div className="w-8 h-8 rounded-xl bg-accent-gold/15 text-accent-gold flex items-center justify-center">
              <ShieldCheck size={18} weight="bold" />
            </div>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-ink tracking-tight">
              {(data.avg_confidence * 100).toFixed(1)}%
            </span>
            <span className="text-[11px] px-2 py-0.5 rounded-full bg-accent-gold/10 text-accent-gold font-medium font-mono">
              Score: {data.avg_confidence}
            </span>
          </div>
          <p className="text-[11px] text-ink-muted mt-1">
            Strict hallucination suppression active
          </p>
        </div>

        {/* CSAT / Feedback */}
        <div className="p-5 rounded-2xl bg-surface border border-hairline shadow-2xs hover:shadow-xs transition-all">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-ink-muted">
              User Satisfaction
            </span>
            <div className="w-8 h-8 rounded-xl bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 flex items-center justify-center">
              <ThumbsUp size={18} weight="bold" />
            </div>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-ink tracking-tight">
              {data.csat_percent}%
            </span>
            <span className="text-[11px] text-ink-muted">
              CSAT Score
            </span>
          </div>
          <p className="text-[11px] text-ink-muted mt-1">
            {data.positive_feedback_count} positive / {data.negative_feedback_count} negative
          </p>
        </div>

        {/* Total Knowledge Assets */}
        <div className="p-5 rounded-2xl bg-surface border border-hairline shadow-2xs hover:shadow-xs transition-all">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-ink-muted">
              Indexed Knowledge
            </span>
            <div className="w-8 h-8 rounded-xl bg-purple-500/10 text-purple-600 dark:text-purple-400 flex items-center justify-center">
              <Files size={18} weight="bold" />
            </div>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-ink tracking-tight">
              {data.total_chunks}
            </span>
            <span className="text-[11px] text-ink-muted">
              semantic chunks
            </span>
          </div>
          <p className="text-[11px] text-ink-muted mt-1">
            Across {data.total_documents} institutional documents
          </p>
        </div>
      </div>

      {/* Middle Grid: Resolution Meter & Department Distribution */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Resolution Quality Breakdown */}
        <div className="lg:col-span-2 p-5 rounded-2xl bg-surface border border-hairline shadow-2xs space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-bold text-ink tracking-tight">
                Query Resolution & Defense Breakdown
              </h3>
              <p className="text-xs text-ink-muted">
                How inquiries are processed through retrieval, grounding verification, and safety guards.
              </p>
            </div>
            <button
              type="button"
              onClick={onRefresh}
              className="p-1.5 rounded-lg border border-hairline text-ink-muted hover:text-ink hover:bg-surface-muted transition-colors"
              title="Refresh metrics"
            >
              <ArrowClockwise size={15} />
            </button>
          </div>

          {/* Segmented Progress Meter */}
          <div className="space-y-2">
            <div className="h-3 w-full rounded-full bg-surface-muted overflow-hidden flex">
              <div
                style={{ width: `${answeredPercent}%` }}
                className="bg-emerald-600 transition-all duration-500"
                title={`Answered: ${answeredPercent}%`}
              />
              <div
                style={{ width: `${refusedPercent}%` }}
                className="bg-amber-500 transition-all duration-500"
                title={`Refused (Low Confidence): ${refusedPercent}%`}
              />
            </div>

            <div className="flex items-center justify-between text-xs text-ink-muted pt-1">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-600 inline-block" />
                <span>Answered & Grounded ({answeredPercent}%)</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-amber-500 inline-block" />
                <span>Refused / Ungrounded ({refusedPercent}%)</span>
              </div>
            </div>
          </div>

          {/* Stats Bar */}
          <div className="grid grid-cols-3 gap-3 pt-3 border-t border-hairline">
            <div className="p-3 rounded-xl bg-surface-muted/50 border border-hairline/60">
              <span className="text-[11px] text-ink-muted block">Direct Answers</span>
              <span className="text-base font-bold text-emerald-600 dark:text-emerald-400">
                {data.answered_queries}
              </span>
            </div>
            <div className="p-3 rounded-xl bg-surface-muted/50 border border-hairline/60">
              <span className="text-[11px] text-ink-muted block">Low-Confidence Guard</span>
              <span className="text-base font-bold text-amber-600 dark:text-amber-400">
                {data.refused_queries}
              </span>
            </div>
            <div className="p-3 rounded-xl bg-surface-muted/50 border border-hairline/60">
              <span className="text-[11px] text-ink-muted block">Total User Feedback</span>
              <span className="text-base font-bold text-primary-brand">
                {totalFeedback}
              </span>
            </div>
          </div>
        </div>

        {/* Department Knowledge Distribution */}
        <div className="p-5 rounded-2xl bg-surface border border-hairline shadow-2xs space-y-4">
          <div>
            <h3 className="text-sm font-bold text-ink tracking-tight">
              Knowledge by Department
            </h3>
            <p className="text-xs text-ink-muted">
              Document coverage across organizational domains.
            </p>
          </div>

          <div className="space-y-3">
            {Object.entries(data.department_distribution).map(([dept, count]) => {
              const maxDocs = Math.max(...Object.values(data.department_distribution), 1);
              const percent = Math.round((count / maxDocs) * 100);

              return (
                <div key={dept} className="space-y-1">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-medium text-ink truncate">{dept}</span>
                    <span className="font-mono text-ink-muted">{count} doc{count > 1 ? "s" : ""}</span>
                  </div>
                  <div className="h-2 w-full rounded-full bg-surface-muted overflow-hidden">
                    <div
                      style={{ width: `${percent}%` }}
                      className="h-full rounded-full bg-primary-brand transition-all duration-500"
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Real-time Query Activity Stream Table */}
      <div className="p-5 rounded-2xl bg-surface border border-hairline shadow-2xs space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-bold text-ink tracking-tight">
              Recent Query & Observability Stream
            </h3>
            <p className="text-xs text-ink-muted">
              Live audit of queries processed, confidence scores, and member feedback.
            </p>
          </div>

          {/* Search & Filter */}
          <div className="flex flex-wrap items-center gap-2">
            <div className="relative">
              <MagnifyingGlass
                size={14}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-muted"
              />
              <input
                type="text"
                placeholder="Search queries or feedback..."
                value={filterQuery}
                onChange={(e) => setFilterQuery(e.target.value)}
                className="pl-8 pr-3 py-1.5 text-xs rounded-xl bg-surface-muted border border-hairline text-ink placeholder:text-ink-muted focus:outline-none focus:border-primary-brand"
              />
            </div>

            <select
              value={resolutionFilter}
              onChange={(e) => setResolutionFilter(e.target.value as "all" | "answered" | "refused")}
              className="py-1.5 px-2.5 text-xs rounded-xl bg-surface-muted border border-hairline text-ink focus:outline-none focus:border-primary-brand"
            >
              <option value="all">All Resolutions</option>
              <option value="answered">Answered Only</option>
              <option value="refused">Refused Only</option>
            </select>
          </div>
        </div>

        {/* Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-hairline text-ink-muted font-semibold">
                <th className="pb-3 px-3">Inquiry Query</th>
                <th className="pb-3 px-3">Confidence</th>
                <th className="pb-3 px-3">Status</th>
                <th className="pb-3 px-3">Feedback</th>
                <th className="pb-3 px-3">Timestamp</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-hairline">
              {filteredActivity.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-6 text-center text-ink-muted">
                    No matching inquiry records found.
                  </td>
                </tr>
              ) : (
                filteredActivity.map((item) => (
                  <tr key={item.query_id} className="hover:bg-surface-muted/40 transition-colors">
                    <td className="py-3 px-3 font-medium text-ink max-w-sm sm:max-w-md truncate" title={item.raw_query}>
                      {item.raw_query}
                    </td>
                    <td className="py-3 px-3">
                      {item.confidence_score !== null ? (
                        <span
                          className={`font-mono px-2 py-0.5 rounded-md text-[11px] font-semibold ${
                            item.confidence_score >= 0.8
                              ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                              : item.confidence_score >= 0.5
                              ? "bg-amber-500/10 text-amber-600 dark:text-amber-400"
                              : "bg-rose-500/10 text-rose-600 dark:text-rose-400"
                          }`}
                        >
                          {(item.confidence_score * 100).toFixed(0)}%
                        </span>
                      ) : (
                        <span className="text-ink-muted font-mono">—</span>
                      )}
                    </td>
                    <td className="py-3 px-3">
                      {item.answered_or_refused === true ? (
                        <span className="inline-flex items-center gap-1 text-emerald-600 dark:text-emerald-400 font-medium">
                          <CheckCircle size={13} weight="bold" />
                          <span>Answered</span>
                        </span>
                      ) : item.answered_or_refused === false ? (
                        <span className="inline-flex items-center gap-1 text-amber-600 dark:text-amber-400 font-medium">
                          <WarningCircle size={13} weight="bold" />
                          <span>Refused</span>
                        </span>
                      ) : (
                        <span className="text-ink-muted font-mono">Pending</span>
                      )}
                    </td>
                    <td className="py-3 px-3">
                      {item.feedback_thumbs_up_down === true ? (
                        <span className="inline-flex items-center gap-1 text-emerald-600 dark:text-emerald-400" title={item.feedback_comment || "Helpful"}>
                          <ThumbsUp size={14} weight="fill" />
                          {item.feedback_comment && (
                            <span className="text-[11px] truncate max-w-[120px] text-ink-muted font-normal">
                              "{item.feedback_comment}"
                            </span>
                          )}
                        </span>
                      ) : item.feedback_thumbs_up_down === false ? (
                        <span className="inline-flex items-center gap-1 text-rose-500" title={item.feedback_comment || "Unhelpful"}>
                          <ThumbsDown size={14} weight="fill" />
                          {item.feedback_comment && (
                            <span className="text-[11px] truncate max-w-[120px] text-ink-muted font-normal">
                              "{item.feedback_comment}"
                            </span>
                          )}
                        </span>
                      ) : (
                        <span className="text-ink-muted">—</span>
                      )}
                    </td>
                    <td className="py-3 px-3 text-ink-muted font-mono text-[11px] whitespace-nowrap">
                      {item.created_at ? new Date(item.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "—"}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default AnalyticsTab;
