"""AISEP metamodel checks (L0-L4, build, impact) — the one implementation behind the CLI (tools/aisep.py) and the MCP
server (docs/mcp-interface.md §3.1). Functions return data and raise AisepError; they never print or exit.

Engines: pyoxigraph for everything (parse, store, SPARQL, L1/L2/L4, build, impact); pyshacl only for L3.
"""
import glob, os, re, threading
from collections import OrderedDict, deque
from datetime import datetime, timezone

import pyoxigraph as ox

from aisep import querybox
from aisep.errors import AisepError

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENDOR = os.path.join(ROOT, "vendor", "meta.linked.archi", "ttl")
RT_FILE = os.path.join(VENDOR, "archimate4_relationship-tables.ttl")  # RDF 1.2: pyoxigraph only
HUB_MODULES = ("am4", "aisep-core")  # their shapes run on the hub data graph (spec §10.2)
TTL = ox.RdfFormat.TURTLE

NS = {
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#", "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "owl": "http://www.w3.org/2002/07/owl#", "xsd": "http://www.w3.org/2001/XMLSchema#",
    "skos": "http://www.w3.org/2004/02/skos/core#", "sh": "http://www.w3.org/ns/shacl#",
    "prov": "http://www.w3.org/ns/prov#", "schema": "https://schema.org/",
    "arch": "https://meta.linked.archi/core#", "am4": "https://meta.linked.archi/archimate4/onto#",
    "am4vp": "https://meta.linked.archi/archimate4/viewpoints#",
    "am4rt": "https://meta.linked.archi/archimate4/relationship-tables#",
    "bpmn": "https://meta.linked.archi/bpmn/onto#", "uml": "https://meta.linked.archi/uml/onto#",
    "ad": "https://meta.linked.archi/arch-decision#",
    "aisep": "https://aisep.example/ont/aisep#", "ddd": "https://aisep.example/ont/ddd#",
    "dcterms": "http://purl.org/dc/terms/",
}
MODEL_BASE = "https://aisep.example/model/"
SPARQL_PREFIXES = "".join(f"PREFIX {k}: <{v}>\n" for k, v in NS.items())
A, ARCH, AM4, AISEP, RT = NS["rdf"] + "type", NS["arch"], NS["am4"], NS["aisep"], NS["am4rt"]
JUNCTIONS = {AM4 + "AndJunction", AM4 + "OrJunction"}
LEVELS = {AISEP + "LevelCode": 0, AISEP + "LevelDesign": 1, AISEP + "LevelHub": 2}
LEVEL_NAME = {0: "code", 1: "design", 2: "hub"}
# spec §7.1: relationship classes that may connect different notations besides hub classes and arch:Refines
TRACE_CLASSES = {AISEP + "Verification", AISEP + "Implementation"}
DECISION_STATE = {AISEP + "DecisionApproved": ARCH + "Approved", AISEP + "DecisionRejected": AISEP + "Rejected"}
SRC_G, BUILT_G, ONTO_G = "urn:aisep:src:", "urn:aisep:built:", "urn:aisep:onto:"
APPROVAL_SHAPE = "https://aisep.example/ont/aisep-shapes#ApprovalRecordShape"
AGENTS = {ARCH + "Stakeholder", NS["prov"] + "Agent"}  # what prov:wasAssociatedWith may point to (incl. aisep:AIAgent)
# what aisep:approvedBy may point to: a person, never an AI (Q4=C, spec §6.2/§6.6; principle 5)
APPROVERS, NOT_APPROVERS = {ARCH + "Stakeholder"}, {AISEP + "AIAgent"}
# R1 "model files must not change the metamodel": metamodel annotations only a module file may declare
META_PREDICATES = {AISEP + "assertedShortcut", AISEP + "dependency", ARCH + "unqualifiedForm"}
SKOS = NS["skos"]
NAME_PREDICATES = {NS["rdfs"] + "label", NS["rdfs"] + "comment", SKOS + "prefLabel", SKOS + "altLabel", SKOS + "definition"}
INSTANCE_SCHEMA_OK = {NS["rdfs"] + "label", NS["rdfs"] + "comment", NS["rdfs"] + "seeAlso", NS["owl"] + "deprecated"}
SCHEMA_NS = (NS["rdfs"], NS["owl"], NS["sh"], NS["rdf"])
# R1/G6: a model class may not specialise these notation-neutral abstract roots (nor any arch:isAbstractClass class)
ABSTRACT_ROOTS = {ARCH + "Element", ARCH + "QualifiedRelationship", ARCH + "ModelConcept"}
# G5: core relationship classes judged like a notation's own relationships (same notation at both ends)
CORE_SAME_NOTATION = {ARCH + "Association", ARCH + "HasPart", ARCH + "DependsOn"}  # DependsOn: core 0.7.0
# xsd:dateTime lexical form (spec §6.6). The SAME regex is the sh:pattern of EG15 (ext-governance) so L3 agrees.
# G7 closed-world predicates: besides properties declared in a loaded module/vendored ontology graph, the only predicates
# a model file may use. rdfs:label/rdfs:comment are additions required by modules/aisep-core/tests/valid/
# r1-model-specialisation-ok.ttl (R1 names on a model class / instance). v0.4 (§4, §6.7): the three PROV-O predicates
# of aisep:AgentActivity (PROV-O is used as-is and not loaded, so they cannot be "declared"); no other prov: predicate.
PROPERTY_DECL = (NS["rdf"] + "Property", NS["owl"] + "ObjectProperty", NS["owl"] + "DatatypeProperty", NS["owl"] + "AnnotationProperty")
PREDICATE_ALLOW = {A, SKOS + "prefLabel", SKOS + "altLabel", SKOS + "definition", SKOS + "note",
                   NS["dcterms"] + "isReplacedBy", NS["owl"] + "deprecated", NS["rdfs"] + "subClassOf",
                   NS["prov"] + "generatedAtTime", NS["schema"] + "codeRepository",
                   NS["rdfs"] + "label", NS["rdfs"] + "comment",
                   NS["prov"] + "startedAtTime", NS["prov"] + "endedAtTime", NS["prov"] + "wasAssociatedWith"}
# G7: declared properties that may link two model members directly (everything else between members must be a
# qualified relationship). Trace properties per the GPT review, plus — added because the procurement model and valid
# fixtures need them — the notation-native structure properties of the vendored BPMN ontology, the core quality-measure
# link and the DDD context-map exposure. v0.4 (§4): aisep:activity (record -> activity) and prov:wasAssociatedWith
# (activity -> agent).
ELEMENT_LINK_OK = {AISEP + "approves", NS["ad"] + "relatedConcept", AISEP + "resultOf", NS["ddd"] + "payload",
                   AISEP + "approvedBy", ARCH + "inModel", ARCH + "inView", ARCH + "viewConformsToViewpoint",
                   ARCH + "source", ARCH + "target",  # the qualified relationship's own structure
                   NS["bpmn"] + "flowElements", NS["bpmn"] + "default", NS["bpmn"] + "flowNodeRefs",
                   NS["bpmn"] + "laneSets", NS["bpmn"] + "lanes", ARCH + "hasQualityMeasure", NS["ddd"] + "exposedAggregate",
                   AISEP + "activity", NS["prov"] + "wasAssociatedWith"}
XSD_DATETIME_RE = r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?(Z|[+-](0[0-9]|1[0-3]):[0-5][0-9]|[+-]14:00)?$"


def parse_xsd_datetime(lex):
    """The one xsd:dateTime parser (L1 ApprovalRecord checks and the approval-state derivation): a timezone-normalised
    (naive = UTC) datetime, or None for an ill-formed lexical form or an impossible instant (2026-02-30, 24:00)."""
    if not isinstance(lex, str) or not re.fullmatch(XSD_DATETIME_RE, lex):
        return None
    try:
        t = datetime.fromisoformat(lex.replace("Z", "+00:00"))
        return t.astimezone(timezone.utc) if t.tzinfo else t.replace(tzinfo=timezone.utc)
    except (ValueError, OverflowError):  # OverflowError: 0001-01-01T00:00:00+13:00 is before datetime.min in UTC
        return None


def _ox_term(t):
    """Inverse of querybox._term (None for an unbound variable)."""
    if t is None:
        return None
    if t["type"] == "iri":
        return ox.NamedNode(t["value"])
    if t["type"] == "bnode":
        return ox.BlankNode(t["value"])
    if "lang" in t:
        return ox.Literal(t["value"], language=t["lang"])
    return ox.Literal(t["value"], datatype=ox.NamedNode(t["datatype"]))


def short(v):
    s = v if isinstance(v, str) else getattr(v, "value", str(v))
    if s.startswith(MODEL_BASE) and "/" in s[len(MODEL_BASE):]:
        slug, local = s[len(MODEL_BASE):].split("/", 1)
        if local:  # a model IRI itself (".../<slug>/") stays a full IRI, like a bare namespace below
            return f"{slug}:{local}"
    for k, ns in NS.items():
        if s.startswith(ns) and len(s) > len(ns):
            return f"{k}:{s[len(ns):]}"
    return s


def _built_graph(m):
    """Graph of a derived triple: BUILT_G + the member's model; a model value that is not a valid IRI (a literal
    arch:inModel, reported by L3) goes to the 'none' graph instead of crashing the build."""
    try:
        return ox.NamedNode(BUILT_G + (m or "none"))
    except ValueError:
        return ox.NamedNode(BUILT_G + "none")


def rel(path, root=ROOT):
    return os.path.relpath(path, root)


# ------------------------------------------------------------------ modules

class Module:
    def __init__(self, name, mdir, iri, props, root=ROOT):
        self.name, self.dir, self.iri, self.root = name, mdir, iri, root
        one = lambda p: (props.get(p) or [None])[0]
        self.kind = (one(AISEP + "moduleKind") or "").replace(AISEP, "")
        self.version = one(NS["owl"] + "versionInfo")
        self.loads = sorted(self.path(p) for p in props.get(AISEP + "loads", []))
        self.shapes = sorted(self.path(p) for p in props.get(AISEP + "shapesFile", []))
        self.align = sorted(self.path(p) for p in props.get(AISEP + "alignmentFile", []))
        self.inherits = (one(AISEP + "inheritsHubRules") or "false") in ("true", "1")
        self.owns = props.get(AISEP + "ownsNamespace", [])
        self.level = LEVELS.get(one(AISEP + "notationLevel"))  # spec §7.2: 0 code < 1 design < 2 hub; None = no level
        # spec §5/§9: impact overrides take effect only when the manifest declares them (no file-name magic)
        self.impact = [f for f in sorted(self.path(p) for p in props.get(AISEP + "impactFile", [])) if f not in self.loads]

    def path(self, p):
        full = os.path.join(self.root if p.split("/")[0] in ("vendor", "modules", "models") else self.dir, p)
        if not os.path.isfile(full):
            raise AisepError("PARSE_FAILED", f"[Violation] module {self.name}: manifest references missing file {p}")
        return full

    @property
    def hub_alignment(self):  # spec §10.2: only hub-inheriting Languages put their alignment into the am4 data graph
        return self.inherits or self.kind in ("Extension", "Framework")


def discover(root=ROOT):
    mods = []
    for mf in sorted(glob.glob(os.path.join(root, "modules", "*", "metamodel.ttl"))):
        try:
            quads = list(ox.parse(path=mf, format=TTL))
        except SyntaxError as e:
            raise AisepError("PARSE_FAILED", f"[Violation] L0 cannot parse manifest {rel(mf, root)}: {e}",
                             details={"file": rel(mf, root), "error": str(e)[:200]})
        subjects = {q.subject.value for q in quads if q.predicate.value == A and q.object.value == ARCH + "Metamodel"}
        if len(subjects) != 1:
            raise AisepError("PARSE_FAILED", f"[Violation] {rel(mf, root)} must declare exactly one arch:Metamodel (found {len(subjects)})")
        iri = subjects.pop()
        props = {}
        for q in quads:
            if q.subject.value == iri:
                props.setdefault(q.predicate.value, []).append(q.object.value)
        mods.append(Module(os.path.basename(os.path.dirname(mf)), os.path.dirname(mf), iri, props, root))
    return mods


def dependencies(mods, name):
    """Hub modules + the module + modules whose files it references (transitively)."""
    by = {m.name: m for m in mods}
    want, todo = (set(HUB_MODULES) & set(by)) | {name}, [name]
    while todo:
        n = todo.pop()
        for f in by[n].loads + by[n].shapes + by[n].align + by[n].impact:
            r = rel(f, by[n].root).split(os.sep)
            if r[0] == "modules" and r[1] in by and r[1] not in want:
                want.add(r[1]); todo.append(r[1])
    return [m for m in mods if m.name in want]


def onto_files(mods, scope="all"):
    """Ontology files for a module set. scope='all': every load + every alignment (queries, L1, L2, L4).
    scope='hub': loads + alignments of hub-inheriting modules only (L3 am4/core data graph, spec §10.2).
    scope='none': loads only, no alignment (L3 per-notation runs add just their own alignment)."""
    all_align = {f for m in mods for f in m.align}
    files = [f for m in mods for f in m.loads + m.impact if f not in all_align]
    files += [f for m in mods for f in m.align if scope == "all" or (scope == "hub" and m.hub_alignment)]
    return list(dict.fromkeys(files))


def owner(mods, iri):
    """Module owning an IRI by longest aisep:ownsNamespace prefix."""
    best = None
    for m in mods:
        for ns in m.owns:
            if iri.startswith(ns) and (best is None or len(ns) > best[0]):
                best = (len(ns), m)
    return best[1] if best else None


# ------------------------------------------------------------------ context: sources + store + build

class Ctx:
    def __init__(self, mods, sources, root=None, read=None):
        """sources: model file paths. read: optional path -> bytes (gitio.read_file for workspace and snapshot files,
        which refuses symlinks and non-regular files); None parses the paths directly (explicit CLI arguments)."""
        self.mods, self.sources = mods, sources
        self.root = root or (mods[0].root if mods else ROOT)
        self.problems = []   # (severity, layer, text)
        self.instances = []  # (severity, layer, text, focus, rule, file): one per add(), structured (§7.3)
        self.src_quads = {}  # file -> [Quad in default graph]
        self.prefixes = dict(NS)
        for f in sources:  # L0
            try:
                parser = ox.parse(path=f, format=TTL) if read is None else ox.parse(read(f), format=TTL)
                qs = list(parser)
                self.prefixes.update({k: v for k, v in parser.prefixes.items() if k})
            except (SyntaxError, OSError) as e:
                msg = str(e)
                if read is not None and isinstance(e, SyntaxError):  # same text as a parse by path: "(file, line n)"
                    msg = re.sub(r"\(line (\d+)\)$", lambda mm: f"({os.path.basename(f)}, line {mm.group(1)})", msg)
                self.add("Violation", "L0", f"cannot parse {self.rel(f)}: {msg}", file=self.rel(f))
                continue
            if any(isinstance(q.object, ox.Triple) or isinstance(q.subject, ox.Triple) for q in qs):
                self.add("Violation", "L0", f"{self.rel(f)} uses an RDF 1.2 triple term <<( )>>, forbidden in AISEP models",
                         file=self.rel(f))
                qs = [q for q in qs if not isinstance(q.object, ox.Triple) and not isinstance(q.subject, ox.Triple)]
            self.src_quads[f] = qs
        self.store = ox.Store()
        for f in onto_files(mods, "all"):
            try:
                self.store.load(path=f, format=TTL, to_graph=ox.NamedNode(ONTO_G + self.rel(f)))
            except SyntaxError as e:  # a module file, not a model file: no partial result, a tool error like the manifest
                raise AisepError("PARSE_FAILED", f"[Violation] L0 cannot parse module file {self.rel(f)}: {str(e)[:200]}",
                                 hint="先修好这个文件", details={"file": self.rel(f), "error": str(e)[:200]}) from None
        for f, qs in self.src_quads.items():
            g = ox.NamedNode(SRC_G + self.rel(f))
            self.store.extend(ox.Quad(q.subject, q.predicate, q.object, g) for q in qs)
        self.supers = {}
        for c, d in self.rows("SELECT ?c ?d WHERE { ?c rdfs:subClassOf ?d FILTER(isIRI(?c) && isIRI(?d)) }"):
            self.supers.setdefault(c, set()).add(d)
        # R1: metamodel annotations count only when a module file declares them (a model file declaring one is an L1
        # Violation, and is not honoured either)
        self.uf = dict(self.rows(f"SELECT ?c ?u WHERE {{ GRAPH ?g {{ ?c arch:unqualifiedForm ?u }} {self.onto_graph_filter()} ?c a owl:Class }}"))
        self.approval_ambiguous = []  # (element, instant, [(record, decision)]) — R3c, reported by L1
        self.asserted = {}  # model member (written in a source, has arch:inModel) -> asserted rdf:types
        for x, t in self.rows(f"""SELECT DISTINCT ?x ?t WHERE {{ GRAPH ?g {{ ?x arch:inModel ?m }} {self.src_graph_filter()}
                                  ?x a ?t FILTER(isIRI(?t)) }}"""):
            self.asserted.setdefault(x, []).append(t)
        self.built = self.build_triples()
        self.store.extend(ox.Quad(s, p, o, _built_graph(m)) for s, p, o, m in self.built)

    def rel(self, path):
        return rel(path, self.root)

    def add(self, sev, layer, text, focus=None, rule=None, file=None):
        self.problems.append((sev, layer, text))
        self.instances.append((sev, layer, text, focus, rule, file))

    def rows(self, q, raw=False):
        res = self.store.query(SPARQL_PREFIXES + q, use_default_graph_as_union=True)
        return [[v if raw else (None if v is None else v.value) for v in r] for r in res]

    def ancestors(self, c):
        """c and its superclasses in BFS order (nearest first)."""
        seen, order, todo = {c}, [c], deque([c])
        while todo:
            for d in sorted(self.supers.get(todo.popleft(), ())):
                if d not in seen:
                    seen.add(d); order.append(d); todo.append(d)
        return order

    def nearest(self, c, table):
        for d in self.ancestors(c):
            if d in table:
                return table[d]
        return None

    def specific(self, x):
        """Most-specific asserted types of x (spec §4 D6: redundant asserted superclasses are dropped)."""
        ts = sorted(set(self.asserted.get(x, ())))
        return [t for t in ts if not any(u != t and t in self.ancestors(u) for u in ts)]

    def module_of(self, x):
        """The module (notation) of a model member: owner of its most-specific type, nearest owned ancestor first."""
        for t in self.specific(x):
            o = next((owner(self.mods, d) for d in self.ancestors(t) if owner(self.mods, d)), None)
            if o:
                return o
        return None

    def is_a(self, x, cls):
        return any(cls in self.ancestors(t) for t in self.asserted.get(x, ()))

    def label(self, x):
        best = None
        for l, lang in self.rows(f"SELECT ?l (LANG(?l) AS ?g) WHERE {{ <{x}> skos:prefLabel ?l }}"):
            if lang.startswith("zh"):
                return l
            best = best or l
        return best or ""

    def types(self, x):
        return [t for (t,) in self.rows(f"SELECT DISTINCT ?t WHERE {{ <{x}> a ?t }}")]

    def src_graph_filter(self):
        return f'FILTER(STRSTARTS(STR(?g), "{SRC_G}"))'

    def onto_graph_filter(self):
        return f'FILTER(STRSTARTS(STR(?g), "{ONTO_G}"))'

    def shape_hits(self, shape=None):
        """Solutions of the aisep-core SHACL-SPARQL constraints over the store ($this unbound):
        (shape, severity, message template, bindings). shape= restricts to one sh:NodeShape.
        The constraints come from the checked commit's own modules/ and pyoxigraph really sends HTTP for SERVICE, so
        they all run in one network-less child (querybox.run_batch, issue #66); an attempt to connect, or no such child
        on this platform, raises instead of returning hits (fail closed: the check cannot pass)."""
        core = [m for m in self.mods if m.name == "aisep-core"]
        cons = []
        for sf in (core[0].shapes if core else []):
            try:
                scs = sparql_constraints(sf)
            except SyntaxError as e:  # a tool error, as for the other module files
                raise AisepError("PARSE_FAILED", f"[Violation] L0 cannot parse module file {self.rel(sf)}: {str(e)[:200]}",
                                 hint="先修好这个文件", details={"file": self.rel(sf), "error": str(e)[:200]}) from None
            cons += [(shp, sev, msg, prefixes + re.sub(r"\$this\b", "?this", sel))
                     for shp, sev, msg, sel, prefixes in scs if not shape or shp == shape]
        if not cons:
            return
        try:
            results = querybox.run_batch(self.store, [q for *_, q in cons], {})
        except querybox.NetworkAttempt:
            raise AisepError("QUERY_NOT_READONLY", "aisep-core 的 SHACL-SPARQL 约束试图访问外部端点（SERVICE），"
                             "执行约束的进程已被终止，没有发出请求", hint="去掉 modules/aisep-core 约束里的 SERVICE 子句") from None
        except querybox.Unavailable as e:
            raise AisepError("INTERNAL", f"本机无法建立无网络的查询进程，模块约束未执行：{e}") from None
        for (shp, sev, msg, _), res in zip(cons, results):
            for row in res["rows"]:
                yield shp, sev, msg, {n: _ox_term(row.get(n)) for n in res["variables"]}

    def language_of_type(self, t):
        """R2: the notation (Language module) of a class = owner of its nearest ancestor owned by a Language module;
        None for notation-neutral classes (arch:Element, aisep:ApprovalRecord, ...)."""
        for d in self.ancestors(t):
            o = owner(self.mods, d)
            if o and o.kind == "Language":
                return o
        return None

    def relationships(self):
        """Qualified relationship resources written in sources: (rel, class, source, target, model)."""
        return self.rows(f"""SELECT DISTINCT ?r ?c ?s ?t ?m WHERE {{ GRAPH ?g {{ ?r arch:source ?s }} {self.src_graph_filter()}
            ?r a ?c ; arch:target ?t . OPTIONAL {{ ?r arch:inModel ?m }} }}""", raw=True)

    def build_triples(self):
        out = []
        for r, c, s, t, m in self.relationships():
            u = self.nearest(c.value, self.uf)
            if u and not isinstance(s, ox.Literal):  # a literal arch:source cannot be a subject (L3 reports it)
                out.append((s, ox.NamedNode(u), t, m.value if m else None))
        in_model = {}
        for x, m in self.rows(f"""SELECT DISTINCT ?x ?m WHERE {{ GRAPH ?g {{ ?x arch:inModel ?m }} {self.src_graph_filter()} }}""", raw=True):
            if isinstance(x, ox.NamedNode):
                in_model.setdefault(x.value, m.value)
        self.blank_members()
        for x, m in in_model.items():
            o = self.module_of(x)
            if o:
                out.append((ox.NamedNode(x), ox.NamedNode(AISEP + "notation"), ox.NamedNode(o.iri), m))
        out += self.derive_approval_state(in_model)
        return out

    def blank_members(self):
        """X1: a model member must be an IRI (spec §3). A blank node with arch:inModel is reported (not a crash) by its
        file and its own triples there, never by its blank node label (a fresh random id on every parse)."""
        term = lambda t: "[]" if isinstance(t, ox.BlankNode) else short(t) if isinstance(t, ox.NamedNode) else str(t)
        for f in sorted(self.src_quads, key=self.rel):
            qs = self.src_quads[f]
            seen = set()
            for b in [q.subject for q in qs if q.predicate.value == ARCH + "inModel" and isinstance(q.subject, ox.BlankNode)]:
                if b in seen:
                    continue
                seen.add(b)
                desc = " ; ".join(sorted(f"{term(q.predicate)} {term(q.object)}" for q in qs if q.subject == b))
                self.add("Violation", "build", f"{self.rel(f)}: blank node [ {desc} ] carries arch:inModel — a model "
                         "member must be an IRI (spec §3); it is left out of the build", file=self.rel(f))

    def _bnodes(self):
        """blank node label -> (display text, referrer): text = its file and its own triples there, like X1
        (blank_members); referrer = the subject of the triple that has it as object (None if unreferenced)."""
        if getattr(self, "_bnode_info", None) is None:
            term = lambda t: "[]" if isinstance(t, ox.BlankNode) else short(t) if isinstance(t, ox.NamedNode) else repr(t.value)
            self._bnode_info = {}
            for f in sorted(self.src_quads, key=self.rel):
                own, ref = {}, {}
                for q in self.src_quads[f]:
                    if isinstance(q.subject, ox.BlankNode):
                        own.setdefault(q.subject.value, []).append(f"{term(q.predicate)} {term(q.object)}")
                    if isinstance(q.object, ox.BlankNode):
                        ref.setdefault(q.object.value, q.subject.value)
                for b, po in own.items():
                    self._bnode_info[b] = (f"{self.rel(f)}: blank node [ {' ; '.join(sorted(po))} ]", ref.get(b),
                                           self.rel(f))
        return self._bnode_info

    def display(self, x):
        """short(x); a blank node (its label is a fresh random id on every parse) is shown by its file and triples."""
        v = x if isinstance(x, str) else getattr(x, "value", str(x))
        return self._bnodes()[v][0] if v in self._bnodes() else short(x)

    def anchor(self, x):
        """Stable finding location as add() keywords: focus x itself, or for a blank node the nearest named subject
        referring to it; an unreferenced blank node has none, so focus None and its file (§7.3: the file then joins the
        instance key), never its label, so that the write tools' "new violation" comparison (§5.1 step 5) sees the
        same key on every parse."""
        v, seen = (x if isinstance(x, str) else x.value), set()
        while v in self._bnodes() and v not in seen:
            seen.add(v)
            if self._bnodes()[v][1] is None:
                return {"focus": None, "file": self._bnodes()[v][2]}
            v = self._bnodes()[v][1]
        return {"focus": v}

    def derive_approval_state(self, in_model):
        """spec §6.6 (D10, ADR-009): arch:approvalState is derived, never authored. Per element: the decision of the
        latest aisep:ApprovalRecord (by prov:generatedAtTime) that aisep:approves it; none -> arch:Proposed;
        an element replaced by another (dcterms:isReplacedBy, spec §7.2 merge/split) -> aisep:Superseded.
        v0.2.1 (R3): only records passing the aisep-core L1 ApprovalRecordShape count (the others are ignored with a
        build Warning); instants are compared timezone-normalised (naive = UTC); valid records about the same
        element at the same instant with different decisions are ambiguous (L1 Violation) and, at the latest instant,
        leave the element arch:Proposed (an ambiguous approval approves nothing). Record IRIs never break ties."""
        invalid = dict(self.approval_problems())  # record -> [failed L1 check messages]; the same function L1 reports
        recs = {}  # target -> {instant: {record: decision}}
        for rec, x, ts, dec in self.rows(f"""SELECT ?rec ?x ?time ?dec WHERE {{ GRAPH ?g {{ ?rec aisep:approves ?x }}
                {self.src_graph_filter()} ?rec a/rdfs:subClassOf* aisep:ApprovalRecord .
                OPTIONAL {{ ?rec prov:generatedAtTime ?time }} OPTIONAL {{ ?rec aisep:decision ?dec }} }}"""):
            if rec in invalid:
                continue
            t = parse_xsd_datetime(ts)
            if t is None:  # not expected: approval_problems checked the written form; never drop a record silently
                invalid[rec] = [f"stored prov:generatedAtTime {ts!r} does not parse"]
                continue
            recs.setdefault(x, {}).setdefault(t, {})[rec] = dec
        for rec, msgs in sorted(invalid.items()):
            self.add("Warning", "build", f"{self.display(rec)}: approval record ignored by the approval-state derivation — it "
                     f"fails the L1 ApprovalRecord checks: {' / '.join(sorted(set(msgs)))}")
        latest = {}  # target -> (record, state)
        for x, by_t in recs.items():
            for t, rd in sorted(by_t.items()):
                if len(set(rd.values())) > 1:
                    self.approval_ambiguous.append((x, t, sorted(rd.items())))
            t = max(by_t)
            if len(set(by_t[t].values())) > 1:
                self.add("Warning", "build", f"{short(x)}: ambiguous approval at {t.isoformat()} (records "
                         f"{', '.join(short(r) for r in sorted(by_t[t]))} decide differently) — state left arch:Proposed")
                latest[x] = (min(by_t[t]), ARCH + "Proposed")
            else:
                latest[x] = (min(by_t[t]), DECISION_STATE[next(iter(by_t[t].values()))])
        replaced = {x for x, _ in self.replacements() if x}  # G8: only a valid replacement supersedes
        # only approvable elements get a state (第四轮 R4-5, ADR-016): records, agent activities and Stakeholders are
        # arch:Elements that can never be approved, so they have no approvalState (spec §6.6)
        subjects = {x for x in in_model if self.is_a(x, ARCH + "Element") and not any(self.is_a(x, c) for c in (
                    ARCH + "QualifiedRelationship", AISEP + "ApprovalRecord", AISEP + "AgentActivity", ARCH + "Stakeholder"))} | set(latest)
        out = []
        for x in sorted(subjects):
            state = AISEP + "Superseded" if x in replaced else latest[x][1] if x in latest else ARCH + "Proposed"
            m = in_model.get(x) or (in_model.get(latest[x][0]) if x in latest else None)  # e.g. a whole arch:Model
            out.append((ox.NamedNode(x), ox.NamedNode(ARCH + "approvalState"), ox.NamedNode(state), m))
        return out

    def replacements(self):
        """G8: dcterms:isReplacedBy written in a source, split into (valid, invalid) lists of (x, object): valid when the
        object is an IRI that is an element (arch:inModel member) of some loaded model. Only valid ones derive
        aisep:Superseded; invalid ones are L1 Violations."""
        members = {x for (x,) in self.rows(f"SELECT DISTINCT ?x WHERE {{ GRAPH ?g {{ ?x arch:inModel ?m }} {self.src_graph_filter()} }}")}
        ok = []
        self.bad_replacements = []
        for qs in self.src_quads.values():
            for q in qs:
                if q.predicate.value == NS["dcterms"] + "isReplacedBy":
                    good = isinstance(q.object, ox.NamedNode) and q.object.value in members
                    (ok if good else self.bad_replacements).append((q.subject.value, q.object))
        return ok

    def _approver(self, iri):
        anc = {a for t in self.types(iri) for a in self.ancestors(t)}
        return bool(anc & APPROVERS) and not anc & NOT_APPROVERS

    def approval_problems(self):
        """THE approval-record validity check (spec §6.6, v0.2.1 R3a), used by L1 and by derive_approval_state:
        record -> [messages]. aisep-core ApprovalRecordShape (SPARQL: one decision, one xsd:dateTime-typed time, one
        gate, one evidence = 40-hex commit id or sha256:<64 hex>, approves/approvedBy present; v0.4: at most one
        aisep:activity, an aisep:AgentActivity, and a 40-hex evidence equals its aisep:headCommit — EG25/EG26) plus the
        checks ext-governance L3 states as EG11/EG13/EG15: the gate is one of the aisep:Gates declared in a MODULE file (G2), every approvedBy is an
        arch:Stakeholder instance and not an aisep:AIAgent (Q4=C), and the time's lexical form parses (parse_xsd_datetime)."""
        if getattr(self, "_approval_problems", None) is not None:
            return self._approval_problems
        bad = {}
        for _, _, msg, b in self.shape_hits(APPROVAL_SHAPE):
            if b.get("this") is not None:
                bad.setdefault(b["this"].value, []).append(msg)
        gates = {g for (g,) in self.rows(f"SELECT DISTINCT ?x WHERE {{ GRAPH ?g {{ ?x skos:inScheme aisep:Gates }} {self.onto_graph_filter()} }}")}
        for rec, p, o in self.rows(f"""SELECT DISTINCT ?rec ?p ?o WHERE {{ GRAPH ?g {{ ?rec a ?t }} {self.src_graph_filter()}
                ?t rdfs:subClassOf* aisep:ApprovalRecord . ?rec ?p ?o
                VALUES ?p {{ aisep:gate aisep:approvedBy }} }}""", raw=True):
            rec, p = rec.value, p.value
            if p == AISEP + "gate" and o.value not in gates:
                bad.setdefault(rec, []).append(f"AISEP: aisep:gate {short(o)} is not one of the module-declared aisep:Gates "
                                               "(GateRequirements|GateArchitecture|GateDesign|GateMerge|GateRelease) (EG11, spec §6.6).")
            elif p == AISEP + "approvedBy" and (not isinstance(o, ox.NamedNode)
                                                 or not self._approver(o.value)):
                bad.setdefault(rec, []).append(f"AISEP: aisep:approvedBy {short(o)} is not an arch:Stakeholder (or is an "
                                               "aisep:AIAgent: an AI may not approve) (EG13, spec §6.6).")
        # the lexical form as WRITTEN (the store canonicalises e.g. 24:00:00 to the next day's 00:00:00)
        recs = {r for (r,) in self.rows(f"""SELECT DISTINCT ?r WHERE {{ GRAPH ?g {{ ?r a ?t }} {self.src_graph_filter()}
                ?t rdfs:subClassOf* aisep:ApprovalRecord }}""")}
        for qs in self.src_quads.values():
            for q in qs:
                if q.predicate.value == NS["prov"] + "generatedAtTime" and q.subject.value in recs \
                        and parse_xsd_datetime(q.object.value) is None:
                    bad.setdefault(q.subject.value, []).append(
                        f"AISEP: prov:generatedAtTime {q.object.value!r} is not a well-formed xsd:dateTime "
                        "(YYYY-MM-DDThh:mm:ss[.s][Z|±hh:mm], a real calendar instant, hour < 24) (EG15, spec §6.6).")
        # 第四轮 R4-5 (ADR-016): an existing approves target must be an element (not a record, an activity or a
        # Stakeholder; relationships and views are not elements), an arch:Model or an ADR. A target that is not a
        # subject of any source is judged as before (the merge-time check reports it against the evidence snapshot).
        src_types = {}
        for x, t in self.rows(f"SELECT DISTINCT ?x ?t WHERE {{ GRAPH ?g {{ ?x a ?t }} {self.src_graph_filter()} FILTER(isIRI(?t)) }}"):
            src_types.setdefault(x, set()).add(t)
        subjects = {q.subject.value for qs in self.src_quads.values() for q in qs if isinstance(q.subject, ox.NamedNode)}
        for rec, x in self.rows(f"""SELECT DISTINCT ?rec ?x WHERE {{ GRAPH ?g {{ ?rec aisep:approves ?x }} {self.src_graph_filter()}
                ?rec a/rdfs:subClassOf* aisep:ApprovalRecord FILTER(isIRI(?x)) }}"""):
            if x not in subjects:
                # 第四轮复评 OWN-1: a metamodel term (typed in the ontology graphs, not a source subject) exists but
                # is not approvable; only a target typed nowhere keeps the "does not exist" reading above
                if self.rows(f"SELECT ?t WHERE {{ GRAPH ?g {{ <{x}> a ?t }} {self.onto_graph_filter()} }} LIMIT 1"):
                    bad.setdefault(rec, []).append(
                        f"AISEP: aisep:approves {short(x)} is a metamodel term, not a model element, arch:Model or ADR "
                        "— it cannot be approved (第四轮 R4-5, spec §6.6).")
                continue
            anc = {a for t in src_types.get(x, ()) for a in self.ancestors(t)}
            element = (x in self.asserted and ARCH + "Element" in anc and not anc & {
                ARCH + "QualifiedRelationship", AISEP + "ApprovalRecord", AISEP + "AgentActivity", ARCH + "Stakeholder"})
            if not (element or ARCH + "Model" in anc or NS["ad"] + "Decision" in anc):
                bad.setdefault(rec, []).append(
                    f"AISEP: aisep:approves {short(x)} is not an approvable target — an element other than an approval "
                    "record, agent activity or arch:Stakeholder, an arch:Model, or an ADR (第四轮 R4-5, spec §6.6).")
        self._approval_problems = bad
        return bad

    def activity_problems(self):
        """v0.4 (spec §6.7, ADR-013) aisep:AgentActivity checks beyond the aisep-core AgentActivityShape (cardinality,
        datatype, commit format): prov:wasAssociatedWith is an arch:Stakeholder or prov:Agent instance (the same test
        as aisep:approvedBy), prov:startedAtTime / prov:endedAtTime as WRITTEN parse with parse_xsd_datetime (the
        approval-record parser), and start <= end timezone-normalised. activity -> [messages]; ext-governance L3 states
        the same as EG17/EG18/EG19/EG24."""
        bad = {}
        acts = {a for (a,) in self.rows(f"""SELECT DISTINCT ?a WHERE {{ GRAPH ?g {{ ?a a ?t }} {self.src_graph_filter()}
                ?t rdfs:subClassOf* aisep:AgentActivity }}""")}
        times = {}
        for qs in self.src_quads.values():
            for q in qs:
                s, p = q.subject.value, q.predicate.value
                if s not in acts:
                    continue
                if p == NS["prov"] + "wasAssociatedWith" and (not isinstance(q.object, ox.NamedNode) or not any(
                        AGENTS & set(self.ancestors(t)) for t in self.types(q.object.value))):
                    bad.setdefault(s, []).append(f"AISEP: prov:wasAssociatedWith {short(q.object)} is not an "
                                                 "arch:Stakeholder or prov:Agent (EG17, spec §6.7).")
                elif p in (NS["prov"] + "startedAtTime", NS["prov"] + "endedAtTime"):
                    t = parse_xsd_datetime(q.object.value)
                    if t is None:
                        bad.setdefault(s, []).append(
                            f"AISEP: {short(p)} {q.object.value!r} is not a well-formed xsd:dateTime "
                            "(YYYY-MM-DDThh:mm:ss[.s][Z|±hh:mm], a real calendar instant, hour < 24) (spec §6.7).")
                    else:
                        times.setdefault((s, p.rsplit("#", 1)[1]), []).append((t, q.object.value))
        for a in sorted(acts):
            st, en = times.get((a, "startedAtTime"), []), times.get((a, "endedAtTime"), [])
            if len(st) == 1 and len(en) == 1 and en[0][0] < st[0][0]:
                bad.setdefault(a, []).append(f"AISEP: agent activity ends before it starts: prov:endedAtTime {en[0][1]!r} "
                                             f"is earlier than prov:startedAtTime {st[0][1]!r} (timezone-normalised) "
                                             "(EG24, spec §6.7).")
        return bad

    def model_graph_of(self, f):
        qs = self.src_quads[f]
        models = {q.subject.value for q in qs if q.predicate.value == A and q.object.value == ARCH + "Model"}
        if len(models) != 1:
            models = {q.object.value for q in qs if q.predicate.value == ARCH + "inModel"}
        return models.pop() if len(models) == 1 else None

    # ---------------- build
    def write_build(self, out_path):
        quads = []
        for f, qs in self.src_quads.items():
            g = self.model_graph_of(f)
            gn = ox.NamedNode(g) if g else ox.DefaultGraph()
            quads += [ox.Quad(q.subject, q.predicate, q.object, gn) for q in qs]
        for s, p, o, m in self.built:
            quads.append(ox.Quad(s, p, o, ox.NamedNode(m) if m else ox.DefaultGraph()))
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        ox.serialize(quads, output=out_path, format=ox.RdfFormat.N_QUADS)
        return quads

    # ---------------- L1
    def l1(self):
        in_src = set()
        for qs in self.src_quads.values():
            for q in qs:
                in_src.add(q.subject.value); in_src.add(q.object.value)
        for shape, sev, msg, b in self.shape_hits():
            focus = b.get("this")
            if shape == APPROVAL_SHAPE or focus is None or focus.value not in in_src:
                continue  # only model content, never ontology individuals; approval records: approval_problems()
            text = re.sub(r"\{[?$](\w+)\}", lambda mm: short(b[mm.group(1)]) if b.get(mm.group(1)) is not None else "?", msg)
            self.add(sev, "L1", f"{self.display(focus)}: {text}", **self.anchor(focus))
        for rec, msgs in sorted(self.approval_problems().items()):  # R3a: the same check the derivation uses
            if rec in in_src:
                for msg in sorted(set(msgs)):
                    self.add("Violation", "L1", f"{self.display(rec)}: {msg}", **self.anchor(rec))
        for act, msgs in sorted(self.activity_problems().items()):  # v0.4 §6.7
            if act in in_src:
                for msg in sorted(set(msgs)):
                    self.add("Violation", "L1", f"{self.display(act)}: {msg}", **self.anchor(act))
        for x, t, rds in self.approval_ambiguous:  # R3c
            self.add("Violation", "L1", f"{short(x)}: ambiguous approval — valid approval records "
                     f"{', '.join(f'{short(r)} ({short(d)})' for r, d in rds)} approve it at the same instant "
                     f"{t.isoformat()} (timezone-normalised) with different decisions; record the later decision with a "
                     f"later prov:generatedAtTime (spec §6.6)")
        # direct triples written in a source file (spec §8): the predicate is the unqualifiedForm of some QR class
        direct_of = {}  # unqualifiedForm -> the most general QR class declaring it (am4:Access, not am4:ReadWriteAccess)
        for c, u in sorted(self.uf.items()):
            if not any(self.uf.get(d) == u for d in self.ancestors(c)[1:]):
                direct_of.setdefault(u, c)
        for f, qs in self.src_quads.items():
            for q in qs:
                if q.predicate.value in direct_of:
                    self.add("Violation", "L1", f"{short(q.subject)}: direct triple written in source {self.rel(f)}: "
                             f"{short(q.subject)} {short(q.predicate)} {short(q.object)} — write a qualified relationship "
                             f"resource (a {short(direct_of[q.predicate.value])} with arch:source/arch:target/arch:inModel) "
                             f"instead; `aisep build` generates the direct triple")
                elif q.predicate.value == ARCH + "approvalState":  # spec §6.6 (D10)
                    self.add("Violation", "L1", f"{short(q.subject)}: hand-written arch:approvalState {short(q.object)} in "
                             f"source {self.rel(f)} — approval state is derived by `aisep build` from aisep:ApprovalRecord "
                             f"(aisep:approves/aisep:decision/prov:generatedAtTime); record an approval instead")
        self.l1_model_schema()
        self.l1_closed_predicates(set(direct_of))
        self.l1_property_domains()
        for x, o in getattr(self, "bad_replacements", []):  # G8
            self.add("Violation", "L1", f"{short(x)}: dcterms:isReplacedBy {short(o) if isinstance(o, ox.NamedNode) else repr(o.value)} "
                     f"— isReplacedBy target must be an IRI that is an element (arch:inModel member) of some model; it "
                     f"does not supersede {short(x)}")
        self.l1_one_notation()
        self.l1_notation_mixing()
        self.l1_refines()

    def l1_model_schema(self):
        """R1 (v0.2.1) "model files must not change the metamodel": the only schema-level content a source file may
        hold is a single-parent specialisation `:X rdfs:subClassOf <declared element/relationship class>` (optionally
        `:X a owl:Class|rdfs:Class`) plus names/definition on :X. Everything else that touches the metamodel is an L1
        Violation: triples about module/upstream terms, property declarations, rdfs:/owl: axioms, multi-parent classes,
        and the module-only annotations aisep:assertedShortcut / aisep:dependency / arch:unqualifiedForm."""
        onto_subjects = {s for (s,) in self.rows(f"SELECT DISTINCT ?s WHERE {{ GRAPH ?g {{ ?s ?p ?o }} "
                                                 f"{self.onto_graph_filter()} FILTER(isIRI(?s)) }}")}
        is_meta = lambda iri: iri in onto_subjects or owner(self.mods, iri) is not None
        # G2: concept schemes declared by module files (aisep:Gates, aisep:Decisions, ...) are closed to model files
        schemes = {x for (x,) in self.rows(f"SELECT DISTINCT ?x WHERE {{ GRAPH ?g {{ ?x a skos:ConceptScheme }} {self.onto_graph_filter()} }}")}
        abstract = {x for (x,) in self.rows(f"SELECT DISTINCT ?x WHERE {{ GRAPH ?g {{ ?x arch:isAbstractClass true }} {self.onto_graph_filter()} }}")}
        sub, cls_types = NS["rdfs"] + "subClassOf", {NS["owl"] + "Class", NS["rdfs"] + "Class"}
        parents, classes = {}, set()
        for qs in self.src_quads.values():
            for q in qs:
                if isinstance(q.subject, ox.NamedNode) and not is_meta(q.subject.value):
                    if q.predicate.value == sub:
                        parents.setdefault(q.subject.value, set()).add(q.object.value)
                        classes.add(q.subject.value)
                    elif q.predicate.value == A and q.object.value in cls_types:
                        classes.add(q.subject.value)
        head = "model file must not change the metamodel (v0.2.1 R1) —"
        tail = ("a model file may only specialise ONE declared element class (`:X rdfs:subClassOf <class>` plus "
                "labels/definition); metamodel changes belong in a module")
        for f, qs in self.src_quads.items():
            for q in qs:
                s, p, o = q.subject.value, q.predicate.value, q.object.value
                if isinstance(q.subject, ox.NamedNode) and is_meta(s):
                    why = f"triple about the module/upstream term {short(s)} ({short(s)} {short(p)} {short(o)})"
                elif p in META_PREDICATES:
                    why = f"{short(p)} on {short(s)} (only a module file may declare it; it is ignored here)"
                elif p in (SKOS + "inScheme", SKOS + "topConceptOf") and o in schemes:
                    why = (f"{short(s)} {short(p)} {short(o)} adds a member to the module concept scheme {short(o)} "
                           f"(model files must not add members to module concept schemes)")
                elif s in classes:
                    ok = p in NAME_PREDICATES or p == sub or (p == A and o in cls_types)
                    why = None if ok else f"model-declared class {short(s)} carries {short(p)} {short(o)}"
                elif p == A and o.startswith(SCHEMA_NS) and o != NS["owl"] + "NamedIndividual":
                    why = f"{short(s)} is declared a {short(o)}"
                elif p.startswith((NS["rdfs"], NS["owl"])) and p not in INSTANCE_SCHEMA_OK:
                    why = f"schema axiom {short(s)} {short(p)} {short(o)}"
                else:
                    why = None
                if why:
                    self.add("Violation", "L1", f"{short(s)}: {head} {why} in {self.rel(f)}; {tail}")
        for c in sorted(classes):
            ps = sorted(parents.get(c, ()))
            if len(ps) != 1:
                self.add("Violation", "L1", f"{short(c)}: {head} model-declared class has {len(ps)} rdfs:subClassOf "
                         f"parents ({', '.join(map(short, ps)) or 'none'}); exactly one declared element class is allowed "
                         f"(single-parent specialisation)")
            elif not {ARCH + "Element", ARCH + "QualifiedRelationship"} & set(self.ancestors(ps[0])) or c in self.ancestors(ps[0]):
                self.add("Violation", "L1", f"{short(c)}: {head} parent {short(ps[0])} is not a declared element or "
                         f"relationship class (subclass of arch:Element / arch:QualifiedRelationship)")
            else:  # G6: the module class the specialisation chain ends at must be concrete and Language/Extension-owned
                root, seen = ps[0], {c}
                while root in classes and root not in seen and len(parents.get(root, ())) == 1:
                    seen.add(root); root = next(iter(parents[root]))
                if root in classes:
                    continue  # the chain's own bad link is reported on that class
                o = owner(self.mods, root)
                if root in ABSTRACT_ROOTS or root in abstract or not o or o.kind not in ("Language", "Extension"):
                    why = ("a notation-neutral abstract root" if root in ABSTRACT_ROOTS else "marked arch:isAbstractClass true"
                           if root in abstract else f"not owned by a Language or Extension module ({o.name if o else 'no owner'})")
                    self.add("Violation", "L1", f"{short(c)}: {head} specialised class {short(root)} is {why}; a model class "
                             f"must specialise a CONCRETE class of a Language or Extension module (not arch:Element, "
                             f"arch:QualifiedRelationship, arch:ModelConcept or an arch:isAbstractClass class)")

    def pname(self, iri):
        """Prefixed name using the source files' own prefixes (falls back to short())."""
        s = short(iri)
        if s != iri:
            return s
        for k, ns in sorted(self.prefixes.items(), key=lambda kv: -len(kv[1])):
            if iri.startswith(ns) and len(iri) > len(ns):
                return f"{k}:{iri[len(ns):]}"
        return f"<{iri}>"

    def l1_closed_predicates(self, direct):
        """G7 closed-world predicates: every predicate in a model file is declared (rdf:Property/owl:ObjectProperty/
        owl:DatatypeProperty/owl:AnnotationProperty) in a loaded module or vendored ontology graph, or is in
        PREDICATE_ALLOW. A declared property linking two model members must be in ELEMENT_LINK_OK (or be a direct-triple
        predicate, reported above) — element-to-element links are qualified relationships."""
        values = " ".join(f"<{k}>" for k in PROPERTY_DECL)
        declared = {p for (p,) in self.rows(f"""SELECT DISTINCT ?p WHERE {{ GRAPH ?g {{ ?p a ?k }} {self.onto_graph_filter()}
                                                VALUES ?k {{ {values} }} }}""")}
        members = {x for (x,) in self.rows(f"SELECT DISTINCT ?x WHERE {{ GRAPH ?g {{ ?x arch:inModel ?m }} {self.src_graph_filter()} }}")}
        for f, qs in self.src_quads.items():
            for p in sorted({q.predicate.value for q in qs} - declared - PREDICATE_ALLOW):
                # one violation per subject using it (not per file): a write that adds another use must count as new
                for s in dict.fromkeys(q.subject for q in qs if q.predicate.value == p):
                    self.add("Violation", "L1", f"{short(s)}: undeclared predicate {self.pname(p)} in model file {self.rel(f)} — "
                             f"every predicate must be declared in a loaded module/ontology or be one of the authoring-profile "
                             f"predicates (closed world, G7); model links between elements as qualified relationships",
                             focus=s.value if isinstance(s, ox.NamedNode) else None)
            for q in qs:
                p = q.predicate.value
                if p in declared and p not in ELEMENT_LINK_OK and p not in direct and p not in PREDICATE_ALLOW \
                        and q.subject.value in members and isinstance(q.object, ox.NamedNode) and q.object.value in members:
                    self.add("Violation", "L1", f"{short(q.subject)}: element-to-element link must be a qualified "
                             f"relationship — {short(q.subject)} {self.pname(p)} {short(q.object)} in {self.rel(f)} links two "
                             f"model elements with a plain property; write a qualified relationship resource (G7)")

    def l1_property_domains(self):
        """Issue #67: the rdfs:domain a module file (modules/**) declares for a property is enforced on model files —
        a subject using the property must have an asserted rdf:type (in a source file) that is the domain class or a
        subclass of it. Otherwise a declared property could be borrowed onto any element (aisep:swhid on a TestResult,
        aisep:approves between two ordinary elements) and its targetClass shapes would never see it. Domains declared
        only by vendored ontologies are not enforced here."""
        domains = {}
        for p, d in self.rows(f"""SELECT DISTINCT ?p ?d WHERE {{ GRAPH ?g {{ ?p rdfs:domain ?d }}
                                  FILTER(STRSTARTS(STR(?g), "{ONTO_G}modules/") && isIRI(?d)) }}"""):
            domains.setdefault(p, set()).add(d)
        types = {}
        for s, t in self.rows(f"SELECT DISTINCT ?s ?t WHERE {{ GRAPH ?g {{ ?s a ?t }} {self.src_graph_filter()} FILTER(isIRI(?t)) }}"):
            types.setdefault(s, set()).add(t)
        seen = set()
        for f, qs in self.src_quads.items():
            for q in qs:
                p, s = q.predicate.value, q.subject.value
                for d in sorted(domains.get(p, ())):
                    if (s, p, d) in seen or any(d in self.ancestors(t) for t in types.get(s, ())):
                        continue
                    seen.add((s, p, d))
                    self.add("Violation", "L1", f"{short(q.subject)}: {self.pname(p)} has rdfs:domain {short(d)} but "
                             f"{short(q.subject)} is not a {short(d)} (asserted types: "
                             f"{', '.join(sorted(map(short, types.get(s, ())))) or 'none'}) in {self.rel(f)} — a property "
                             f"may only be used on its domain class (issue #67)",
                             focus=s if isinstance(q.subject, ox.NamedNode) else None)

    def l1_one_notation(self):
        """R2 (v0.2.1) one notation per element: every asserted type, the redundant superclasses included, belongs to
        the same notation (Language module); notation-neutral core classes do not count."""
        for x, ts in sorted(self.asserted.items()):
            by = {}
            for t in sorted(set(ts)):
                o = self.language_of_type(t)
                if o:
                    by.setdefault(o.name, []).append(short(t))
            if len(by) > 1:
                self.add("Violation", "L1", f"{short(x)}: one notation per element — typed in {len(by)} notations "
                         f"({'; '.join(f'{n}: {', '.join(v)}' for n, v in sorted(by.items()))}); model the same thing as one "
                         f"node per notation linked by arch:Refines (refiner = lower level, spec §7.2)")

    def l1_notation_mixing(self):
        """spec §7.3 (D8): a relationship of notation N connects two N nodes. Cross-notation links only through hub
        relationship classes (modules with inheritsHubRules=true), arch:Refines and the trace relationships (§7.1)."""
        for r, c, s, t, m in self.relationships():
            r, c, s, t = r.value, c.value, s.value, t.value
            own = next((owner(self.mods, d) for d in self.ancestors(c) if owner(self.mods, d)), None)
            ends = [(x, self.module_of(x)) for x in (s, t) if self.asserted.get(x)]  # untyped/dangling: other L1 rules
            if (not own or own.kind != "Language") and CORE_SAME_NOTATION & set(self.ancestors(c)) and len(ends) == 2:
                # G5: arch:Association / arch:HasPart / arch:DependsOn (and model subclasses) connect nodes of one notation, or two
                # notation-neutral nodes; cross-notation only via hub classes, arch:Refines and trace relationships
                lang = [mx if mx is not None and mx.kind == "Language" else None for _, mx in ends]
                if lang[0] is not lang[1]:
                    self.add("Violation", "L1", f"{short(r)}: notation mixing — core relationship {short(c)} connects "
                             + " and ".join(f"{short(x)} ({'+'.join(map(short, self.specific(x)))}, notation "
                                            f"{lx.name if lx else 'neutral'})" for (x, _), lx in zip(ends, lang))
                             + "; arch:Association/arch:HasPart/arch:DependsOn need both endpoints in the same notation. Cross-notation "
                             "links only via hub relationships, arch:Refines or trace relationships (spec §7.1/§7.3)")
                continue
            if not own or own.kind != "Language" or ARCH + "Refines" in self.ancestors(c) \
                    or TRACE_CLASSES & set(self.ancestors(c)):
                continue  # other core/extension classes (refines, verification, implementation, ...) may cross notations
            if own.inherits:
                for x, mx in ends:
                    if mx is not None and mx.kind == "Language" and not mx.inherits:
                        self.add("Violation", "L1", f"{short(r)}: notation mixing — hub relationship {short(c)} has endpoint "
                                 f"{short(x)} ({'+'.join(map(short, self.specific(x)))}) of notation {mx.name}, which does not "
                                 f"inherit the hub rules (unknown to the ArchiMate matrix); connect a {mx.name} node to the hub "
                                 f"only through arch:Refines (spec §7.3)")
            else:
                for x, mx in ends:
                    if mx is not own:
                        self.add("Violation", "L1", f"{short(r)}: notation mixing — {own.name} relationship {short(c)} has "
                                 f"endpoint {short(x)} ({'+'.join(map(short, self.specific(x)))}) of notation "
                                 f"{mx.name if mx else 'none'}; both endpoints must be {own.name} nodes. Cross-notation links "
                                 f"only via hub relationships, arch:Refines or trace relationships (spec §7.1/§7.3)")

    def l1_refines(self):
        """spec §7.2 (D9): refiner (source) at a strictly lower aisep:notationLevel than the refined node (code ->
        design -> hub); never within one notation; at most one refined node (primary anchor) per target notation."""
        anchors = {}
        for r, c, s, t, m in self.relationships():
            r, c, s, t = r.value, c.value, s.value, t.value
            if ARCH + "Refines" not in self.ancestors(c) or not self.asserted.get(s) or not self.asserted.get(t):
                continue
            ms, mt = self.module_of(s), self.module_of(t)
            name = lambda mod: mod.name if mod else "none"
            if ms is mt:
                self.add("Violation", "L1", f"{short(r)}: arch:Refines within one notation ({name(ms)}: {short(s)} -> "
                         f"{short(t)}) is forbidden; refines links the same thing across notation levels, use the "
                         f"notation's own Specialization/Composition instead (spec §7.2)")
                continue
            missing = [mod for mod in (ms, mt) if mod is None or mod.level is None]
            if missing:
                self.add("Violation", "L1", f"{short(r)}: arch:Refines endpoint notation {', '.join(map(name, missing))} "
                         f"declares no aisep:notationLevel; refines only links notations of the code -> design -> hub "
                         f"levels (spec §7.2)")
                continue
            if ms.level >= mt.level:
                self.add("Violation", "L1", f"{short(r)}: arch:Refines must point to a higher notation level (code -> "
                         f"design -> hub): {short(s)} is {ms.name} ({LEVEL_NAME[ms.level]}), {short(t)} is {mt.name} "
                         f"({LEVEL_NAME[mt.level]}) (spec §7.2)")
                continue
            anchors.setdefault((s, mt.name), set()).add(t)
        for (s, n), ts in sorted(anchors.items()):
            if len(ts) > 1:
                self.add("Violation", "L1", f"{short(s)}: refines more than one {n} node ({', '.join(sorted(map(short, ts)))}); "
                         f"at most one primary anchor per notation (spec §7.2)")

    # ---------------- L2
    def l2(self):
        perm_of, direct_of, table = rt_table(os.path.join(self.root, os.path.relpath(RT_FILE, ROOT)))
        am4_perm = {c: perm_of[u] for c, u in self.uf.items() if u in perm_of}
        am4_direct = {c: direct_of[u] for c, u in self.uf.items() if u in direct_of}
        # R1: honoured only when a module file declares it
        shortcut = {c for (c,) in self.rows(f"SELECT ?c WHERE {{ GRAPH ?g {{ ?c aisep:assertedShortcut true }} {self.onto_graph_filter()} }}")}
        asserted = {x: self.specific(x) for x in self.asserted}  # D6: redundant superclasses do not vote
        closure = lambda x: {d for t in asserted.get(x, ()) for d in self.ancestors(t)}
        allowed = lambda perm, s, tgt: all(any(table.get((perm, sa), set()) & tgt for sa in self.ancestors(st))
                                           for st in asserted[s])
        for r, c, s, t, m in self.relationships():
            r, c, s, t = r.value, c.value, s.value, t.value
            own = next((owner(self.mods, d) for d in self.ancestors(c) if owner(self.mods, d)), None)
            if not own or not own.inherits:
                continue  # BPMN/UML-internal links are not judged by the ArchiMate matrix (spec §6.2, §10.2)
            perm = self.nearest(c, am4_perm)
            if not perm or not asserted.get(s) or not asserted.get(t):
                continue  # untyped/dangling endpoints are L1's job
            if (closure(s) | closure(t)) & JUNCTIONS:
                continue  # the tables have no junction rows; upstream shapes permit junction endpoints
            tgt = closure(t)
            # SHACL semantics (spike la.py): every asserted source type must permit it; the target needs one match
            if not allowed(perm, s, tgt):
                self.add("Violation", "L2", f"{short(r)}: illegal by ArchiMate 4.0 relationship table ({short(perm)}): "
                         f"{short(s)} ({'+'.join(map(short, asserted[s]))}) -[{short(c)}]-> {short(t)} "
                         f"({'+'.join(map(short, asserted[t]))})")
                continue
            # spec §6.4: permitted only as the conclusion of a derivation (am4rt:permits… but not permitsDirect…)
            direct = self.nearest(c, am4_direct)
            if direct and not allowed(direct, s, tgt) and not shortcut & set(self.ancestors(c)):
                self.add("Warning", "L2", f"{short(r)}: derived-only relationship asserted — the ArchiMate 4.0 table "
                         f"permits {short(s)} ({'+'.join(map(short, asserted[s]))}) -[{short(c)}]-> {short(t)} "
                         f"({'+'.join(map(short, asserted[t]))}) only as a derivation ({short(direct)} does not list it); "
                         f"model the underlying chain, or declare aisep:assertedShortcut true on the relationship class")


_RT = {}


def rt_table(path=RT_FILE):
    if path not in _RT:
        st = ox.Store()
        st.load(path=path, format=TTL)
        q = lambda s: [[v.value for v in r] for r in st.query(SPARQL_PREFIXES + s)]
        perm_of = dict(q("SELECT ?p ?perm WHERE { ?p am4rt:permittedBy ?perm }"))
        direct_of = dict(q("SELECT ?p ?perm WHERE { ?p am4rt:permittedDirectlyBy ?perm }"))
        table = {}
        for a, perm, b in q("""SELECT ?a ?perm ?b WHERE { { ?p am4rt:permittedBy ?perm } UNION { ?p am4rt:permittedDirectlyBy ?perm }
                               ?a ?perm ?b }"""):
            table.setdefault((perm, a), set()).add(b)
        _RT[path] = (perm_of, direct_of, table)
    return _RT[path]


_SC = {}


def sparql_constraints(path):
    """(shape, severity, message, select, prefix-declarations) for every sh:sparql constraint in a shapes file."""
    if path not in _SC:
        st = ox.Store()
        st.load(path=path, format=TTL)
        q = lambda s: [[None if v is None else v.value for v in r] for r in st.query(SPARQL_PREFIXES + s)]
        decl = "".join(f"PREFIX {p}: <{n}>\n" for p, n in q("SELECT DISTINCT ?p ?n WHERE { ?d sh:declare [ sh:prefix ?p ; sh:namespace ?n ] }"))
        _SC[path] = [(shape, (sev or NS["sh"] + "Violation").split("#")[-1], msg or "SPARQL constraint violated", sel, decl)
                     for shape, sev, msg, sel in q("""SELECT ?shape ?sev ?msg ?sel WHERE { ?shape sh:sparql ?c . ?c sh:select ?sel .
                         OPTIONAL { ?c sh:message ?msg } OPTIONAL { ?shape sh:severity ?sev } } ORDER BY ?shape ?sel""")]
    return _SC[path]


# ------------------------------------------------------------------ L3 (pyshacl)

_RDFLIB = OrderedDict()  # LRU: a long-running MCP server gates many commits, each version of a file adds entries
_RDFLIB_MAX = 128  # one validate of the repo uses ~30 entries, so a few snapshots' worth stay warm
_PREPARED = {}  # (query text, initNs) -> rdflib prepared Query


def _content_key(files):
    """Cache key by file content, not path: a commit snapshot's temp-dir copy of modules/ and vendor/ hits the entry
    of the same bytes parsed elsewhere (merge checks gate several snapshots). These files hold no relative IRIs."""
    import hashlib
    return tuple(hashlib.sha256(open(f, "rb").read()).hexdigest() for f in files)


def rdflib_graph(kind, files, root=ROOT):
    """Union of files as an rdflib Graph, cached by content; shapes files get MINUS rewritten (pyshacl rejects MINUS)."""
    from rdflib import Graph, Literal
    from rdflib.namespace import SH
    key = (kind, _content_key(files))
    if key not in _RDFLIB:
        g = Graph()
        for f in files:
            try:
                g.parse(f, format="turtle")
            except (SyntaxError, UnicodeDecodeError) as e:  # e.g. a shapes file, which only L3 reads: a tool error, as for the other module files
                raise AisepError("PARSE_FAILED", f"[Violation] L0 cannot parse module file {rel(f, root)}: {str(e)[:200]}",
                                 hint="先修好这个文件", details={"file": rel(f, root), "error": str(e)[:200]}) from None
        if kind == "shapes":
            for _, _, c in list(g.triples((None, SH.sparql, None))):
                sel = str(g.value(c, SH.select) or "")
                if re.search(r"\bMINUS\s*\{", sel):  # upstream core-shapes: MINUS == FILTER NOT EXISTS there (vars bound)
                    g.set((c, SH.select, Literal(re.sub(r"\bMINUS\s*\{", "FILTER NOT EXISTS {", sel))))
        _RDFLIB[key] = g
        if len(_RDFLIB) > _RDFLIB_MAX:
            _RDFLIB.popitem(last=False)
    _RDFLIB.move_to_end(key)
    return _RDFLIB[key]


def _prepared_query_graph():
    """rdflib Graph whose query() parses each SPARQL text once: pyshacl re-sends the same sh:select text for every focus
    node (pre-bound via initBindings), and re-parsing it was about half of L3's time. Same text, same initNs
    (rdflib's default: the graph's namespaces), same base (None) as rdflib's own string path, so the same algebra."""
    from rdflib import Graph
    from rdflib.plugins.sparql.processor import prepareQuery

    class PreparedQueryGraph(Graph):
        def query(self, query_object, processor="sparql", result="sparql", initNs=None, initBindings=None,  # noqa: N803
                  use_store_provided=True, **kwargs):
            if isinstance(query_object, str) and processor == "sparql" and not kwargs:
                ns = initNs or dict(self.namespaces())
                key = (query_object, tuple(sorted((k, str(v)) for k, v in ns.items())))
                if key not in _PREPARED:
                    _PREPARED[key] = prepareQuery(query_object, initNs=ns)
                query_object = _PREPARED[key]
            return super().query(query_object, processor, result, initNs, initBindings, use_store_provided, **kwargs)
    return PreparedQueryGraph()


_L3_LOCK = threading.Lock()


def l3(ctx):
    """Serialised process-wide: the MCP server runs tools in threads, and rdflib's SPARQL parser is not thread-safe —
    pyparsing's _trim_arity learns each parse action's arity on its first calls by catching TypeErrors, so concurrent
    first parses raise TypeErrors and can leave a parse action permanently mis-learned (every later L3 fails). The
    caches above are only touched under this lock too (so the LRU bookkeeping needs no lock of its own). L3 is pure Python, so the GIL left no parallelism to lose."""
    with _L3_LOCK:
        _l3(ctx)


def _l3(ctx):
    from rdflib import Graph
    from rdflib.namespace import RDF, SH, SKOS
    from pyshacl import validate as shacl
    model_nt = ox.serialize([ox.Triple(q.subject, q.predicate, q.object) for qs in ctx.src_quads.values() for q in qs]
                            + [ox.Triple(s, p, o) for s, p, o, _ in ctx.built], format=ox.RdfFormat.N_TRIPLES)
    model = Graph().parse(data=model_nt.decode("utf-8"), format="nt")  # once; each run below copies it
    hub = [m for m in ctx.mods if m.name in HUB_MODULES]
    runs = []
    if hub:
        runs.append(("am4+core", onto_files(ctx.mods, "hub"), [f for m in hub for f in m.shapes]))
    for m in ctx.mods:
        if m.name not in HUB_MODULES and m.shapes:
            # every module's plain ontology (so cross-notation endpoints are typed, e.g. a DDD BoundedContext as
            # arch:Element for ext-code's EC6) but only the alignments of this module and its dependencies (spec §10.2
            # "本模块依赖"; e.g. aisep-core's prov:SoftwareAgent ⊑ prov:Agent, which ext-governance's EG17 needs)
            align = [f for d in dependencies(ctx.mods, m.name) for f in d.align]
            runs.append((m.name, list(dict.fromkeys(onto_files(ctx.mods, "none") + align)), m.shapes))
    for name, data_files, shape_files in runs:
        if not shape_files:
            continue
        data = _prepared_query_graph()
        for f in data_files:  # per file: the module runs share most ontology files
            data += rdflib_graph("data", [f], ctx.root)
        data += model
        shapes = rdflib_graph("shapes", shape_files, ctx.root)
        _, report, _ = shacl(data, shacl_graph=shapes, inference="none", allow_warnings=True)
        if not isinstance(report, Graph):  # pyshacl ValidationFailure (SHACL §3.6.2 failure, e.g. a shape breaking
            # the §5.3.1 pre-binding rules): no report graph, so the gate must not pass silently or crash
            ctx.add("Violation", "L3", f"[{name}] SHACL engine rejected the data/shapes (ValidationFailure): {report}")
            continue
        for r in report.subjects(RDF.type, SH.ValidationResult):
            sev = str(report.value(r, SH.resultSeverity)).split("#")[-1]
            focus, path = report.value(r, SH.focusNode), report.value(r, SH.resultPath)
            msg = report.value(r, SH.resultMessage) or f"constraint {short(str(report.value(r, SH.sourceConstraintComponent)))}"
            # several prefLabels (what some shapes report) → pick deterministically, @zh first like Ctx.label;
            # Graph.value() returns whichever the hash-seeded store yields first
            lab = min(data.objects(focus, SKOS.prefLabel) if focus is not None else (), default=None,
                      key=lambda l: (not (getattr(l, "language", None) or "").startswith("zh"),
                                     getattr(l, "language", None) or "", str(l)))
            ctx.add(sev, "L3", f"[{name}] {short(str(focus))}{' (' + str(lab) + ')' if lab else ''}"
                    f"{' path=' + short(str(path)) if path is not None else ''}: {msg}")


# ------------------------------------------------------------------ L4

def l4(ctx):
    # X1: blank-node members are a build Violation already; member queries below interpolate IRIs, so skip blanks
    # spec §6.5: only Must-priority requirements / acceptance criteria are trace gaps when unverified
    for x, m in ctx.rows("""SELECT DISTINCT ?x ?m WHERE { ?x arch:inModel ?m ; a/rdfs:subClassOf* am4:Requirement ;
                                                          aisep:priority aisep:Must . FILTER(isIRI(?x))
            FILTER NOT EXISTS { ?v a/rdfs:subClassOf* aisep:Verification ; arch:target ?x }
            FILTER NOT EXISTS { ?g a/rdfs:subClassOf* am4:Aggregation ; arch:source ?x ; arch:target ?ac .
                                ?v2 a/rdfs:subClassOf* aisep:Verification ; arch:target ?ac } }"""):
        ctx.add("Warning", "L4", f"{short(x)} ({ctx.label(x)}): trace gap — Must requirement/acceptance criterion has no "
                "verifying test case (aisep:Verification), directly or via an aggregated acceptance criterion")
    # spec §6.2 (D4): a node of a non-hub notation (BPMN, UML) that is verified or implemented must reach the hub
    # (a module with inheritsHubRules=true) through arch:Refines
    refines = {}
    for s, t in ctx.rows("SELECT ?s ?t WHERE { ?r a/rdfs:subClassOf* arch:Refines ; arch:source ?s ; arch:target ?t }"):
        refines.setdefault(s, set()).add(t)
    for x, c in ctx.rows("""SELECT DISTINCT ?x ?c WHERE { ?r a ?c ; arch:target ?x .
            ?c rdfs:subClassOf* ?k VALUES ?k { aisep:Verification aisep:Implementation } }"""):
        mx = ctx.module_of(x)
        if not mx or mx.kind != "Language" or mx.inherits:
            continue
        seen, todo = {x}, [x]
        while todo:
            for y in refines.get(todo.pop(), ()):
                if y not in seen:
                    seen.add(y); todo.append(y)
        if not any((ctx.module_of(y) and ctx.module_of(y).inherits) for y in seen - {x}):
            ctx.add("Warning", "L4", f"{short(x)} ({ctx.label(x)}): trace gap — {mx.name} node is a trace endpoint "
                    f"({short(c)}) but has no arch:Refines (chain) to a hub node; add a refines to its am4 anchor (spec §6.2)")
    # R4 (v0.2.1): a refines link to a deprecated/replaced node must move to the replacing node
    for r, s, t in ctx.rows("""SELECT DISTINCT ?r ?s ?t WHERE { ?r a/rdfs:subClassOf* arch:Refines ; arch:source ?s ; arch:target ?t .
            FILTER(EXISTS { ?t owl:deprecated true } || EXISTS { ?t dcterms:isReplacedBy ?n }) }"""):
        repl = sorted(short(n) for (n,) in ctx.rows(f"SELECT DISTINCT ?n WHERE {{ <{t}> dcterms:isReplacedBy ?n }}"))
        ctx.add("Warning", "L4", f"{short(r)}: arch:Refines {short(s)} -> {short(t)} targets a node that is "
                f"{'replaced (dcterms:isReplacedBy)' if repl else 'owl:deprecated'}; migrate the trace link to the "
                f"replacing node ({', '.join(repl) or 'none declared'})")
    for x, t in ctx.rows("""SELECT DISTINCT ?x ?t WHERE { ?x arch:inModel ?m ; a ?t . ?t rdfs:subClassOf* arch:Element . FILTER(isIRI(?x))
            FILTER NOT EXISTS { ?r arch:source|arch:target ?x }
            FILTER NOT EXISTS { { ?x ?p ?y } UNION { ?y ?p ?x } ?y arch:inModel ?m2 . FILTER(?p != arch:inModel) } }"""):
        ctx.add("Info", "L4", f"{short(x)} ({ctx.label(x)}, {short(t)}): isolated element — no relationship or link to another model member")
    # ADR-024 recovery condition ② (#126 follow-up): a model declaring two or more members that can approve (the same
    # test as aisep:approvedBy, Ctx._approver) may mean a second approver has appeared; a hint only, Albert decides
    approvers = {}
    for x, m in ctx.rows("""SELECT DISTINCT ?x ?m WHERE { ?x arch:inModel ?m ; a/rdfs:subClassOf* arch:Stakeholder .
            FILTER(isIRI(?x)) }"""):
        if ctx._approver(x):
            approvers.setdefault(m, set()).add(x)
    for m, xs in sorted(approvers.items()):
        if len(xs) > 1:
            ctx.add("Info", "L4", f"{short(m)}: {len(xs)} members can approve ({', '.join(sorted(short(x) for x in xs))}) — "
                    "ADR-024 recovery condition ② (a second approver or user) may have been met; record it in the "
                    "tracking issue #141 and report to Albert, who decides whether to restore review levels")


# ------------------------------------------------------------------ impact

def impact_hops(ctx, start, depth, mode="depends"):
    """Returns [(depth, element, hops, related)] sorted by depth then short name; hops = [(from, relationship resource,
    relationship class, arrow → ← ~, to)], one per hop from `start`. spec §9: depends = follow the declared dependency direction ('who may break');
    ripple = every traversed relationship both ways ('who may change together'). In both modes Association/None and
    undeclared classes are never traversed, only listed at hop 1 as related."""
    dep = dict(ctx.rows(f"SELECT ?c ?d WHERE {{ GRAPH ?g {{ ?c aisep:dependency ?d }} {ctx.onto_graph_filter()} }}"))  # R1: module files only
    edges, related = {}, {}
    for r, c, s, t, m in ctx.relationships():
        r, c, s, t = r.value, c.value, s.value, t.value
        d = (ctx.nearest(c, dep) or "").replace(AISEP, "")
        if mode == "ripple" and d in ("Forward", "Backward"):
            d = "Both"
        if d in ("Forward", "Both"):
            edges.setdefault(s, []).append((t, c, "→", r))
        if d in ("Backward", "Both"):
            edges.setdefault(t, []).append((s, c, "←", r))
        if d not in ("Forward", "Backward", "Both"):  # None or undeclared: listed at hop 1 only, never traversed
            related.setdefault(s, []).append((t, c, "~", r)); related.setdefault(t, []).append((s, c, "~", r))
    found, todo = {start: (0, [])}, deque([start])
    while todo:
        x = todo.popleft()
        dx, hx = found[x]
        if dx >= depth:
            continue
        for y, c, arrow, r in edges.get(x, []):
            if y not in found:
                found[y] = (dx + 1, hx + [(x, r, c, arrow, y)])
                todo.append(y)
    rows = [(d, x, h, False) for x, (d, h) in found.items() if x != start]
    for y, c, arrow, r in related.get(start, []):
        if y not in found:
            found[y] = (1, None)
            rows.append((1, y, [(start, r, c, arrow, y)], True))
    return sorted(rows, key=lambda r: (r[0], short(r[1])))


def impact(ctx, start, depth, mode="depends"):
    """impact_hops as the CLI prints it: (depth, element, path text, note)."""
    out = []
    for d, x, hops, related in impact_hops(ctx, start, depth, mode):
        if related:
            _, _, c, arrow, y = hops[0]
            out.append((d, x, f"{short(start)} -[{short(c)}{arrow}]- {short(y)}", " (related)"))
        else:
            out.append((d, x, short(start) + "".join(f" -[{short(c)}{a}]-> {short(y)}" for _, _, c, a, y in hops), ""))
    return out


def run_check(ctx):
    ctx.l1()
    ctx.l2()


def expand(ctx, name):
    """slug:local, prefix:local or a full IRI -> a full IRI. The result is always a valid IRI (it is put into SPARQL
    text and into ox.NamedNode by callers): anything else is INVALID_ARGUMENT, never a SPARQL syntax error."""
    if not isinstance(name, str):
        raise AisepError("INVALID_ARGUMENT", f"{name!r} 不是 IRI 或前缀名")
    if "://" in name:
        iri = name.strip("<>")
    else:
        p, _, local = name.partition(":")
        if p not in ctx.prefixes and re.fullmatch(r"[\w-]+", p):
            iri = f"{MODEL_BASE}{p}/{local}"  # the slug:local form that short() prints for model instances
        elif p not in ctx.prefixes:
            raise AisepError("INVALID_ARGUMENT", f"unknown prefix '{p}:' (known: {', '.join(sorted(ctx.prefixes))})")
        else:
            iri = ctx.prefixes[p] + local
    try:
        ox.NamedNode(iri)
    except ValueError as e:
        raise AisepError("INVALID_ARGUMENT", f"{name!r} 不是合法的 IRI：{e}") from None
    return iri


MODEL_SLUG_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")


def model_slug(model):
    """The ONE model-name rule of the MCP tools (write, read and approval paths): a bare slug or the full model IRI
    (trailing '/' optional) -> the slug. Anything path-like ('procurement/', '../x', './x', '.../a/../b/') is
    INVALID_ARGUMENT naming `model`; whether models/<slug>/ exists is the caller's MODEL_NOT_FOUND."""
    slug = model
    if isinstance(model, str) and model.startswith(MODEL_BASE):
        slug = model[len(MODEL_BASE):]
        slug = slug[:-1] if slug.endswith("/") else slug
    if not isinstance(slug, str) or not MODEL_SLUG_RE.fullmatch(slug):
        raise AisepError("INVALID_ARGUMENT", f"model {model!r} 须为模型 slug（^[A-Za-z0-9][A-Za-z0-9_-]*$）或完整模型 IRI",
                         details={"model": model, "rejectedFields": ["model"]})
    return slug


def forget_paths(prefix):
    """Drop the per-path caches (relationship table, SHACL-SPARQL constraints) for files under prefix —
    a deleted snapshot directory's path may be reused by a later snapshot of a different commit."""
    for k in [k for k in _RT if k.startswith(prefix)]:
        del _RT[k]
    for k in [k for k in _SC if k.startswith(prefix)]:
        del _SC[k]


def shown(problems, layers):
    """THE display order and de-duplication of problems (CLI report and MCP findings): severity, layer, text."""
    return sorted({p for p in problems if p[1] in layers}, key=lambda p: ({"Violation": 0, "Warning": 1}.get(p[0], 2), p[1], p[2]))
