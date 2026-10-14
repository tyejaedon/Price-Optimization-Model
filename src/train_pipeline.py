"""Backward-compatibility shim for src.train_pipeline -> src.training.train_pipeline."""
from src.training.train_pipeline import *  # noqa: F401, F403
if __name__ == "__main__":
    from src.training.train_pipeline import main
    main()
