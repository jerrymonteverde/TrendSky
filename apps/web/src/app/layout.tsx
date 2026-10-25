import type { Metadata } from "next";
import localFont from "next/font/local";
import Link from "next/link";
import { Header } from "@/components/header";
import { ThemeProvider } from "@/components/theme-provider";
import "./globals.css";

const ubuntu = localFont({
  src: [
    { path: "../fonts/ubuntu-latin-400-normal.woff2", weight: "400", style: "normal" },
    { path: "../fonts/ubuntu-latin-500-normal.woff2", weight: "500", style: "normal" },
  ], variable: "--font-ubuntu", display: "swap", fallback: ["Arial", "sans-serif"],
});
export const metadata: Metadata = {
  title: { default: "TrendSky — Discover what's rising.", template: "%s | TrendSky" },
  description: "Explore public Bluesky conversations. Transparent social intelligence, built around observed activity and honest coverage.",
};
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en" data-scroll-behavior="smooth" suppressHydrationWarning><body className={ubuntu.variable}>
    <ThemeProvider><a className="skip-link" href="#main">Skip to content</a><Header />
      <main id="main">{children}</main>
      <footer className="site-footer"><div className="shell footer-inner"><p><span className="footer-brand">TrendSky</span><span className="footer-tagline">A little perspective on what’s next.</span></p><div><span>Built around public Bluesky conversations.</span><Link href="/about#coverage">Data & transparency <span aria-hidden="true">↗</span></Link></div></div></footer>
    </ThemeProvider>
  </body></html>;
}
