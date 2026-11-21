"""vendor/MANIFEST.json 与 vendor/ 一致（规范 §11）；检查本身会因篡改而失败（在临时副本里证伪）。

Run:  <venv python> tests/acceptance/test_vendor_manifest.py      (also run by `aisep.py test`, CI job fixtures)
"""
import os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TOOL = os.path.join("tools", "vendor_manifest.py")


def check(root):
    p = subprocess.run([sys.executable, os.path.join(root, TOOL), "check"], cwd=root, capture_output=True, text=True,
                       timeout=300)
    return p.returncode, p.stdout + p.stderr


def copy():
    d = tempfile.mkdtemp(prefix="aisep-vendor-")
    for sub in ("aisep", "modules", "tools", "vendor"):
        shutil.copytree(os.path.join(ROOT, sub), os.path.join(d, sub))
    return d


failures = []
rc, out = check(ROOT)
print(out.strip())
if rc != 0:
    failures.append("repository: check failed")

for name, tamper, want in [
    ("append to a loaded file", lambda d: open(os.path.join(d, "vendor/meta.linked.archi/ttl/core.ttl"), "a").write("#\n"),
     "sha256 differs from MANIFEST.json: vendor/meta.linked.archi/ttl/core.ttl"),
    ("add a file", lambda d: open(os.path.join(d, "vendor/meta.linked.archi/ttl/extra.ttl"), "w").write(""),
     "not in MANIFEST.json: vendor/meta.linked.archi/ttl/extra.ttl"),
]:
    d = copy()
    try:
        tamper(d)
        rc, out = check(d)
    finally:
        shutil.rmtree(d, ignore_errors=True)
    ok = rc == 1 and want in out
    print(f"[{'CONFIRMED' if ok else 'REFUTED'}] tampered copy fails the check: {name}")
    if not ok:
        failures.append(f"{name}: rc={rc} {out.strip()[-300:]}")

print(f"SUMMARY vendor-manifest acceptance failures={len(failures)} result={'FAIL' if failures else 'PASS'}")
sys.exit(1 if failures else 0)
