"""Backward-compatibility shim for src.ingest_multisource -> src.data.ingest_multisource."""
from src.data.ingest_multisource import *  # noqa: F401, F403
if __name__ == "__main__":
    from src.data.ingest_multisource import main
    main()
