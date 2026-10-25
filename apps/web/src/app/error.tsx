"use client";
import { Button } from "@/components/ui/button";
export default function ErrorPage({ reset }: { reset: () => void }) { return <div className="shell interior"><h1>Something interrupted the view.</h1><p className="page-intro">Please try loading this page again.</p><Button onClick={reset}>Try again</Button></div>; }
