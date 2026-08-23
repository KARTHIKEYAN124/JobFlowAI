"use client";
import * as React from "react";
import * as ProgressPrimitive from "@radix-ui/react-progress";
import { cn } from "@/lib/utils";
export function Progress({ value = 0, className, ...props }: React.ComponentProps<typeof ProgressPrimitive.Root>) { const current = value ?? 0; return <ProgressPrimitive.Root value={current} className={cn("relative h-2 w-full overflow-hidden rounded-full bg-secondary", className)} {...props}><ProgressPrimitive.Indicator className="h-full w-full bg-primary transition-transform" style={{ transform: `translateX(-${100 - current}%)` }} /></ProgressPrimitive.Root>; }
