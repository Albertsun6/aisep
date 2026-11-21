"""vendor/MANIFEST.json（规范 §11）：生成与核对。

  <venv python> tools/vendor_manifest.py check      核对，不一致退出 1（tests/acceptance/test_vendor_manifest.py 调用它）
  <venv python> tools/vendor_manifest.py generate   重写 MANIFEST.json；只在按 §11 升级上游、或按 ADR-018 删除文件的那次变更里用

清单逐个记录 vendor/ 下的文件（MANIFEST.json 自身除外）：SHA256、来源 URL、抓取时间、许可证及其出处、owl:versionInfo，
以及是否被加载、被谁加载。核对四件事：文件集合与清单一致、每个文件的 SHA256 一致、清单与 meta.linked.archi/SHA256SUMS
一致、"被加载"与加载代码一致（模块清单的 aisep:loads / aisep:shapesFile，加上 aisep/core.py 写死的 RT_FILE）。
"""
import hashlib, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 本文件所在的 tools/ 里有个 aisep.py，会顶替 aisep 包；去掉脚本目录，仓库根放在最后（不让根目录的同名 .py 顶替依赖）。
sys.path.pop(0)
sys.path.append(ROOT)
from aisep import core  # noqa: E402

VENDOR = os.path.join(ROOT, "vendor")
MANIFEST = os.path.join(VENDOR, "MANIFEST.json")
UP = "meta.linked.archi"  # vendor/ 下唯一的上游目录
RECORDS = ("FETCHED_AT", "REMOVED.txt", "SHA256SUMS", "fetch.log", "urls.txt")  # 抓取记录，AISEP 自己写的，不来自上游
CC = "http://creativecommons.org/ns#license"
DCT = "http://purl.org/dc/terms/license"
VERSION = core.NS["owl"] + "versionInfo"
ONTOLOGY = core.NS["owl"] + "Ontology"


def sha256(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def vendor_files():
    out = []
    for d, _, names in os.walk(VENDOR):
        out += [os.path.relpath(os.path.join(d, n), VENDOR).replace(os.sep, "/") for n in names]
    return sorted(p for p in out if p != "MANIFEST.json")


def loaded_by():
    """vendor 相对路径 -> 加载它的位置（与 aisep.core 的加载代码同源）。"""
    out = {}
    for m in core.discover(ROOT):
        src = core.rel(os.path.join(m.dir, "metamodel.ttl"), ROOT)
        for f in m.loads + m.shapes:
            r = os.path.relpath(f, VENDOR).replace(os.sep, "/")
            if not r.startswith(".."):
                out.setdefault(r, set()).add(src)
    out.setdefault(os.path.relpath(core.RT_FILE, VENDOR).replace(os.sep, "/"), set()).add("aisep/core.py (RT_FILE)")
    return {k: sorted(v) for k, v in out.items()}


def sha256sums():
    with open(os.path.join(VENDOR, UP, "SHA256SUMS"), encoding="utf-8") as f:
        return {f"{UP}/{p.strip()}": h for h, p in (line.split(None, 1) for line in f if line.strip())}


def check():
    problems = []
    try:
        with open(MANIFEST, encoding="utf-8") as f:
            entries = {e["path"]: e for e in json.load(f)["files"]}
    except (OSError, ValueError, KeyError, TypeError) as e:
        return [f"cannot read vendor/MANIFEST.json: {e}"]
    files = vendor_files()
    problems += [f"not in MANIFEST.json: vendor/{p}" for p in sorted(set(files) - set(entries))]
    problems += [f"in MANIFEST.json but missing: vendor/{p}" for p in sorted(set(entries) - set(files))]
    for p in sorted(set(files) & set(entries)):
        if sha256(os.path.join(VENDOR, p)) != entries[p].get("sha256"):
            problems.append(f"sha256 differs from MANIFEST.json: vendor/{p}")
    for p, h in sorted(sha256sums().items()):
        if p in entries and entries[p].get("sha256") != h:
            problems.append(f"MANIFEST.json and {UP}/SHA256SUMS disagree: vendor/{p}")
    used = loaded_by()
    problems += [f"loaded but not in vendor/: vendor/{p}" for p in sorted(set(used) - set(entries))]
    for p, e in sorted(entries.items()):
        if e.get("loadedBy", []) != used.get(p, []) or e.get("loaded") != (p in used):
            problems.append(f"loaded/loadedBy in MANIFEST.json differ from the loading code ({used.get(p, [])}): vendor/{p}")
    return problems


# ------------------------------------------------------------------ generate（只在上游变更时跑）

def file_url(name, urls):
    """ttl/<名>.ttl <- https://meta.linked.archi/<路径>：路径里的 / 换成 _（fetch.log、urls.txt 的抓取口径）。"""
    hits = [u for u in urls if u.removeprefix(f"https://{UP}/").replace("/", "_") + ".ttl" == name]
    if len(hits) != 1:
        raise SystemExit(f"cannot map ttl/{name} to exactly one URL in urls.txt: {hits}")
    return hits[0]


def describe(path):
    """许可证（先看文件自身，再看 catalog 按数据集的声明，ADR-018）与 owl:versionInfo。"""
    quads = list(core.ox.parse(path=path, format=core.TTL))
    onto = {q.subject.value for q in quads if q.predicate.value == core.A and q.object.value == ONTOLOGY}
    pick = lambda pred: sorted({q.object.value for q in quads if q.predicate.value == pred and q.subject.value in onto})
    lic = pick(CC) + [x for x in pick(DCT) if x not in pick(CC)]
    return lic, pick(VERSION)


def generate():
    up = os.path.join(VENDOR, UP)
    urls = open(os.path.join(up, "urls.txt"), encoding="utf-8").read().split()
    fetched = open(os.path.join(up, "FETCHED_AT"), encoding="utf-8").read().strip()
    cat = list(core.ox.parse(path=os.path.join(up, "ttl", "catalog.ttl"), format=core.TTL))
    catalog = {}
    for q in cat:
        if q.predicate.value == DCT:
            catalog.setdefault(q.subject.value, set()).add(q.object.value)
    sums, used, out = sha256sums(), loaded_by(), []
    for p in vendor_files():
        full = os.path.join(VENDOR, p)
        e = {"path": p, "sha256": sha256(full)}
        if p.startswith(f"{UP}/ttl/") and p.endswith(".ttl"):
            url = file_url(p.rsplit("/", 1)[1], urls)
            lic, ver = describe(full)
            src = "file"
            if not lic and catalog.get(url):
                lic, src = sorted(catalog[url]), f"{UP}/ttl/catalog.ttl"
            e |= {"source": "upstream", "url": url, "fetchedAt": fetched, "license": lic,
                  "licenseDeclaredIn": src if lic else None, "versionInfo": ver}
            if sums.get(p) != e["sha256"]:
                raise SystemExit(f"vendor/{p} does not match {UP}/SHA256SUMS")
        elif p in (f"{UP}/{r}" for r in RECORDS):
            e |= {"source": "fetch-record", "url": None, "fetchedAt": None, "license": None,
                  "licenseDeclaredIn": None, "versionInfo": []}
        else:
            raise SystemExit(f"unknown kind of vendor file: vendor/{p}")
        e |= {"loaded": p in used, "loadedBy": used.get(p, [])}
        out.append(e)
    doc = {"about": "规范 §11 的 vendor 清单，由 tools/vendor_manifest.py generate 生成、check 核对；不要手改。"
                    "source=upstream 的文件原样来自上游（fetch.log、urls.txt），fetch-record 是 AISEP 记的抓取记录。"
                    "license 为空表示文件自身与 catalog.ttl 都没有声明；许可口径见 NOTICE。",
           "files": out}
    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"wrote vendor/MANIFEST.json: {len(out)} files, {sum(e['loaded'] for e in out)} loaded")


if __name__ == "__main__":
    if sys.argv[1:] == ["generate"]:
        generate()
    elif sys.argv[1:] == ["check"]:
        ps = check()
        for p in ps:
            print(f"[Violation] {p}")
        print(f"SUMMARY vendor-manifest problems={len(ps)} result={'FAIL' if ps else 'PASS'}")
        sys.exit(1 if ps else 0)
    else:
        sys.exit(__doc__)
