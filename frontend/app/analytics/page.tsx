"use client";

import { useEffect, useState } from "react";
import { LoaderCircle } from "lucide-react";
import { PageHeading } from "@/components/page-heading";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";

type Overview = { match_to_apply_rate: number; application_to_interview_rate: number; average_match: number; weekly_jobs: { label: string; count: number }[]; ai: { requests: number; input_tokens: number; output_tokens: number; cost_usd: number } };

export default function AnalyticsPage() {
  const [data, setData] = useState<Overview | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { void api<Overview>("/analytics/overview").then(setData).catch(caught => setError(caught instanceof Error ? caught.message : "Could not load analytics.")); }, []);
  if (!data) return <><PageHeading title="Analytics" description="Measured signals from your search and applications."/>{error ? <p className="text-sm text-destructive" role="alert">{error}</p> : <p className="flex items-center gap-2 py-10 text-sm text-muted-foreground"><LoaderCircle className="size-4 animate-spin"/>Loading analytics…</p>}</>;
  const maximum = Math.max(1, ...data.weekly_jobs.map(item => item.count));
  return <><PageHeading title="Analytics" description="Measured signals from your search, matches, applications, and AI usage."/><div className="grid gap-6 md:grid-cols-3">{[["Match-to-apply", `${data.match_to_apply_rate}%`], ["Application-to-interview", `${data.application_to_interview_rate}%`], ["Average match", `${data.average_match}%`]].map(([label, value]) => <Card key={label}><CardHeader><CardDescription>{label}</CardDescription><CardTitle className="text-3xl">{value}</CardTitle></CardHeader></Card>)}</div><div className="mt-6 grid gap-6 xl:grid-cols-[2fr_1fr]"><Card><CardHeader><CardTitle>Relevant jobs discovered</CardTitle><CardDescription>Last 12 weeks from persisted jobs</CardDescription></CardHeader><CardContent><div className="flex h-72 items-end gap-2">{data.weekly_jobs.map(item => <div key={item.label} className="group flex h-full flex-1 flex-col items-center justify-end gap-2"><span className="text-[10px]">{item.count}</span><div className="w-full min-h-1 rounded-t bg-primary/80" style={{ height: `${Math.max(2, item.count / maximum * 90)}%` }}/><span className="text-[10px] text-muted-foreground">{item.label}</span></div>)}</div></CardContent></Card><Card><CardHeader><CardTitle>AI usage</CardTitle><CardDescription>Recorded provider activity for your account</CardDescription></CardHeader><CardContent className="space-y-4 text-sm"><p><strong>{data.ai.requests}</strong> requests</p><p><strong>{data.ai.input_tokens.toLocaleString()}</strong> input tokens</p><p><strong>{data.ai.output_tokens.toLocaleString()}</strong> output tokens</p><p><strong>${data.ai.cost_usd.toFixed(4)}</strong> estimated cost</p></CardContent></Card></div></>;
}
