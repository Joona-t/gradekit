"""Enable `python3 -m gradekit analyze ...` (zero-install, run from the repo root)."""
import sys

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
