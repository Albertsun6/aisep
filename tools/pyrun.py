"""Run a module of this repo, like `python -m <module> [args]`, without putting the checkout on sys.path:

  python tools/pyrun.py aisep.mergecheck --pr-head H ...

`python -m` puts the current directory first on sys.path, and any directory of the checkout on sys.path, first or last,
lets a file there answer an import nothing else satisfies: a root `pyoxigraph.py` shadowed the real one, and a root
`msvcrt.py` is picked up by the standard library's own `try: import msvcrt` on Linux and macOS. So this script takes
its own directory, the current directory and the repo root off sys.path, and a finder at the front of sys.meta_path
resolves the single top-level name `aisep` to the repo's aisep/ package; every other import ignores the checkout.
tools/aisep.py imports this module for the same effect."""
import importlib.machinery, os, runpy, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_unsafe = {os.path.realpath(p) for p in (ROOT, os.path.dirname(os.path.abspath(__file__)), os.getcwd())}
sys.path[:] = [p for p in sys.path if os.path.realpath(p or ".") not in _unsafe]


class _AisepFinder:
    @staticmethod
    def find_spec(name, path=None, target=None):
        return importlib.machinery.PathFinder.find_spec(name, [ROOT]) if name == "aisep" else None


sys.meta_path.insert(0, _AisepFinder)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    runpy.run_module(sys.argv.pop(1), run_name="__main__", alter_sys=True)
