"""Shim exposing ``src.benchmarks.ensemble_benchmark`` at ``src.ensemble_benchmark``."""

from src.benchmarks.ensemble_benchmark import *  # noqa: F401, F403
from src.benchmarks.ensemble_benchmark import main

if __name__ == "__main__":
    raise SystemExit(main())
