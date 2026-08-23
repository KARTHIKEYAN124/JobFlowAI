import * as React from "react";
import { cn } from "@/lib/utils";
export function Input({ className, type, ...props }: React.ComponentProps<"input">) { return <input type={type} className={cn("flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm outline-none placeholder:text-muted-foreground focus-visible:ring-2 disabled:cursor-not-allowed disabled:opacity-50", className)} {...props} />; }

