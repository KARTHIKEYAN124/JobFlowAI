import type { Metadata } from "next";
import "./globals.css";
import { AppShell } from "@/components/app-shell";

export const metadata: Metadata = { title: "JobFlow AI", description: "AI-powered job intelligence and application automation" };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) { return <html lang="en"><body><AppShell>{children}</AppShell></body></html>; }
