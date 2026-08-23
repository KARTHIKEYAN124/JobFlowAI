"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { ArrowRight, Bot } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { api, TokenResponse } from "@/lib/api";

export function AuthForm({ mode }: { mode: "sign-in" | "sign-up" }) {
  const signUp = mode === "sign-up"; const router = useRouter(); const [error,setError]=useState(""); const [pending,setPending]=useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); setPending(true); setError(""); const values=new FormData(event.currentTarget); try { const token=await api<TokenResponse>(signUp?"/auth/register":"/auth/login",{method:"POST",body:JSON.stringify({email:values.get("email"),password:values.get("password"),...(signUp?{full_name:values.get("full_name")}:{})})}); sessionStorage.setItem("jobflow_token",token.access_token); router.push(signUp?"/profile":"/"); } catch (reason) { setError(reason instanceof Error?reason.message:"Could not continue"); } finally { setPending(false); } }
  return <div className="flex min-h-screen items-center justify-center bg-background p-4"><div className="w-full max-w-md"><Link href="/" className="mb-8 flex items-center justify-center gap-2 font-display text-lg font-bold"><span className="flex size-9 items-center justify-center rounded-lg bg-primary text-primary-foreground"><Bot className="size-5"/></span>JobFlow AI</Link><Card><CardHeader><CardTitle className="text-2xl">{signUp?"Create your account":"Welcome back"}</CardTitle><CardDescription>{signUp?"Start with one profile, then let your workflows do the searching.":"Continue to your job intelligence workspace."}</CardDescription></CardHeader><CardContent><form onSubmit={submit}><FieldGroup>{signUp?<Field><FieldLabel htmlFor="full_name">Full name</FieldLabel><Input id="full_name" name="full_name" autoComplete="name" required/></Field>:null}<Field><FieldLabel htmlFor="email">Email</FieldLabel><Input id="email" name="email" type="email" autoComplete="email" required/></Field><Field><FieldLabel htmlFor="password">Password</FieldLabel><Input id="password" name="password" type="password" minLength={10} autoComplete={signUp?"new-password":"current-password"} required/><FieldDescription>At least 10 characters.</FieldDescription></Field>{error?<p role="alert" className="text-sm text-destructive">{error}</p>:null}<Button disabled={pending} type="submit" className="w-full">{pending?"Please wait…":signUp?"Create account":"Sign in"}<ArrowRight data-icon="inline-end"/></Button></FieldGroup></form><p className="mt-6 text-center text-sm text-muted-foreground">{signUp?"Already registered?":"New to JobFlow?"} <Link className="font-semibold text-primary hover:underline" href={signUp?"/auth/sign-in":"/auth/sign-up"}>{signUp?"Sign in":"Create an account"}</Link></p></CardContent></Card></div></div>;
}

