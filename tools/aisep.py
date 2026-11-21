"""AISEP metamodel prototype CLI (implements CONTRACT.md / spec "AISEP 第二步：元模型规范（草案）").

Usage (run with $PY = main checkout .venv/bin/python, see AGENTS.md):
  aisep.py build    [model files...]   -> build/graph.nq (sources + generated direct triples + derived aisep:notation and
                                          arch:approvalState, one graph per arch:Model); L3/L4/query/impact see the same
                                          (prints [Warning] build lines for ignored/ambiguous approval records)
  aisep.py check    [model files...]   -> L0 parse, L1 closed world, L2 ArchiMate relationship tables; exit 1 on Violation
  aisep.py validate [model files...]   -> L3 SHACL per module scope (spec §10.2); exit 1 on Violation
  aisep.py findings [model files...]   -> L4 ModelQuestions (trace gaps, refines to deprecated nodes, isolated elements); never fails
  aisep.py gate     [model files...]   -> L0..L4 atomically (check + validate + findings), one combined summary; exit 1 on
                                          any Violation in any layer. THE command CI and pre-commit run (G10)
  aisep.py query  FILE.rq|'SPARQL' [model files...]   -> over build graph + all ontologies + all alignments
  aisep.py impact <element IRI or prefixed name> [--mode depends|ripple] [--depth N] [--allow-invalid] [model files...]
                                          (spec §9; runs L1+L2 first and refuses an invalid model unless --allow-invalid)
  aisep.py test [--no-pytest]          -> every modules/*/tests fixture + tests/acceptance/*.py + aisep-mcp/tests (pytest);
                                          exit 1 on failure. --no-pytest skips aisep-mcp/tests (CI runs it in its own job)
Default model files = models/**/*.ttl. Problem lines start with [Violation], [Warning] or [Info].

Engines: pyoxigraph for everything (parse, store, SPARQL, L1/L2/L4, build, impact); pyshacl only for L3.
"""
import glob, os, subprocess, sys, tempfile, time
from xml.etree import ElementTree

import pyoxigraph as ox

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)  # the aisep/ library package; this file has the same name, so the repo root must come first
from aisep.core import (AISEP, ARCH, Ctx, dependencies, discover, expand, impact, l3, l4, rel,  # noqa: E402
                        run_check, short, shown)
from aisep import gitio  # noqa: E402
from aisep.errors import AisepError  # noqa: E402


# ------------------------------------------------------------------ commands

def model_files(args):
    """(files, read) for Ctx. Explicit arguments are parsed as given. Default: the workspace file set of §3.3 (tracked
    + untracked-not-ignored .ttl under models/, the same rule as the MCP server), read without following symlinks;
    outside a Git checkout (e.g. an exported tarball) every models/**/*.ttl."""
    if args:
        return [os.path.abspath(a) for a in args], None
    rc, top, _ = gitio.git(ROOT, "rev-parse", "--show-toplevel")
    if rc != 0 or os.path.realpath(top.strip()) != os.path.realpath(ROOT):
        return sorted(glob.glob(os.path.join(ROOT, "models", "**", "*.ttl"), recursive=True)), None
    return [os.path.join(ROOT, f) for f in gitio.model_files(ROOT)], lambda f: gitio.read_file(ROOT, rel(f))


def report(ctx, layers):
    rows = shown(ctx.problems, layers)
    for sev, layer, text in rows:
        print(f"[{sev}] {layer} {text}")
    n = lambda s: sum(1 for p in rows if p[0] == s)
    return n("Violation"), n("Warning"), n("Info")


def cmd_check(files, read=None):
    t = time.time()
    ctx = Ctx(discover(), files, read=read)
    if any(p[1] == "L0" for p in ctx.problems):
        v, w, i = report(ctx, ("L0",))
    else:
        run_check(ctx)
        v, w, i = report(ctx, ("L0", "L1", "L2"))
    print(f"SUMMARY check files={len(files)} violations={v} warnings={w} infos={i} seconds={time.time() - t:.2f}")
    return 1 if v else 0


def cmd_validate(files, read=None):
    t = time.time()
    ctx = Ctx(discover(), files, read=read)
    if not any(p[1] == "L0" for p in ctx.problems):
        l3(ctx)
    v, w, i = report(ctx, ("L0", "L3"))
    print(f"SUMMARY validate files={len(files)} violations={v} warnings={w} infos={i} seconds={time.time() - t:.2f}")
    return 1 if v else 0


def cmd_gate(files, read=None):
    """G10: the one CI / pre-commit entry point — L0..L4 atomically on one context (check + validate + findings),
    one combined summary, exit 1 if any layer reports a Violation."""
    t = time.time()
    ctx = Ctx(discover(), files, read=read)
    if not any(p[1] == "L0" for p in ctx.problems):
        run_check(ctx)
        l3(ctx)
        l4(ctx)
    layers = ("L0", "build", "L1", "L2", "L3", "L4")
    v, w, i = report(ctx, layers)
    per = " ".join(f"{l}={sum(1 for p in set(ctx.problems) if p[1] == l and p[0] == 'Violation')}" for l in layers)
    print(f"SUMMARY gate files={len(files)} violations={v} warnings={w} infos={i} violations_by_layer[{per}] "
          f"result={'FAIL' if v else 'PASS'} seconds={time.time() - t:.2f}")
    return 1 if v else 0


def cmd_build(files, read=None):
    ctx = Ctx(discover(), files, read=read)
    v, _, _ = report(ctx, ("L0", "build"))  # build Warnings: ignored/ambiguous approval records (R3)
    out = os.path.join(ROOT, "build", "graph.nq")
    quads = ctx.write_build(out)
    graphs = {q.graph_name.value for q in quads if isinstance(q.graph_name, ox.NamedNode)}
    kinds = {AISEP + "notation": "notation", ARCH + "approvalState": "approval"}
    n = lambda k: sum(1 for _, p, _, _ in ctx.built if kinds.get(p.value, "direct") == k)
    print(f"SUMMARY build files={len(ctx.src_quads)} source_triples={sum(map(len, ctx.src_quads.values()))} "
          f"direct_triples={n('direct')} notation_triples={n('notation')} approval_state_triples={n('approval')} "
          f"model_graphs={len(graphs)} -> {rel(out)}")
    return 1 if v else 0


def cmd_findings(files, read=None):
    ctx = Ctx(discover(), files, read=read)
    l4(ctx)
    v, w, i = report(ctx, ("L0", "L4"))
    print(f"SUMMARY findings warnings={w} infos={i}")
    return 0


def cmd_query(q, files, read=None):
    if os.path.isfile(q):
        q = open(q, encoding="utf-8").read()
    ctx = Ctx(discover(), files, read=read)
    report(ctx, ("L0",))
    res = ctx.store.query(q, prefixes=ctx.prefixes, use_default_graph_as_union=True)
    if isinstance(res, ox.QueryBoolean) or isinstance(res, bool):
        print(bool(res)); return 0
    if isinstance(res, ox.QueryTriples):
        for tr in res:
            print(f"{short(tr.subject)}\t{short(tr.predicate)}\t{short(tr.object)}")
        return 0
    names = [v.value for v in res.variables]
    print("\t".join(names))
    n = 0
    for sol in res:
        n += 1
        print("\t".join("" if sol[v] is None else short(sol[v]) for v in names))
    print(f"-- rows={n}", file=sys.stderr)
    return 0


def cmd_impact(args):
    depth, mode = 3, "depends"
    allow_invalid = "--allow-invalid" in args
    args = [a for a in args if a != "--allow-invalid"]
    if "--depth" in args:
        i = args.index("--depth")
        depth = int(args[i + 1]); args = args[:i] + args[i + 2:]
    if "--mode" in args:
        i = args.index("--mode")
        mode = args[i + 1]; args = args[:i] + args[i + 2:]
    if not args or mode not in ("depends", "ripple"):
        sys.exit("usage: aisep.py impact <element> [--mode depends|ripple] [--depth N] [--allow-invalid] [model files...]")
    files, read = model_files(args[1:])
    ctx = Ctx(discover(), files, read=read)
    if not any(p[1] == "L0" for p in ctx.problems):
        run_check(ctx)  # G9: impact over an L1/L2-invalid model is refused unless --allow-invalid
    v = sum(1 for p in set(ctx.problems) if p[0] == "Violation")
    if v:
        for sev, layer, text in sorted({p for p in ctx.problems if p[0] == "Violation"}, key=lambda p: (p[1], p[2])):
            print(f"[{sev}] {layer} {text}", file=sys.stderr)
        if not allow_invalid:
            print(f"[Violation] impact refused: the model has {v} L0/L1/L2 violation(s) (above); fix the violations or "
                  f"pass --allow-invalid to compute impact on an invalid model", file=sys.stderr)
            return 1
        print("=" * 78 + f"\n[Warning] IMPACT ON AN INVALID MODEL (--allow-invalid): {v} L0/L1/L2 violation(s); the result "
              "below may be wrong\n" + "=" * 78, file=sys.stderr)
    start = expand(ctx, args[0])
    unknown = not ctx.types(start)
    if unknown:  # exit 1, not 0: "no impact" and "no such element" must not look alike (mcp-interface.md §3.1, F4)
        print(f"[Warning] {short(start)} is not an element of the loaded models", file=sys.stderr)
    rows = impact(ctx, start, depth, mode)
    print("element\tlabel\ttype\tdepth\tpath")
    for d, x, p, note in rows:
        print(f"{short(x)}\t{ctx.label(x)}\t{'+'.join(short(t) for t in ctx.types(x))}\t{d}{note}\t{p}")
    print(f"-- impact ({mode}) of {short(start)} ({ctx.label(start)}): {len(rows)} element(s), depth<={depth}", file=sys.stderr)
    return 1 if unknown else 0


def run_fixture(mods, fixture):
    """Returns (ok, detail) for one test fixture."""
    head = open(fixture, encoding="utf-8").read().splitlines()[:5]
    expect = next((l.split("# expect:", 1)[1].strip() for l in head[:1] if l.startswith("# expect:")), None)
    warn = [l.split(":", 1)[1].strip() for l in head if l.startswith("# expect-warning:")]
    no_warn = [l.split(":", 1)[1].strip() for l in head if l.startswith("# expect-no-warning:")]
    uses = [l.split("# uses:", 1)[1].strip() for l in head if l.startswith("# uses:")]
    files = [fixture] + [f for u in uses for f in sorted(glob.glob(os.path.join(ROOT, u, "**", "*.ttl"), recursive=True))]
    invalid = os.path.basename(os.path.dirname(fixture)) == "invalid"
    if invalid and not expect:
        return False, "invalid fixture lacks a first line '# expect: <substring>'"
    ctx = Ctx(mods, files)
    viol = lambda: [t for s, _, t in ctx.problems if s == "Violation"]
    if not viol():
        run_check(ctx)
    if not viol() or (invalid and not any(expect in v for v in viol())):
        if not any(p[1] == "L0" for p in ctx.problems):
            l3(ctx)
    v = viol()
    if not invalid:
        if not v:
            l4(ctx)  # L4 only adds Warnings/Infos, so expect-warning can name an L4 finding (e.g. R4)
        if v:
            return False, f"{len(v)} violation(s): {v[0][:160]}"
        w = [t for s, _, t in ctx.problems if s == "Warning"]
        miss = [x for x in warn if not any(x in t for t in w)] + [x for x in no_warn if any(x in t for t in w)]
        return not miss, (f"warning expectation failed for: {miss[0]!r}" if miss else
                          "; ".join(t[:100] for t in w if any(x in t for x in warn)))
    hit = [x for x in v if expect in x]
    return bool(hit), (hit[0][:160] if hit else f"expected '{expect}', got: {(v or ['no violation'])[0][:140]}")


def run_pytest(tests_dir):
    """aisep-mcp/tests (pytest, docs/mcp-interface.md §11): one result row per test case, from the JUnit XML report."""
    if not os.path.isdir(tests_dir):
        return []
    with tempfile.TemporaryDirectory() as tmp:
        xml = os.path.join(tmp, "junit.xml")
        try:  # the merge-check negatives take most of the time; CI's `negatives` job prints their real timing
            p = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", f"--junitxml={xml}",
                                tests_dir], cwd=ROOT, capture_output=True, text=True, timeout=7200)
        except subprocess.TimeoutExpired:
            return [("pytest", os.path.relpath(tests_dir, ROOT), "pytest", False, "timed out after 7200 s")]
        cases = ElementTree.parse(xml).getroot().iter("testcase") if os.path.isfile(xml) else []
        rows = []
        for c in cases:
            bad = c.find("failure") if c.find("failure") is not None else c.find("error")
            detail = (bad.get("message") or "").splitlines()[0][:160] if bad is not None else ""
            skip = c.find("skipped")  # xfail and skip: not a failure, but say so instead of a bare PASS
            if bad is None and skip is not None:
                detail = f"{skip.get('type', 'skipped')}: {(skip.get('message') or '').splitlines()[0][:140] if skip.get('message') else ''}"
            rows.append(("pytest", c.get("name"), "pytest", bad is None, detail))
    if not rows or p.returncode not in (0, 1):  # collection error, usage error, pytest missing
        tail = (p.stdout + p.stderr).strip().splitlines()
        rows.append(("pytest", os.path.relpath(tests_dir, ROOT), "pytest", False, tail[-1][:160] if tail else f"exit {p.returncode}"))
    return rows


def cmd_test(no_pytest=False):
    mods = discover()
    results = []
    t0 = time.time()
    names = {m.name for m in mods}
    for m in mods:
        for kind in ("valid", "invalid"):
            for fx in sorted(glob.glob(os.path.join(m.dir, "tests", kind, "*.ttl"))):
                head = open(fx, encoding="utf-8").read().splitlines()[:5]
                uses_all = any(l.startswith("# uses:") for l in head)
                # '# modules: a b' adds those modules (and their dependencies) to the fixture's environment
                extra = [n for l in head if l.startswith("# modules:") for n in l.split(":", 1)[1].split()]
                if set(extra) - names:
                    results.append((m.name, os.path.basename(fx), kind, False, f"unknown module(s) {sorted(set(extra) - names)}"))
                    continue
                want = {d.name for n in [m.name] + extra for d in dependencies(mods, n)}
                ok, detail = run_fixture(mods if uses_all else [d for d in mods if d.name in want], fx)
                results.append((m.name, os.path.basename(fx), kind, ok, detail))
    for py in sorted(glob.glob(os.path.join(ROOT, "tests", "acceptance", "*.py"))):
        p = subprocess.run([sys.executable, py], cwd=ROOT, capture_output=True, text=True, timeout=900)
        tail = (p.stdout + p.stderr).strip().splitlines()
        results.append(("acceptance", os.path.basename(py), "script", p.returncode == 0, tail[-1][:160] if tail else ""))
    if not no_pytest:
        results += run_pytest(os.path.join(ROOT, "aisep-mcp", "tests"))
    w = max([len(r[0]) for r in results] + [6]), max([len(r[1]) for r in results] + [7])
    print(f"{'module':<{w[0]}}  {'fixture':<{w[1]}}  kind     result  detail")
    for mod, fx, kind, ok, detail in results:
        print(f"{mod:<{w[0]}}  {fx:<{w[1]}}  {kind:<7}  {'PASS' if ok else 'FAIL':<6}  {detail}")
    failed = sum(1 for r in results if not r[3])
    print(f"SUMMARY test total={len(results)} passed={len(results) - failed} failed={failed} seconds={time.time() - t0:.1f}")
    return 1 if failed else 0


def main(argv):
    if not argv or argv[0] not in ("build", "check", "validate", "findings", "gate", "query", "impact", "test"):
        print(__doc__); return 2
    cmd, args = argv[0], argv[1:]
    if cmd == "test":
        if args not in ([], ["--no-pytest"]):
            print(__doc__); return 2
        return cmd_test(no_pytest=bool(args))
    if cmd == "impact":
        return cmd_impact(args)
    if cmd == "query":
        if not args:
            print(__doc__); return 2
        return cmd_query(args[0], *model_files(args[1:]))
    return {"build": cmd_build, "check": cmd_check, "validate": cmd_validate, "findings": cmd_findings,
            "gate": cmd_gate}[cmd](*model_files(args))


if __name__ == "__main__":
    try:
        code = main(sys.argv[1:])
    except AisepError as e:
        sys.exit(e.message)
    sys.exit(code)
