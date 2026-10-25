"use client";
import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { Button } from "@/components/ui/button";
import { useHydrated } from "@/lib/use-hydrated";
export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const hydrated = useHydrated();
  return <Button variant="ghost" size="icon" disabled={!hydrated} aria-label="Toggle color theme" onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}>
    <Moon className="dark:hidden" aria-hidden="true" /><Sun className="hidden dark:block" aria-hidden="true" />
  </Button>;
}
