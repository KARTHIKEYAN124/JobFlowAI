"use client";

import { useState } from "react";
import { ExternalLink, LoaderCircle, MessageSquareText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";

type Question = { skill: string; question: string; answer: string; source: string; source_url: string };
type InterviewPack = { questions: Question[]; preparation_plan: string; source_note: string };

export function PrepareInterviewButton({ jobId }: { jobId: string }) {
  const [pack, setPack] = useState<InterviewPack | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  async function prepare() {
    setPending(true); setError("");
    try { setPack(await api<InterviewPack>("/ai/interview", { method: "POST", body: JSON.stringify({ job_id: jobId }) })); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Could not prepare interview questions."); }
    finally { setPending(false); }
  }

  return <div>
    <Button variant="outline" className="w-full" onClick={prepare} disabled={pending}>{pending ? <LoaderCircle className="animate-spin" data-icon="inline-start" /> : <MessageSquareText data-icon="inline-start" />}{pending ? "Searching public sources…" : "Prepare interview questions"}</Button>
    {error ? <p className="mt-3 text-sm text-destructive" role="alert">{error}</p> : null}
    {pack ? <div className="mt-6 space-y-4">
      <Card><CardHeader><CardTitle>Preparation plan</CardTitle></CardHeader><CardContent><p className="whitespace-pre-line text-sm leading-6 text-muted-foreground">{pack.preparation_plan}</p></CardContent></Card>
      {pack.questions.length ? pack.questions.map((item, index) => <Card key={item.source_url}><CardHeader><CardDescription>{item.skill} · Question {index + 1}</CardDescription><CardTitle className="text-base leading-6">{item.question}</CardTitle></CardHeader><CardContent><p className="text-sm leading-6 text-muted-foreground">{item.answer}</p><a className="mt-4 inline-flex items-center gap-1 text-xs font-semibold text-primary hover:underline" href={item.source_url} target="_blank" rel="noreferrer">Read accepted answer on Stack Overflow <ExternalLink className="size-3" /></a></CardContent></Card>) : <p className="rounded-lg border p-4 text-sm text-muted-foreground">No accepted public answers were available for this job’s topics. Use the preparation plan above.</p>}
      <p className="text-xs leading-5 text-muted-foreground">{pack.source_note}</p>
    </div> : null}
  </div>;
}
