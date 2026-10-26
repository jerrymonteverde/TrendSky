"use client";
import { ArrowRight, Search } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { exploreUrl, MAX_QUERY_LENGTH, normalizeQuery } from "@/lib/search";
import { Button } from "./ui/button";
import { useHydrated } from "@/lib/use-hydrated";

export function SearchForm({ initialQuery = "", compact = false, suggestions = [] }: { initialQuery?: string; compact?: boolean; suggestions?: string[] }) {
  const [query, setQuery] = useState(initialQuery);
  const [error, setError] = useState("");
  const router = useRouter();
  const hydrated = useHydrated();
  return <div className={`search-unit ${compact ? "compact" : ""}`}>
    <form className="search-form" action="/explore" role="search" onSubmit={(event) => {
      event.preventDefault();
      if (!normalizeQuery(query)) { setError("Enter a topic, keyword or hashtag to explore."); return; }
      setError(""); router.push(exploreUrl(query));
    }}>
      <div className="search-box"><Search aria-hidden="true" className="search-icon" /><label htmlFor="topic-search" className="sr-only">Explore a topic, keyword or hashtag</label>
        <input id="topic-search" name="q" value={query} disabled={!hydrated} onChange={(event) => { setQuery(event.target.value); setError(""); }} maxLength={MAX_QUERY_LENGTH} placeholder="Explore a topic, keyword or hashtag..." autoComplete="off" aria-describedby={error ? "search-error" : "search-hint"} aria-invalid={Boolean(error)} />
        <Button type="submit" disabled={!hydrated} aria-label="Explore topic"><span>Explore</span><ArrowRight aria-hidden="true" /></Button>
      </div>
      {error ? <p id="search-error" role="alert" className="search-error">{error}</p> : <p id="search-hint" className="search-hint">Keywords, #hashtags or &ldquo;exact phrases&rdquo;</p>}
    </form>
    {suggestions.length > 0 && <div className="suggestion-row" role="group" aria-label="Suggested searches"><span className="suggestion-label">Try a search</span>{suggestions.map((suggestion) => <Link className="suggestion-chip" href={exploreUrl(suggestion)} key={suggestion}>{suggestion}</Link>)}</div>}
  </div>;
}
