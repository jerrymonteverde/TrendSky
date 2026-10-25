"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Menu, X } from "lucide-react";
import { useState } from "react";
import { ThemeToggle } from "./theme-toggle";
import { Button } from "./ui/button";
import { useHydrated } from "@/lib/use-hydrated";

export function Brand() {
  return <Link href="/" className="brand" aria-label="TrendSky home"><svg viewBox="0 0 32 32" fill="none" aria-hidden="true"><path d="M3 23 12 14l6 5L29 7" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"/><path d="M20 7h9v9" stroke="var(--brand-accent)" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"/></svg><span>Trend<span className="brand-sky">Sky</span></span></Link>;
}
const links = [["/explore", "Explore"], ["/trending", "Trending Now"], ["/predictions", "Predictions"], ["/about", "About"]];
export function Header() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const hydrated = useHydrated();
  return <header className="site-header"><div className="shell header-inner">
    <Brand />
    <nav id="mobile-navigation" aria-label="Main navigation" className={`main-nav ${open ? "is-open" : ""}`}>
      {links.map(([href, label]) => <Link key={href} href={href} aria-current={pathname === href ? "page" : undefined} onClick={() => setOpen(false)}>{label}</Link>)}
    </nav>
    <div className="header-actions"><ThemeToggle /><Button variant="ghost" size="icon" className="mobile-menu" disabled={!hydrated} aria-label={open ? "Close navigation" : "Open navigation"} aria-expanded={open} aria-controls="mobile-navigation" onClick={() => setOpen(!open)}>{open ? <X aria-hidden="true" /> : <Menu aria-hidden="true" />}</Button></div>
  </div></header>;
}
