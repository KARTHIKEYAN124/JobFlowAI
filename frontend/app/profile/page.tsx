"use client";

import { ChangeEvent, useEffect, useState } from "react";
import { FileUp, LoaderCircle, Save } from "lucide-react";
import { PageHeading } from "@/components/page-heading";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api, apiForm } from "@/lib/api";

type Profile = {
  full_name: string; headline: string; skills: string[];
  experience: Record<string, unknown>[]; education: Record<string, unknown>[]; projects: Record<string, unknown>[];
  languages: Record<string, string>; preferred_roles: string[]; preferred_locations: string[];
  expected_salary: string; remote_preference: string;
};
type Resume = { filename: string; structured_data: { skills?: string[] }; created_at?: string; job_scan?: { source?: string; found: number; imported: number; matched: number; error?: string } };
const emptyProfile: Profile = { full_name: "", headline: "", skills: [], experience: [], education: [], projects: [], languages: {}, preferred_roles: [], preferred_locations: [], expected_salary: "", remote_preference: "hybrid" };

export default function ProfilePage() {
  const [profile, setProfile] = useState(emptyProfile);
  const [roles, setRoles] = useState("");
  const [locations, setLocations] = useState("");
  const [resume, setResume] = useState<Resume | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    async function load() {
      try {
        const current = await api<Profile>("/profile");
        setProfile(current);
        setRoles(current.preferred_roles.join(", "));
        setLocations(current.preferred_locations.join(", "));
        setResume(await api<Resume>("/resume").catch(() => null));
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : "Could not load your profile.");
      } finally { setLoading(false); }
    }
    void load();
  }, []);

  const list = (value: string) => value.split(",").map(item => item.trim()).filter(Boolean);
  async function save() {
    setSaving(true); setError(""); setMessage("");
    try {
      const updated = await api<Profile>("/profile", { method: "PUT", body: JSON.stringify({ ...profile, preferred_roles: list(roles), preferred_locations: list(locations) }) });
      setProfile(updated);
      setMessage("Profile saved. Your name and preferences are now updated.");
      window.dispatchEvent(new CustomEvent("jobflow-profile-updated", { detail: updated }));
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Could not save your profile."); }
    finally { setSaving(false); }
  }

  async function upload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setUploading(true); setError(""); setMessage("");
    try {
      const form = new FormData(); form.append("file", file);
      const uploaded = await apiForm<Resume>("/resume", form);
      setResume(uploaded);
      const scan = uploaded.job_scan;
      setMessage(scan?.error ? `${uploaded.filename} was processed, but ${scan.error.toLowerCase()}. You can retry from Jobs.` : `${uploaded.filename} processed. The internet scan found ${scan?.found ?? 0} skill-related jobs and imported ${scan?.imported ?? 0} new jobs.`);
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Could not upload your resume."); }
    finally { setUploading(false); event.target.value = ""; }
  }

  const skills = resume?.structured_data.skills ?? profile.skills;
  return <>
    <PageHeading title="Candidate profile" description="One profile powers matching, documents, analytics, and interview preparation." actions={<Button onClick={save} disabled={loading || saving}>{saving ? <LoaderCircle className="animate-spin" data-icon="inline-start" /> : <Save data-icon="inline-start" />}{saving ? "Saving…" : "Save profile"}</Button>} />
    {error ? <p className="mb-4 rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive" role="alert">{error}</p> : null}
    {message ? <p className="mb-4 rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900" role="status">{message}</p> : null}
    <div className="grid gap-6 xl:grid-cols-[1.4fr_1fr]">
      <Card><CardHeader><CardTitle>Preferences</CardTitle><CardDescription>Keep these precise to improve matching.</CardDescription></CardHeader><CardContent className="grid gap-5 md:grid-cols-2">
        <Field label="Full name" value={profile.full_name} disabled={loading} onChange={value => setProfile(current => ({ ...current, full_name: value }))} />
        <Field label="Headline" value={profile.headline} disabled={loading} onChange={value => setProfile(current => ({ ...current, headline: value }))} />
        <Field label="Preferred roles" value={roles} disabled={loading} onChange={setRoles} placeholder="Backend Developer, AI Engineer" />
        <Field label="Locations" value={locations} disabled={loading} onChange={setLocations} placeholder="Berlin, Potsdam, Remote" />
        <Field label="Expected salary" value={profile.expected_salary} disabled={loading} onChange={value => setProfile(current => ({ ...current, expected_salary: value }))} placeholder="€18–22/hour" />
        <Field label="Remote preference" value={profile.remote_preference} disabled={loading} onChange={value => setProfile(current => ({ ...current, remote_preference: value }))} placeholder="hybrid" />
      </CardContent></Card>
      <div className="flex flex-col gap-6">
        <Card><CardHeader><CardTitle>Resume</CardTitle><CardDescription>PDF · maximum 5 MB · selectable text required</CardDescription></CardHeader><CardContent>
          <label className="block"><input className="sr-only" type="file" accept="application/pdf,.pdf" onChange={upload} disabled={uploading} /><span className="inline-flex h-10 w-full cursor-pointer items-center justify-center gap-2 rounded-md border bg-background px-4 text-sm font-medium hover:bg-accent">{uploading ? <LoaderCircle className="size-4 animate-spin" /> : <FileUp className="size-4" />}{uploading ? "Uploading…" : "Choose and upload PDF resume"}</span></label>
          <p className="mt-3 text-xs text-muted-foreground">{resume ? `${resume.filename}${resume.created_at ? ` · Processed ${new Date(resume.created_at).toLocaleDateString()}` : " · Processed just now"}` : "No resume uploaded yet."}</p>
        </CardContent></Card>
        <Card><CardHeader><CardTitle>Extracted skills</CardTitle></CardHeader><CardContent className="flex flex-wrap gap-2">{skills.length ? skills.map(skill => <Badge key={skill} variant="secondary">{skill}</Badge>) : <p className="text-sm text-muted-foreground">Upload a PDF resume to extract skills.</p>}</CardContent></Card>
      </div>
    </div>
  </>;
}

function Field({ label, value, onChange, disabled, placeholder }: { label: string; value: string; onChange: (value: string) => void; disabled?: boolean; placeholder?: string }) {
  return <label className="flex flex-col gap-2 text-sm font-medium">{label}<Input value={value} onChange={event => onChange(event.target.value)} disabled={disabled} placeholder={placeholder} /></label>;
}
