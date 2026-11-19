"""Check every DDD relationship's (source ⊑ am4, target ⊑ am4) pair against the ArchiMate 4.0
relationship tables for its am4 parent relationship; report direct vs derived-only.
Run: <venv python> modules/ddd/tests/check_am4_matrix.py   (exit 1 if any pair is not permitted)"""
import sys
from pathlib import Path
import pyoxigraph as ox

R = Path(__file__).resolve().parents[3]
V = R / "vendor/meta.linked.archi/ttl"
M = R / "modules/ddd"

# DDD QR class -> (source DDD classes, target DDD classes), per spec §6.4
PAIRS = {
    "UpstreamDownstream": (["BoundedContext"], ["BoundedContext"]),
    "CustomerSupplier": (["BoundedContext"], ["BoundedContext"]),
    "Partnership": (["BoundedContext"], ["BoundedContext"]),
    "SharedKernel": (["BoundedContext"], ["BoundedContext"]),
    "Ownership": (["BoundedContext"], ["Aggregate"]),
    "Containment": (["Aggregate"], ["Entity", "ValueObject"]),
    "RootContainment": (["Aggregate"], ["Entity"]),
    "SubdomainImplementation": (["BoundedContext"], ["Subdomain"]),
    "EventTriggering": (["DomainService", "Policy"], ["DomainEvent", "Command"]),
}

store = ox.Store()
for f in ["core.ttl", "archimate4_onto.ttl", "archimate4_relationship-tables.ttl"]:
    store.bulk_load(path=str(V / f), format=ox.RdfFormat.TURTLE)
for f in ["onto.ttl", "align.ttl"]:
    store.bulk_load(path=str(M / f), format=ox.RdfFormat.TURTLE)

PFX = """PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX arch: <https://meta.linked.archi/core#>
PREFIX am4: <https://meta.linked.archi/archimate4/onto#>
PREFIX am4rt: <https://meta.linked.archi/archimate4/relationship-tables#>
PREFIX ddd: <https://aisep.example/ont/ddd#>
"""

def one(q):
    rows = list(store.query(PFX + q))
    return rows

def am4_parent_rel(qr):
    # nearest am4 QR superclass, its unqualified property, and the permission annotations for it
    rows = one(f"""SELECT ?c ?p ?perm ?direct WHERE {{
        ddd:{qr} rdfs:subClassOf+ ?c . FILTER(STRSTARTS(STR(?c), STR(am4:)))
        ?c arch:unqualifiedForm ?p . ?p am4rt:permittedBy ?perm ; am4rt:permittedDirectlyBy ?direct .
        FILTER NOT EXISTS {{ ddd:{qr} rdfs:subClassOf+ ?c2 . ?c2 rdfs:subClassOf+ ?c .
                             FILTER(STRSTARTS(STR(?c2), STR(am4:))) }} }}""")
    assert len(rows) == 1, (qr, rows)
    return rows[0]

def am4_class(ddd_cls):
    rows = one(f"""SELECT ?c WHERE {{ ddd:{ddd_cls} rdfs:subClassOf ?c . FILTER(STRSTARTS(STR(?c), STR(am4:))) }}""")
    assert len(rows) == 1, (ddd_cls, rows)
    return rows[0]["c"]

def permits(s, ann, t):
    # the table may list t itself or a superclass of t (e.g. arch:ModelConcept for association)
    return bool(store.query(PFX + f"ASK {{ {s} {ann} ?x . {t} rdfs:subClassOf* ?x }}"))

ok = True
for qr, (srcs, tgts) in PAIRS.items():
    r = am4_parent_rel(qr)
    for s in srcs:
        for t in tgts:
            S, T = am4_class(s), am4_class(t)
            anyp, direct = permits(S, r["perm"], T), permits(S, r["direct"], T)
            verdict = "DIRECT" if direct else ("DERIVED-ONLY" if anyp else "NOT PERMITTED")
            ok &= anyp
            short = lambda n: str(n.value).split("#")[-1]
            print(f"{qr:24} {s}->{t}: am4:{short(r['c'])} {short(S)}->{short(T)} via {short(r['p'])}: {verdict}")
sys.exit(0 if ok else 1)
