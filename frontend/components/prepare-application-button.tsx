import Link from "next/link";
import { ArrowUpRight, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";

export function PrepareApplicationButton({ jobId, fullWidth = false }: { jobId: string; fullWidth?: boolean }) {
  return <Button asChild className={fullWidth ? "w-full" : undefined} size={fullWidth ? "default" : "sm"}>
    <Link href={`/applications/prepare/${jobId}`}>
      {fullWidth ? <Sparkles data-icon="inline-start" /> : null}Prepare application{!fullWidth ? <ArrowUpRight data-icon="inline-end" /> : null}
    </Link>
  </Button>;
}
