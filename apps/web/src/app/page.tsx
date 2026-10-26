import Image from "next/image";
import Link from "next/link";
import { ArrowRight, ChartNoAxesCombined, GitCompareArrows, Search } from "lucide-react";
import { SearchForm } from "@/components/search-form";
import { CollectionStatus } from "@/components/collection-notice";
import { TrendingResults } from "@/components/trending-results";
import { CollectionRefresh } from "@/components/collection-refresh";
import { getIngestionStatus } from "@/lib/api";
import { getTrends } from "@/lib/trends";

export const dynamic = "force-dynamic";
const suggestions = ["#bluesky", "#tech", "climate change", "art", "gaming", "mexico"];
const pathways = [
  { icon: Search, eyebrow: "START WITH A QUESTION", title: "Explore conversations", copy: "Follow a topic through the conversations around it.", href: "/explore" },
  { icon: GitCompareArrows, eyebrow: "FIND THE CONTEXT", title: "Compare topics", copy: "See where different conversations meet and diverge.", href: "/explore#comparison" },
  { icon: ChartNoAxesCombined, eyebrow: "LOOK A LITTLE FURTHER", title: "Find what's next", copy: "Explore momentum and carefully evaluated predictions.", href: "/predictions" },
];
export default async function Home() {
  const [data, trends] = await Promise.all([getIngestionStatus(), getTrends("popular", 5, "all", 3)]);
  return <>
    <section className="hero" aria-labelledby="hero-title">
      <div className="hero-copy">
        <div className="eyebrow hero-eyebrow"><span className="eyebrow-rule" /> A NEW PERSPECTIVE ON CONVERSATION</div>
        <h1 id="hero-title">Discover what’s <span>rising.</span></h1>
        <p className="hero-subtitle">Explore real conversations on Bluesky, compare trends, and discover what might happen next.</p>
        <SearchForm suggestions={suggestions} />
        <p className="hero-footnote"><span className="footnote-star" aria-hidden="true">✳</span> Big conversations. Clearer signals. Powered by Bluesky.</p>
      </div>
      <figure className="hero-art">
        <Image src="/images/hero/city-sunset-study-terrace.webp" alt="A group of people sharing conversations and following activity together above a city at sunset." fill preload sizes="(max-width: 700px) 100vw, (max-width: 1100px) 54vw, 56vw" className="hero-image" />
        <div className="hero-art-shade" aria-hidden="true" />
        <figcaption className="hero-art-caption"><span className="caption-spark" aria-hidden="true">✳</span> A little perspective on what’s next</figcaption>
      </figure>
    </section>
    <CollectionRefresh />
    <div className="shell home-collection"><CollectionStatus data={data} /></div>
    <section className="trending-section shell" aria-labelledby="trending-title">
      <div className="section-heading"><div><div className="eyebrow">THE CONVERSATION, IN FOCUS</div><h2 id="trending-title">Trending Right Now</h2></div><Link className="text-link" href="/trending">View all trends <ArrowRight size={16} aria-hidden="true" /></Link></div>
      <div className="trend-shelf"><TrendingResults data={trends} /></div>
    </section>
    <section className="pathways-section shell" aria-labelledby="pathways-title">
      <div className="section-heading pathway-heading"><div><div className="eyebrow">FROM CURIOSITY TO CONTEXT</div><h2 id="pathways-title">Every conversation has a bigger picture.</h2></div><p>Begin anywhere. Find your perspective.</p></div>
      <div className="pathways-grid">{pathways.map(({ icon: Icon, eyebrow, title, copy, href }, index) => <Link href={href} className="pathway" key={title}><span className="pathway-number">0{index + 1}</span><Icon size={24} strokeWidth={1.6} aria-hidden="true" /><span className="pathway-eyebrow">{eyebrow}</span><h3>{title}</h3><p>{copy}</p><span className="pathway-link">Take a look <ArrowRight size={15} aria-hidden="true" /></span></Link>)}</div>
      <div className="home-disclaimer"><span aria-hidden="true">✳</span><p>TrendSky measures public conversation activity on Bluesky. Coverage begins when collection starts.</p><Link href="/about#coverage">How we measure <ArrowRight size={14} aria-hidden="true" /></Link></div>
    </section>
  </>;
}
