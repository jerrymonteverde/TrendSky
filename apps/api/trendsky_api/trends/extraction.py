"""Conservative multilingual extraction; no stemming, inferred language or semantic merging."""

import hashlib
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass

URL = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
TOKEN = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)?", re.UNICODE)
TAG = re.compile(r"(?<!\w)#([\w]{1,128})", re.UNICODE)
REPEATED = re.compile(r"(.)\1{4}")
STOPWORDS = {
    "en": set(
        """a an and are as at be been being but by can could did do does doing for from had has
have he her here hers him his how i if in into is it its just like me more most my no
nor not of on once one only or our ours out over own same she should so some than
that the their theirs them then there these they this those through to too under up
us very was we were what when where which while who why will with would you your
yours also get got now about after again all am any because before both each few
further having off other such until during don dont im ive its youre really much many
even still know think want going say said people post rt via http https www com""".split()
    ),
    "es": set(
        """a al algo algunas algunos ante antes aquel aquella aqui aquí así aun aunque bajo bien
cada casi como cómo con contra cual cuál cuando cuándo de del desde donde dónde dos
el él ella ellas ellos en entre era eran es esa esas ese eso esos esta está estaba
estamos están estar estas este esto estos fue fueron ha había han hasta hay he hemos
hoy la las le les lo los mas más me mi mis muy ni no nos nosotros nuestra nuestras
nuestro nuestros o otra otras otro otros para pero poco por porque qué que quien
quién se sea ser si sí sin sobre son su sus también tanto te tiene todo todos tras tu
tú tus un una unas uno unos usted ustedes ya yo e y también sólo solo estoy ahora
hacer hace gracias soy eres vamos ver vez nunca siempre nada día dias días pues aquí
ahí os eso""".split()
    ),
}


def normalize(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold().strip()


@dataclass(frozen=True)
class ExtractedTopic:
    id: str
    kind: str
    normalized: str
    label: str


def topic(kind: str, value: str) -> ExtractedTopic:
    normalized = normalize(value)
    identifier = hashlib.sha256(f"{kind}:{normalized}".encode()).hexdigest()
    return ExtractedTopic(
        identifier, kind, normalized, f"#{normalized}" if kind == "hashtag" else normalized
    )


def primary_language(languages: list[str] | None) -> str:
    if not languages:
        return "unknown"
    if not isinstance(languages[0], str):
        return "unknown"
    first = languages[0].lower().split("-")[0]
    return first if first in {"en", "es"} else "other"


def extract_topics(
    text: str | None,
    languages: list[str] | None,
    explicit_tags: list[str],
    *,
    phrases: list[str],
    min_length: int = 3,
    max_keywords: int = 12,
) -> tuple[str, list[ExtractedTopic]]:
    language = primary_language(languages)
    clean = normalize(text if isinstance(text, str) else "")[:10000]
    tags = {normalize(tag).removeprefix("#") for tag in explicit_tags if isinstance(tag, str)}
    tags.update(match.group(1) for match in TAG.finditer(clean))
    tags = {tag for tag in tags if 1 <= len(tag) <= 128 and re.fullmatch(r"\w+", tag)}
    found = {value.id: value for value in (topic("hashtag", tag) for tag in sorted(tags)[:32])}
    # Unknown/other declared languages retain hashtags only; never silently assume English.
    if language not in STOPWORDS:
        return language, list(found.values())
    urls = len(URL.findall(clean))
    clean = TAG.sub(" ", URL.sub(" ", clean))
    tokens = TOKEN.findall(clean)[:500]
    counts = Counter(tokens)
    if urls > 3 or (len(tokens) >= 10 and max(counts.values(), default=0) / len(tokens) > 0.6):
        return language, list(found.values())
    eligible = sorted(
        {
            token
            for token in tokens
            if min_length <= len(token) <= 40
            and token not in STOPWORDS[language]
            and not REPEATED.search(token)
        }
    )
    # Stable first-appearance order avoids an alphabetical selection bias at the bounded cap.
    eligible.sort(key=lambda token: tokens.index(token))
    for value in eligible[:max_keywords]:
        extracted = topic("keyword", value)
        found[extracted.id] = extracted
    for phrase in sorted({normalize(phrase) for phrase in phrases}):
        parts = TOKEN.findall(phrase)
        pattern = r"(?<!\w)" + r"\s+".join(re.escape(part) for part in parts) + r"(?!\w)"
        if 2 <= len(parts) <= 4 and len(phrase) <= 128 and re.search(pattern, clean):
            extracted = topic("phrase", " ".join(parts))
            found[extracted.id] = extracted
    return language, list(found.values())
