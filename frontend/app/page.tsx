"use client";

import { Bot } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

export default function EntryPage() {
  const router = useRouter();

  useEffect(() => {
    const destination = window.sessionStorage.getItem("jobflow_token")
      ? "/dashboard"
      : "/auth/sign-up";
    router.replace(destination);
  }, [router]);

  return <main className="flex min-h-screen items-center justify-center bg-background">
    <div className="flex items-center gap-3 font-display text-lg font-bold" role="status" aria-label="Opening JobFlow AI">
      <span className="flex size-10 items-center justify-center rounded-lg bg-primary text-primary-foreground"><Bot className="size-5" /></span>
      JobFlow AI
    </div>
  </main>;
}
