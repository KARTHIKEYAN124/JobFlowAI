"use client";
import { useState } from "react";
import { PageHeading } from "@/components/page-heading";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
const settings=["High-match email alerts","Daily job digest","Follow-up reminders","Interview preparation"];
export default function SettingsPage(){const [enabled,setEnabled]=useState<Record<string,boolean>>(Object.fromEntries(settings.map(x=>[x,true])));return <><PageHeading title="Settings" description="Notifications, privacy, security, and integration preferences."/><Card><CardHeader><CardTitle>Notifications</CardTitle><CardDescription>Choose when JobFlow should get your attention.</CardDescription></CardHeader><CardContent>{settings.map(item=><div key={item} className="flex items-center justify-between border-b py-4 last:border-b-0"><div><p className="text-sm font-semibold">{item}</p><p className="mt-1 text-xs text-muted-foreground">Sent only for your profile and approved channels.</p></div><Button variant={enabled[item]?"default":"outline"} size="sm" onClick={()=>setEnabled(value=>({...value,[item]:!value[item]}))}>{enabled[item]?"Enabled":"Disabled"}</Button></div>)}</CardContent></Card><Card className="mt-6"><CardHeader><CardTitle>Security</CardTitle><CardDescription>JWT sessions, role-based access, webhook signing, rate limits, and encrypted provider credentials are enforced by the backend.</CardDescription></CardHeader></Card></>}

