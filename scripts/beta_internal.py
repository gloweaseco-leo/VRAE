"""Single TEST_ONLY entry; no production, share or administrative runtime endpoint."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from integration.beta_review.codex3.runner import main  # noqa: E402

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "app":
        from integration.beta_review.codex3.local_app import main as app_main
        raise SystemExit(app_main(sys.argv[2:]))
    main()
