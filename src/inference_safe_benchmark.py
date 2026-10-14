"""Backward-compatibility shim for src.inference_safe_benchmark -> src.benchmarks.inference_safe_benchmark."""
from src.benchmarks.inference_safe_benchmark import *  # noqa: F401, F403
if __name__ == "__main__":
    from src.benchmarks.inference_safe_benchmark import main
    main()
