"use client";

import { useCallback, useEffect, useState } from "react";
import { Activity, CircleCheckBig, CircleX, Clock3, LoaderCircle, Play, Workflow } from "lucide-react";
import { PageHeading } from "@/components/page-heading";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";

type AutomationData = { executions_today: number; success_rate: number | null; workflows: { id: string; name: string; status: string; last_run: string | null; duration_ms: number | null; error: string }[] };

export default function AutomationsPage() {
  const [data, setData] = useState<AutomationData | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const load = useCallback(() => api<AutomationData>("/automations").then(setData).catch(caught => setError(caught instanceof Error ? caught.message : "Could not load workflow state.")), []);
  useEffect(() => { void load(); }, [load]);
  async function runDiscovery() { setRunning(true); setError(""); try { await api("/automations/run-discovery", { method: "POST" }); await load(); } catch (caught) { setError(caught instanceof Error ? caught.message : "Discovery failed."); } finally { setRunning(false); } }
  return <><PageHeading title="Automations" description="Persisted n8n and API workflow execution state without exposing the editor." actions={<Button variant="outline" onClick={runDiscovery} disabled={running}>{running ? <LoaderCircle className="animate-spin" data-icon="inline-start"/> : <Play data-icon="inline-start"/>}{running ? "Running…" : "Run discovery"}</Button>}/>{error ? <p className="mb-4 text-sm text-destructive" role="alert">{error}</p> : null}{!data ? <p className="flex items-center gap-2 py-10 text-sm text-muted-foreground"><LoaderCircle className="size-4 animate-spin"/>Loading workflow runs…</p> : <><div className="mb-6 grid gap-4 md:grid-cols-3"><Card><CardHeader><CardDescription>Executions today</CardDescription><CardTitle className="text-3xl">{data.executions_today}</CardTitle></CardHeader></Card><Card><CardHeader><CardDescription>Success rate</CardDescription><CardTitle className="text-3xl">{data.success_rate === null ? "No runs" : `${data.success_rate}%`}</CardTitle></CardHeader></Card><Card><CardHeader><CardDescription>Last recorded run</CardDescription><CardTitle className="text-xl">{data.workflows.find(item => item.last_run)?.last_run ? new Date(data.workflows.find(item => item.last_run)!.last_run!).toLocaleString() : "Not run"}</CardTitle></CardHeader></Card></div><Card><CardHeader><CardTitle>Workflow health</CardTitle><CardDescription>Failures are persisted for retry and dead-letter handling.</CardDescription></CardHeader><CardContent>{data.workflows.map((workflowItem, index) => { const success = ["SUCCESS", "COMPLETED"].includes(workflowItem.status); const failed = workflowItem.status === "FAILED"; return <div key={workflowItem.id} className="flex items-center gap-4 border-b py-4 last:border-b-0"><div className="flex size-9 items-center justify-center rounded-lg bg-secondary">{index === 9 ? <Activity className="size-4"/> : <Workflow className="size-4"/>}</div><div className="flex-1"><p className="text-sm font-semibold">{workflowItem.id} {workflowItem.name}</p><p className="mt-1 flex items-center gap-1 text-xs text-muted-foreground"><Clock3 className="size-3"/>{workflowItem.last_run ? `${new Date(workflowItem.last_run).toLocaleString()}${workflowItem.duration_ms !== null ? ` · ${workflowItem.duration_ms}ms` : ""}` : "No execution recorded"}</p>{workflowItem.error ? <p className="mt-1 text-xs text-destructive">{workflowItem.error}</p> : null}</div><Badge variant={success ? "success" : failed ? "warning" : "secondary"}>{success ? <CircleCheckBig className="mr-1 size-3"/> : failed ? <CircleX className="mr-1 size-3"/> : null}{workflowItem.status}</Badge></div>; })}</CardContent></Card></>}</>;
}
