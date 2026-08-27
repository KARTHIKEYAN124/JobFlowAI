"use client";

import { ExternalLink, Puzzle, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function PortalLaunchPage() {
  const [target, setTarget] = useState("");
  const [waiting, setWaiting] = useState(true);

  useEffect(() => {
    const value = new URLSearchParams(window.location.hash.slice(1)).get("target") ?? "";
    try { setTarget(new URL(value).protocol === "https:" ? value : ""); }
    catch { setTarget(""); }
    const timeout = window.setTimeout(() => setWaiting(false), 1800);
    return () => window.clearTimeout(timeout);
  }, []);

  return <main className="flex min-h-screen items-center justify-center bg-muted/30 p-4">
    <Card className="w-full max-w-lg">
      <CardHeader><div className="mb-3 flex size-11 items-center justify-center rounded-lg bg-primary text-primary-foreground"><Puzzle className="size-5" /></div><CardTitle>{waiting ? "Connecting JobFlow Companion…" : "Companion extension not detected"}</CardTitle><CardDescription>{waiting ? "The employer application will open automatically." : "JobFlow could not hand the reviewed application to the browser extension."}</CardDescription></CardHeader>
      <CardContent className="space-y-4 text-sm">
        {!waiting ? <><ol className="list-decimal space-y-2 pl-5 text-muted-foreground"><li>Open <strong>chrome://extensions</strong> or <strong>edge://extensions</strong>.</li><li>Find JobFlow AI Companion and click <strong>Reload</strong>.</li><li>Confirm its version is <strong>1.3.1</strong>.</li><li>Return here and try again.</li></ol><div className="flex flex-wrap gap-2"><Button type="button" onClick={() => window.location.reload()}><RefreshCw data-icon="inline-start" />Try again</Button>{target ? <Button asChild variant="outline"><a href={target}>Continue without autofill <ExternalLink data-icon="inline-end" /></a></Button> : null}</div></> : <p className="text-muted-foreground">Do not close this tab. If it stays here, the extension needs to be reloaded.</p>}
      </CardContent>
    </Card>
  </main>;
}
