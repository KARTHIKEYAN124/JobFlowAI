"use client";

import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, LoaderCircle, Send } from "lucide-react";
import { PageHeading } from "@/components/page-heading";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { api } from "@/lib/api";

const columns = ["DISCOVERED", "SAVED", "PREPARING", "READY", "APPLIED", "INTERVIEW", "OFFER", "REJECTED", "WITHDRAWN", "EXPIRED"] as const;
type Status = typeof columns[number];
type Application = { id: string; job_id: string; status: Status; approved_at: string | null; created_at: string };
type ApiJob = { id: string; title: string; company_name: string };

export default function ApplicationsPage() {
  const [applications, setApplications] = useState<Application[]>([]);
  const [jobs, setJobs] = useState<ApiJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try { const [applicationRecords, jobRecords] = await Promise.all([api<Application[]>("/applications"), api<ApiJob[]>("/jobs?limit=100")]); setApplications(applicationRecords); setJobs(jobRecords); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Could not load applications."); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void load(); }, [load]);

  async function update(application: Application, action: "approve" | "apply") {
    setBusyId(application.id); setError("");
    try {
      const body = action === "approve" ? { approved: true } : { status: "APPLIED" };
      const updated = await api<Application>(`/applications/${application.id}`, { method: "PATCH", body: JSON.stringify(body) });
      setApplications(current => current.map(item => item.id === updated.id ? updated : item));
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Could not update the application."); }
    finally { setBusyId(""); }
  }

  return <>
    <PageHeading title="Applications" description="Track every opportunity from discovery through offer." />
    {error ? <p className="mb-4 rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive" role="alert">{error}</p> : null}
    {loading ? <div className="flex items-center gap-2 py-12 text-sm text-muted-foreground"><LoaderCircle className="size-4 animate-spin" />Loading applications…</div> : applications.length === 0 ? <Card><CardContent className="p-8 text-center text-sm text-muted-foreground">No applications yet. Open Jobs and choose Prepare application.</CardContent></Card> :
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">{columns.map(column => <section key={column}><div className="mb-3 flex items-center justify-between"><h2 className="text-xs font-bold tracking-wider text-muted-foreground">{column}</h2><Badge variant="secondary">{applications.filter(item => item.status === column).length}</Badge></div><div className="flex flex-col gap-3">{applications.filter(item => item.status === column).map(item => {
        const job = jobs.find(candidate => candidate.id === item.job_id);
        const busy = busyId === item.id;
        return <Card key={item.id}><CardContent className="p-4"><Badge variant="outline">{new Date(item.created_at).toLocaleDateString()}</Badge><p className="mt-3 text-sm font-semibold leading-5">{job?.title ?? `Job ${item.job_id}`}</p><p className="mt-1 text-xs text-muted-foreground">{job?.company_name ?? "Imported job"}</p>{item.status === "READY" ? <div className="mt-4">{!item.approved_at ? <Button size="sm" className="w-full" onClick={() => update(item, "approve")} disabled={busy}>{busy ? <LoaderCircle className="animate-spin" /> : <CheckCircle2 />}Review & approve</Button> : <Button size="sm" className="w-full" onClick={() => update(item, "apply")} disabled={busy}>{busy ? <LoaderCircle className="animate-spin" /> : <Send />}Mark applied</Button>}</div> : null}</CardContent></Card>;
      })}</div></section>)}</div>}
    <div className="mt-6 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950"><strong>Human approval is mandatory.</strong> JobFlow prepares documents and answers, but it never submits an application without your review. “Mark applied” records an application you submitted; it does not send it to the employer.</div>
  </>;
}
