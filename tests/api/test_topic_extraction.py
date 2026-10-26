from trendsky_api.trends.extraction import extract_topics, topic


def extracted(text, langs=None, tags=None):
    return extract_topics(text, langs, tags or [], phrases=["climate change", "cambio climático"])


def test_normalized_hashtags_are_unique_unicode_and_distinct_from_keywords():
    language, topics = extracted(
        "#Python #PYTHON #México #ｍéxico", ["en"], ["Python", "", "bad tag"]
    )
    assert language == "en"
    assert {(item.kind, item.normalized) for item in topics} == {
        ("hashtag", "python"),
        ("hashtag", "méxico"),
    }
    assert topic("hashtag", "PYTHON").id == topic("hashtag", "python").id
    assert topic("hashtag", "python").id != topic("keyword", "python").id


def test_spanish_and_english_stopwords_urls_and_phrase_boundaries():
    _, topics = extracted("The climate change is here https://example.com/advertisement", ["en"])
    values = {(item.kind, item.normalized) for item in topics}
    assert ("phrase", "climate change") in values
    assert ("keyword", "the") not in values
    assert not any("advertisement" in value for _, value in values)
    _, spanish = extracted("El cambio climático y la ciencia", ["es-MX"])
    assert topic("phrase", "cambio climático") in spanish
    assert topic("keyword", "ciencia") in spanish
    assert topic("keyword", "la") not in spanish
    assert topic("phrase", "climate change") not in extracted("climate. Change", ["en"])[1]


def test_unknown_language_and_explicit_facets_are_not_assumed_english():
    language, values = extracted("climate change", None, ["FacetTag"])
    assert language == "unknown"
    assert values == [topic("hashtag", "facettag")]
    assert extracted(None)[1] == []
    assert extracted(123)[1] == []


def test_repetitive_spam_does_not_generate_keywords():
    assert extracted("buy " * 20, ["en"])[1] == []
