"use client";

import { useEffect, useState } from "react";
import { LoaderCircle, Save } from "lucide-react";
import { PageHeading } from "@/components/page-heading";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";

type Preferences = { high_match_email: boolean; daily_digest: boolean; followup_reminders: boolean; interview_preparation: boolean; notification_email: string; telegram_chat_id: string };
const toggles: [keyof Preferences, string][] = [["high_match_email", "High-match email alerts"], ["daily_digest", "Daily job digest"], ["followup_reminders", "Follow-up reminders"], ["interview_preparation", "Interview preparation"]];

export default function SettingsPage() {
  const [preferences, setPreferences] = useState<Preferences | null>(null);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  useEffect(() => { void api<Preferences>("/settings").then(setPreferences).catch(caught => setError(caught instanceof Error ? caught.message : "Could not load settings.")); }, []);
  async function save() { if (!preferences) return; setSaving(true); setError(""); setMessage(""); try { setPreferences(await api<Preferences>("/settings", { method: "PUT", body: JSON.stringify(preferences) })); setMessage("Preferences saved."); } catch (caught) { setError(caught instanceof Error ? caught.message : "Could not save settings."); } finally { setSaving(false); } }
  return <><PageHeading title="Settings" description="Persisted notification, privacy, security, and integration preferences." actions={<Button onClick={save} disabled={!preferences || saving}>{saving ? <LoaderCircle className="animate-spin" data-icon="inline-start"/> : <Save data-icon="inline-start"/>}{saving ? "Saving…" : "Save settings"}</Button>}/>{error ? <p className="mb-4 text-sm text-destructive" role="alert">{error}</p> : null}{message ? <p className="mb-4 text-sm text-emerald-700" role="status">{message}</p> : null}{!preferences ? <p className="flex items-center gap-2 py-10 text-sm text-muted-foreground"><LoaderCircle className="size-4 animate-spin"/>Loading preferences…</p> : <><Card><CardHeader><CardTitle>Notifications</CardTitle><CardDescription>Choose when JobFlow should notify you. Changes are stored with your account.</CardDescription></CardHeader><CardContent>{toggles.map(([key, label]) => <div key={key} className="flex items-center justify-between border-b py-4 last:border-b-0"><div><p className="text-sm font-semibold">{label}</p><p className="mt-1 text-xs text-muted-foreground">Sent only through configured channels.</p></div><Button variant={preferences[key] ? "default" : "outline"} size="sm" onClick={() => setPreferences(value => value ? { ...value, [key]: !value[key] } : value)}>{preferences[key] ? "Enabled" : "Disabled"}</Button></div>)}</CardContent></Card><Card className="mt-6"><CardHeader><CardTitle>Delivery channels</CardTitle><CardDescription>Provider credentials stay on the backend or in n8n; only destination identifiers are stored here.</CardDescription></CardHeader><CardContent className="grid gap-4 md:grid-cols-2"><label className="space-y-2 text-sm font-medium">Notification email<Input type="email" value={preferences.notification_email} onChange={event => setPreferences({ ...preferences, notification_email: event.target.value })}/></label><label className="space-y-2 text-sm font-medium">Telegram chat ID<Input value={preferences.telegram_chat_id} onChange={event => setPreferences({ ...preferences, telegram_chat_id: event.target.value })}/></label></CardContent></Card><Card className="mt-6"><CardHeader><CardTitle>Security controls</CardTitle><CardDescription>Expiring JWT sessions, enforced admin RBAC, signed webhooks, API rate limits, input validation, parameterized SQL, and validated PDF storage are enforced by the backend.</CardDescription></CardHeader></Card></>}</>;
}
