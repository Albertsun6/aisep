"""Run a module of this repo, like `python -m <module> [args]`, without letting a file in the repo root or the current
directory stand in for a standard-library or installed module (a root `pyoxigraph.py` used to turn mergecheck green).

  python tools/pyrun.py aisep.mergecheck --pr-head H ...

`python -m` puts the current directory first on sys.path; here the script's own directory, the current directory and
the repo root are taken out and the repo root goes back last, so only names nothing else provides (the aisep package)
come from the checkout."""
import os, runpy, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_unsafe = {os.path.realpath(p) for p in (ROOT, os.path.dirname(os.path.abspath(__file__)), os.getcwd())}
sys.path[:] = [p for p in sys.path if os.path.realpath(p or ".") not in _unsafe] + [ROOT]

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    runpy.run_module(sys.argv.pop(1), run_name="__main__", alter_sys=True)
