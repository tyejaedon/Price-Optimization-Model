import argparse
import re
from functools import lru_cache
from typing import Iterable, List, Set

try:
    import nltk
    from nltk.corpus import stopwords
    from nltk.stem import WordNetLemmatizer
except ImportError as exc:
    raise RuntimeError("nltk is required for src.nlp_pipeline. Install dependencies from requirements.txt") from exc

URL_PATTERN = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
NON_ALPHA_PATTERN = re.compile(r"[^a-z\s]")
FALLBACK_STOPWORDS = {
    "a",
    "an",
    "the",
    "and",
    "or",
    "but",
    "if",
    "to",
    "of",
    "in",
    "on",
    "for",
    "with",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "by",
    "as",
    "at",
    "from",
}


@lru_cache(maxsize=1)
def _stopwords_set() -> Set[str]:
    try:
        return set(stopwords.words("english"))
    except LookupError:
        nltk.download("stopwords", quiet=True)
        try:
            return set(stopwords.words("english"))
        except LookupError:
            return set(FALLBACK_STOPWORDS)


@lru_cache(maxsize=1)
def _lemmatizer() -> WordNetLemmatizer:
    try:
        nltk.data.find("corpora/wordnet")
    except LookupError:
        nltk.download("wordnet", quiet=True)
    return WordNetLemmatizer()


def _clean_text(raw_text: str) -> str:
    text = (raw_text or "").lower()
    text = URL_PATTERN.sub(" ", text)
    text = NON_ALPHA_PATTERN.sub(" ", text)
    return " ".join(text.split())


def sanitize_text(raw_text: str) -> str:
    """Normalize text for downstream NLP by cleaning and lemmatizing tokens."""
    cleaned = _clean_text(raw_text)
    if not cleaned:
        return ""

    stop_words = _stopwords_set()
    lemma = _lemmatizer()

    tokens: List[str] = []
    for token in cleaned.split():
        if len(token) <= 2:
            continue
        if token in stop_words:
            continue
        try:
            normalized = lemma.lemmatize(token)
        except LookupError:
            normalized = token
        if normalized and len(normalized) > 2 and normalized not in stop_words:
            tokens.append(normalized)

    return " ".join(tokens)


def sanitize_many(texts: Iterable[str]) -> List[str]:
    return [sanitize_text(text) for text in texts]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sanitize a text string for NLP preprocessing.")
    parser.add_argument("--text", default="", help="Raw text to sanitize")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    print(sanitize_text(args.text))


if __name__ == "__main__":
    main()

