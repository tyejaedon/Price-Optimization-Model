import argparse
import json
import os
import re
import time
from functools import lru_cache
from typing import Iterable, List, Sequence, Set, Tuple

try:
    import joblib
    import nltk
    import numpy as np
    from nltk.corpus import stopwords
    from nltk.stem import WordNetLemmatizer
    from sklearn.decomposition import TruncatedSVD
    from sklearn.feature_extraction.text import TfidfVectorizer
except ImportError as exc:
    raise RuntimeError("Missing NLP dependencies. Install from requirements.txt") from exc

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

DEFAULT_ARTIFACT_DIR = os.path.join("artifacts")
DEFAULT_TFIDF_ARTIFACT = "tfidf_vectorizer.joblib"
DEFAULT_SVD_ARTIFACT = "svd_reducer.joblib"
DEFAULT_METADATA_ARTIFACT = "nlp_reducer_metadata.json"


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


class TextFeatureReducer:
    """TF-IDF + TruncatedSVD feature pipeline for marketplace profile text."""

    def __init__(
        self,
        n_components: int = 50,
        max_features: int = 12000,
        ngram_range: Tuple[int, int] = (1, 2),
        random_state: int = 42,
    ) -> None:
        self.n_components_requested = int(n_components)
        self.max_features = int(max_features)
        self.ngram_range = ngram_range
        self.random_state = random_state

        self.vectorizer = TfidfVectorizer(
            max_features=self.max_features,
            ngram_range=self.ngram_range,
            min_df=1,
            norm="l2",
            sublinear_tf=True,
        )
        self.reducer = TruncatedSVD(n_components=max(1, self.n_components_requested), random_state=self.random_state)
        self.fitted = False

    def _effective_components(self, n_features: int) -> int:
        if n_features <= 1:
            return 1
        return max(1, min(self.n_components_requested, n_features - 1))

    def fit_transform(self, texts: Sequence[str]) -> np.ndarray:
        cleaned_texts = sanitize_many(texts)
        tfidf_sparse = self.vectorizer.fit_transform(cleaned_texts)

        effective_components = self._effective_components(tfidf_sparse.shape[1])
        self.reducer = TruncatedSVD(n_components=effective_components, random_state=self.random_state)
        dense_vectors = self.reducer.fit_transform(tfidf_sparse)
        self.fitted = True
        return dense_vectors

    def transform(self, texts: Sequence[str]) -> np.ndarray:
        if not self.fitted:
            raise RuntimeError("TextFeatureReducer must be fitted before transform().")

        cleaned_texts = sanitize_many(texts)
        tfidf_sparse = self.vectorizer.transform(cleaned_texts)
        return self.reducer.transform(tfidf_sparse)

    def explained_variance_sum(self) -> float:
        if not self.fitted:
            return 0.0
        values = getattr(self.reducer, "explained_variance_ratio_", None)
        if values is None:
            return 0.0
        finite_values = np.nan_to_num(values, nan=0.0, posinf=0.0, neginf=0.0)
        return float(np.sum(finite_values))

    def save_artifacts(self, artifact_dir: str = DEFAULT_ARTIFACT_DIR) -> None:
        if not self.fitted:
            raise RuntimeError("TextFeatureReducer must be fitted before save_artifacts().")

        os.makedirs(artifact_dir, exist_ok=True)
        tfidf_path = os.path.join(artifact_dir, DEFAULT_TFIDF_ARTIFACT)
        svd_path = os.path.join(artifact_dir, DEFAULT_SVD_ARTIFACT)
        metadata_path = os.path.join(artifact_dir, DEFAULT_METADATA_ARTIFACT)

        joblib.dump(self.vectorizer, tfidf_path)
        joblib.dump(self.reducer, svd_path)

        metadata = {
            "n_components_requested": self.n_components_requested,
            "n_components_fitted": int(self.reducer.n_components),
            "max_features": self.max_features,
            "ngram_range": [self.ngram_range[0], self.ngram_range[1]],
            "explained_variance_sum": self.explained_variance_sum(),
        }
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, sort_keys=True)

    @classmethod
    def load_artifacts(cls, artifact_dir: str = DEFAULT_ARTIFACT_DIR) -> "TextFeatureReducer":
        tfidf_path = os.path.join(artifact_dir, DEFAULT_TFIDF_ARTIFACT)
        svd_path = os.path.join(artifact_dir, DEFAULT_SVD_ARTIFACT)

        vectorizer = joblib.load(tfidf_path)
        reducer = joblib.load(svd_path)
        loaded_ngram = getattr(vectorizer, "ngram_range", (1, 2))
        if not isinstance(loaded_ngram, tuple) or len(loaded_ngram) != 2:
            loaded_ngram = (1, 2)

        instance = cls(
            n_components=int(getattr(reducer, "n_components", 50)),
            max_features=int(getattr(vectorizer, "max_features", 12000) or 12000),
            ngram_range=(int(loaded_ngram[0]), int(loaded_ngram[1])),
        )
        instance.vectorizer = vectorizer
        instance.reducer = reducer
        instance.fitted = True
        return instance


def _profile_transform_latency_ms(reducer: TextFeatureReducer, sample_text: str, iterations: int = 50) -> float:
    start = time.perf_counter()
    for _ in range(max(1, iterations)):
        reducer.transform([sample_text])
    elapsed = time.perf_counter() - start
    return (elapsed / max(1, iterations)) * 1000.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="NLP sanitization and TF-IDF/SVD feature tooling.")
    parser.add_argument(
        "--mode",
        choices=("sanitize", "fit_demo"),
        default="sanitize",
        help="sanitize single text (M2.1) or run fit/transform artifact demo (M2.2).",
    )
    parser.add_argument("--text", default="", help="Raw text input used for sanitize mode or demo sample")
    parser.add_argument("--artifact-dir", default=DEFAULT_ARTIFACT_DIR, help="Directory for saved NLP artifacts")
    parser.add_argument("--n-components", type=int, default=50, help="SVD output dimensions")
    parser.add_argument("--max-features", type=int, default=12000, help="TF-IDF vocabulary cap")
    parser.add_argument("--preview-limit", type=int, default=3, help="Preview rows for demo output")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.mode == "sanitize":
        print(sanitize_text(args.text))
        return

    sample_texts = [
        "Senior data scientist building machine learning models for churn prediction.",
        "Full stack engineer building APIs and frontend dashboards for SaaS analytics.",
        "Cloud DevOps specialist using Kubernetes, Docker, and Terraform on AWS.",
        "Digital marketer running Google Ads, SEO audits, and campaign optimization.",
        "UX designer creating Figma prototypes and user journey improvements.",
    ]
    if args.text:
        sample_texts.append(args.text)

    reducer = TextFeatureReducer(n_components=args.n_components, max_features=args.max_features)
    dense_vectors = reducer.fit_transform(sample_texts)
    reducer.save_artifacts(args.artifact_dir)

    restored = TextFeatureReducer.load_artifacts(args.artifact_dir)
    sample_query = args.text or sample_texts[0]
    query_vector = restored.transform([sample_query])
    avg_ms = _profile_transform_latency_ms(restored, sample_query, iterations=30)

    preview_limit = max(1, min(args.preview_limit, dense_vectors.shape[0]))
    payload = {
        "fit_rows": int(dense_vectors.shape[0]),
        "fit_dimensions": int(dense_vectors.shape[1]),
        "explained_variance_sum": round(reducer.explained_variance_sum(), 6),
        "query_vector_shape": [int(query_vector.shape[0]), int(query_vector.shape[1])],
        "avg_transform_latency_ms": round(avg_ms, 4),
        "artifact_dir": args.artifact_dir,
        "sanitized_preview": sanitize_many(sample_texts[:preview_limit]),
    }
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
