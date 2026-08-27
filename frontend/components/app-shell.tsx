"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { BarChart3, Bell, Bot, BriefcaseBusiness, CircleUserRound, FileStack, Gauge, LogOut, Menu, Search, Settings, Sparkles, Target, Workflow, X } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, clearSession, hasUsableSession } from "@/lib/api";
import { cn } from "@/lib/utils";

const nav = [
  ["Dashboard", "/dashboard", Gauge], ["Jobs", "/jobs", BriefcaseBusiness], ["Matches", "/matches", Target],
  ["Applications", "/applications", FileStack], ["Skills", "/skills", Sparkles], ["Analytics", "/analytics", BarChart3],
  ["Automations", "/automations", Workflow], ["Profile", "/profile", CircleUserRound], ["Settings", "/settings", Settings],
] as const;

type Candidate = { full_name: string; headline: string };
type AutomationSummary = { workflows: { status: string; last_run: string | null }[] };

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [authorizedPath, setAuthorizedPath] = useState("");
  const [candidate, setCandidate] = useState<Candidate>({ full_name: "Candidate", headline: "Complete your profile" });
  const [automation, setAutomation] = useState<AutomationSummary | null>(null);

  const publicPage = pathname === "/" || pathname === "/portal-launch" || pathname.startsWith("/auth/");

  useEffect(() => {
    if (publicPage) {
      return;
    }
    if (!hasUsableSession()) {
      router.replace("/auth/sign-in");
      return;
    }
    setAuthorizedPath(pathname);
  }, [pathname, publicPage, router]);

  useEffect(() => {
    function update(event: Event) {
      const profile = (event as CustomEvent<Candidate>).detail;
      setCandidate({ full_name: profile.full_name || "Candidate", headline: profile.headline || "Complete your profile" });
    }
    if (hasUsableSession()) {
      void api<Candidate>("/profile").then(profile => update(new CustomEvent("profile", { detail: profile }))).catch(() => undefined);
      void api<AutomationSummary>("/automations").then(setAutomation).catch(() => undefined);
    }
    window.addEventListener("jobflow-profile-updated", update);
    return () => window.removeEventListener("jobflow-profile-updated", update);
  }, [pathname]);

  if (publicPage) return children;
  if (authorizedPath !== pathname) return <div className="flex min-h-screen items-center justify-center text-sm text-muted-foreground" role="status">Checking your session…</div>;
  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const query = search.trim();
    router.push(query ? `/jobs?q=${encodeURIComponent(query)}` : "/jobs");
  }
  function signOut() {
    clearSession();
    router.replace("/auth/sign-in");
  }
  const initials = candidate.full_name.split(/\s+/).filter(Boolean).slice(0, 2).map(part => part[0]).join("").toUpperCase() || "C";
  const successful = automation?.workflows.filter(item => ["SUCCESS", "COMPLETED"].includes(item.status)).length ?? 0;
  const latestRun = automation?.workflows.map(item => item.last_run).filter((value): value is string => Boolean(value)).sort().at(-1);
  return <div className="min-h-screen bg-background">
    <aside className={cn("fixed inset-y-0 left-0 z-40 flex w-64 flex-col bg-sidebar text-sidebar-foreground transition-transform lg:translate-x-0", open ? "translate-x-0" : "-translate-x-full")}>
      <div className="flex h-20 items-center gap-3 px-6"><div className="flex size-9 items-center justify-center rounded-lg bg-sidebar-primary text-sidebar-primary-foreground"><Bot className="size-5" /></div><span className="font-display text-lg font-bold tracking-tight">JobFlow AI</span><Button className="ml-auto lg:hidden" variant="ghost" size="icon" onClick={() => setOpen(false)} aria-label="Close navigation"><X /></Button></div>
      <nav className="flex flex-1 flex-col gap-1 px-3">{nav.map(([label, href, Icon]) => { const selected = pathname === href || pathname.startsWith(`${href}/`); return <Link key={href} href={href} onClick={() => setOpen(false)} className={cn("flex h-11 items-center gap-3 rounded-lg px-3 text-sm font-medium transition-colors", selected ? "bg-sidebar-accent text-sidebar-accent-foreground" : "text-sidebar-foreground/65 hover:bg-sidebar-accent/60 hover:text-sidebar-accent-foreground")}><Icon className="size-4" />{label}</Link>; })}</nav>
      <div className="m-4 rounded-xl border border-sidebar-border p-4"><div className="mb-2 flex items-center gap-2 text-xs font-semibold"><span className={`size-2 rounded-full ${successful ? "bg-emerald-400" : "bg-amber-400"}`} />{automation ? `${successful} workflows healthy` : "Workflow state unavailable"}</div><p className="text-xs leading-5 text-sidebar-foreground/55">{automation?.workflows.length ?? 0} workflows · {latestRun ? `Last run ${new Date(latestRun).toLocaleString()}` : "No run recorded"}</p></div>
    </aside>
    <div className="lg:pl-64">
      <header className="sticky top-0 z-30 flex h-20 items-center gap-4 border-b bg-background/95 px-4 backdrop-blur lg:px-8"><Button variant="ghost" size="icon" className="lg:hidden" onClick={() => setOpen(true)} aria-label="Open navigation"><Menu /></Button><form className="relative hidden max-w-md flex-1 md:block" role="search" onSubmit={submitSearch}><Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"/><Input className="pl-9" aria-label="Search jobs" placeholder="Search jobs, companies, skills…" value={search} onChange={event => setSearch(event.target.value)} /></form><div className="ml-auto flex items-center gap-2"><Button variant="ghost" size="icon" aria-label="Notifications"><Bell /></Button><div className="mx-2 hidden h-7 w-px bg-border sm:block"/><Avatar className="size-9"><AvatarFallback>{initials}</AvatarFallback></Avatar><div className="hidden sm:block"><p className="text-sm font-semibold">{candidate.full_name}</p><p className="text-xs text-muted-foreground">{candidate.headline}</p></div><Button variant="ghost" size="icon" onClick={signOut} aria-label="Sign out"><LogOut /></Button></div></header>
      <main className="mx-auto max-w-[1500px] p-4 lg:p-8">{children}</main>
    </div>
  </div>;
}
