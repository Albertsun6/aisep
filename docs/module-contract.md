# Prototype contract (shared by all module authors) — implements `docs/metamodel-spec.md` v0.2 (+ v0.2.1 rules R1–R4 from the adversarial audit)

Python: the main checkout's `.venv/bin/python` (`~/Desktop/AISEP/aisep/.venv`; pyoxigraph 0.5, pyshacl 0.40, rdflib 7.6). Do NOT create another venv.
Vendored upstream (read-only): `vendor/meta.linked.archi/ttl/*.ttl` (file name = URL path, `/`→`_`). rdflib cannot parse files with RDF 1.2 `<<( )>>` (e.g. `archimate4_relationship-tables.ttl`); pyoxigraph can.
Reference implementation from the spike (copy ideas freely): `/Users/yongqian/Desktop/AISEP/spike-linked-archi/scripts/la.py`, `shapes/aisep-closed-world.ttl`, `scripts/negative_tests.py`, `scripts/diff_test.py`.

## Namespaces (fixed — use exactly these)
```
arch:  https://meta.linked.archi/core#
am4:   https://meta.linked.archi/archimate4/onto#
am4vp: https://meta.linked.archi/archimate4/viewpoints#
am4rt: https://meta.linked.archi/archimate4/relationship-tables#
bpmn:  (whatever IRI vendor/.../bpmn_onto.ttl declares — read it)
uml:   (whatever IRI vendor/.../uml_onto.ttl declares — read it)
ad:    (whatever IRI vendor/.../arch-decision.ttl declares)
aisep: https://aisep.example/ont/aisep#        (core AISEP vocab: module manifest terms, extensions, impact vocab)
ddd:   https://aisep.example/ont/ddd#
model: https://aisep.example/model/<slug>/     (instances)
```

## Module layout (one directory per module under `modules/`)
```
modules/<name>/
  metamodel.ttl   # REQUIRED: one arch:Metamodel individual with
                  #   aisep:moduleKind aisep:Language|aisep:Extension|aisep:Alignment|aisep:Framework
                  #   owl:versionInfo "0.1.0"
                  #   aisep:loads  "<relative path>" ...   (vendor or module files this module needs, in load order;
                  #                                        vendor paths start with "vendor/")
                  #   aisep:shapesFile "<relative path>" ... (SHACL files run in L3 for this module)
                  #   aisep:alignmentFile "<relative path>"  (subClassOf/subPropertyOf axioms to am4; optional)
                  #   aisep:inheritsHubRules true|false     (Language modules only)
                  #   aisep:ownsNamespace "<IRI prefix>" ... (namespaces whose classes belong to this module; used
                  #                                        to derive aisep:notation and to scope validation)
                  #   aisep:notationLevel aisep:LevelCode|aisep:LevelDesign|aisep:LevelHub   (Language modules:
                  #                                        uml=code, bpmn/ddd=design, am4=hub; Extensions have none)
                  #   aisep:impactFile "<relative path>"   (aisep:dependency overrides; ONLY declared files are loaded)
  onto.ttl        # classes/properties this module defines (if any)
  shapes.ttl      # SHACL (SHACL Core + SPARQL constraints WITHOUT MINUS and WITHOUT the substring "SERVICE"/"Service "
                  #   followed by whitespace — pyshacl rejects those)
  align.ttl       # alignment axioms (only for Language/Alignment modules)
  impact.ttl      # optional: aisep:dependency overrides — effective only if the manifest names it in aisep:impactFile
  tests/valid/*.ttl     # each MUST pass L0–L3 when loaded together with modules it depends on
  tests/invalid/*.ttl   # each MUST fail; first line is `# expect: <substring of an expected Violation message>`
```
Test fixtures are MODEL files (instances), written in the authoring profile below. A fixture may reference instances in `models/procurement/*.ttl` only if it says so in a `# uses: models/procurement` line.
Optional header lines (within the first 5 lines): `# modules: bpmn uml` adds those modules (and their dependencies) to
the fixture's environment; in a valid fixture `# expect-warning: <substring>` / `# expect-no-warning: <substring>` make
the fixture fail unless a Warning containing the substring is / is not reported (Warnings never fail otherwise; valid
fixtures run L0–L4, so L4 Warnings can be expected too).

## Authoring profile (what humans/AI write in model files)
- Every element: exactly one most-specific rdf:type (asserting its own superclasses as well is allowed, D6; two types neither of which is a subclass of the other is a Violation); **one notation per element** (v0.2.1 R2, L1): every asserted type, redundant superclasses included, belongs to the same notation (Language module by `aisep:ownsNamespace` of the type's nearest owned ancestor; notation-neutral core classes such as arch:Element do not count) — `a ddd:Aggregate , am4:DataObject` is a Violation, model two nodes linked by `arch:Refines` instead; `arch:inModel <model IRI>` exactly once, exactly one `skos:prefLabel "…"@zh` (junctions/gateways may have none); English/other names go to `skos:altLabel`.
- Every relationship: ONE qualified relationship resource (`a am4:Serving` etc. or a subclass) with `arch:source`, `arch:target`, `arch:inModel`. **Never write the direct triple** — `aisep build` generates it from `arch:unqualifiedForm` (declared upstream on QR classes; AISEP modules must declare it on their own QR classes too).
- Notation mixing (§7.3, L1): a relationship class of a non-hub Language (BPMN, UML) needs both endpoints in that notation; a hub relationship class (am4, or a module with `inheritsHubRules true`) may not touch a node of an `inheritsHubRules false` module. The core classes `arch:Association` / `arch:HasPart` (and any model subclass of them) connect two nodes of the same notation, or two notation-neutral nodes. Cross-notation only via hub classes between hub-judged nodes, `arch:Refines`, `aisep:Verification`/`aisep:Implementation` (and the plain properties `aisep:approves`, `ad:relatedConcept`).
- Same real thing in two notations → two nodes linked by a qualified `arch:Refines` relationship (core), refiner = source. §7.2 (L1): the refiner's module level must be strictly lower than the refined one's (code → design → hub); no refines within one notation or to/from a module without a level; at most one refines target per (node, target notation).
- Never write `arch:approvalState` (L1 Violation). Write an `aisep:ApprovalRecord` (`aisep:gate` ∈ the 5 module-declared aisep:Gates, `aisep:decision` aisep:DecisionApproved|aisep:DecisionRejected, `aisep:approvedBy` an arch:Stakeholder instance that is not an `aisep:AIAgent` (an AI may not approve, Q4=C), `aisep:approves`, `prov:generatedAtTime` a well-formed xsd:dateTime — `YYYY-MM-DDThh:mm:ss[.s][Z|±hh:mm]`, a real calendar instant, no `24:00` — and — **required since v0.2.1** — exactly one `aisep:evidence` string matching `^[0-9a-f]{40}$` (git commit id) or `^sha256:[0-9a-f]{64}$` (report hash)); `aisep build` derives approvalState per element (v0.2.1 R3):
  - only records passing the L1 ApprovalRecord checks (`Ctx.approval_problems`: aisep-core `ApprovalRecordShape` + gate/approvedBy/dateTime checks; ext-governance EG11/EG13/EG15/EG16 in L3 state the same rules) count; every other record is ignored and `build` prints a `[Warning] build … approval record ignored …` for it;
  - the latest valid record by `prov:generatedAtTime`, compared timezone-normalised (naive = UTC), decides: arch:Approved / aisep:Rejected; no valid record → arch:Proposed;
  - two valid records about the same element at the same instant with different decisions → L1 Violation `ambiguous approval`; if that instant is the latest, the element stays arch:Proposed (build Warning). Record IRIs never break ties;
  - **Superseded** = the element has a valid `dcterms:isReplacedBy` (written in a source file, object an element of some model — G8); this wins over any record.
  - optional (v0.4, §6.6) `aisep:activity` → at most one `aisep:AgentActivity`; when `aisep:evidence` is a 40-hex commit it must equal that activity's `aisep:headCommit`. Both are part of `Ctx.approval_problems` (L1 = derivation; L3 EG25/EG26), so a record breaking them is ignored by the derivation. The activity must be a model element (an IRI with `arch:inModel`, not a blank node; L3 EG25 `sh:nodeKind sh:IRI`), and `aisep:activity` / `prov:wasAssociatedWith` may only be used on an approval record / an `aisep:AgentActivity` (aisep-core `ActivityLinkSubjectShape`, L1 and L3).
- **Completed AI activity (v0.4, §6.7, ADR-013, ADR-014)**: `aisep:AgentActivity` (⊑ arch:Element, prov:Activity; notation-neutral like aisep:ApprovalRecord; same label/`arch:inModel` rules as every element) is written only when a task passes a gate (`governance.record_approval`) — never in-progress state, never the changed elements (those come from `model.diff(baseCommit, headCommit)`). Exactly one each of: `prov:wasAssociatedWith` (an arch:Stakeholder or prov:Agent instance, e.g. an `aisep:AIAgent` ⊑ prov:SoftwareAgent ⊑ prov:Agent — wider than `aisep:approvedBy`, which excludes AI agents), `prov:startedAtTime` and `prov:endedAtTime` (well-formed xsd:dateTime, same parser as approval records, start <= end timezone-normalised, a timezone-less value read as UTC in both L1 and EG24), `aisep:sessionRef` and `aisep:branch` (non-empty strings), `aisep:baseCommit` (the merge-base) and `aisep:headCommit` (`^[0-9a-f]{40}$`). L1: aisep-core `AgentActivityShape` + `Ctx.activity_problems`; L3: ext-governance EG17–EG24.
- Optional `aisep:priority` ∈ aisep:Priorities (aisep:Must|Should|Could|Wont, at most one) on an am4:Requirement / aisep:AcceptanceCriterion only (§6.5, EV9/EV10); only Must items without a test are L4 trace gaps. Optional `ddd:payload` on a ddd:Command only, pointing to an am4:DataObject (§6.4 D3).
- Optional run provenance on an `aisep:TestResult` (§6.5, ext-verification v0.3.0): `aisep:testedCommit` (a plain xsd:string, `^[0-9a-f]{40}$`, at most 40 characters), `aisep:ciRun` (an IRI, the CI run URL) and `schema:codeRepository` (an IRI, the repository URL), each at most one (EV11–EV13); `aisep:testedCommit` / `aisep:ciRun` may only be stated on an `aisep:TestResult` (EV14).
- No rdf:reifies / `<<( )>>`, no arch:partOfModel / arch:exposedInView / arch:contains.
- **Model files must not change the metamodel** (v0.2.1 R1, L1): the only schema-level triples allowed in a model file are `:X rdfs:subClassOf <declared class>` with exactly ONE parent (single-parent specialisation; the chain, possibly via other such model classes, ends at a CONCRETE class of a Language or Extension module — not arch:Element, arch:QualifiedRelationship, arch:ModelConcept or an `arch:isAbstractClass true` class), optionally `:X a owl:Class|rdfs:Class`, plus `rdfs:label|rdfs:comment|skos:prefLabel|skos:altLabel|skos:definition` on :X. Violations: rdfs:subPropertyOf and other rdfs:/owl: axioms (instances may still carry `owl:deprecated`, `rdfs:label`, `rdfs:comment`, `rdfs:seeAlso`), property/class/shape declarations (`a owl:ObjectProperty` …), a class with two parents, any triple whose subject is a module/upstream term (e.g. `am4:Serving aisep:assertedShortcut true`), `skos:inScheme`/`skos:topConceptOf` a module concept scheme (e.g. minting `:myGate skos:inScheme aisep:Gates`; gate membership is judged on module files only), and `aisep:assertedShortcut` / `aisep:dependency` / `arch:unqualifiedForm` on anything.
- **Closed-world predicates (G7, L1)**: every predicate in a model file is either declared (`rdf:Property` / `owl:ObjectProperty` / `owl:DatatypeProperty` / `owl:AnnotationProperty`) in a loaded module or vendored ontology graph (shapes files do not count), or one of the authoring-profile predicates `rdf:type`, `skos:prefLabel|altLabel|definition|note`, `dcterms:isReplacedBy`, `owl:deprecated` (instances), `rdfs:subClassOf` (only as R1 allows), `prov:generatedAtTime`, `prov:startedAtTime`, `prov:endedAtTime`, `prov:wasAssociatedWith` (v0.4; no other `prov:` predicate, e.g. `prov:used` is rejected), `schema:codeRepository`, plus `rdfs:label|rdfs:comment` (added: needed by the valid fixture `r1-model-specialisation-ok.ttl`) — anything else is `undeclared predicate <p> in model file` (this also catches `sh:targetClass` / `sh:deactivated` in a model file; `rdfs:seeAlso` on instances is therefore no longer accepted). A declared property linking two model members (both with `arch:inModel`) must be a trace/structure property — `aisep:approves`, `ad:relatedConcept`, `aisep:resultOf`, `ddd:payload`, `aisep:approvedBy`, `aisep:activity` and `prov:wasAssociatedWith` (v0.4), `arch:inModel`, `arch:inView`, `arch:viewConformsToViewpoint`, the qualified relationship's own `arch:source`/`arch:target`, and (added: used by the procurement example and valid fixtures) the vendored BPMN structure properties `bpmn:flowElements|default|flowNodeRefs|laneSets|lanes`, `arch:hasQualityMeasure`, `ddd:exposedAggregate` — or a direct-triple predicate (its own L1 error); otherwise `element-to-element link must be a qualified relationship`.
- **dcterms:isReplacedBy (G8, L1)**: the object must be an IRI that is an element (`arch:inModel` member) of some loaded model; otherwise L1 Violation, and it does not derive Superseded.
- Refines to a deprecated node (v0.2.1 R4, L4 Warning): an `arch:Refines` whose target is `owl:deprecated true` or has `dcterms:isReplacedBy` → "migrate the trace link to the replacing node".

## Impact vocabulary
`aisep:dependency` (annotation on a relationship CLASS, honoured only when declared in a module file — v0.2.1 R1) ∈ `aisep:Forward` (target depends on source), `aisep:Backward` (source depends on target), `aisep:Both`, `aisep:None`. Subclasses inherit unless they override. Defaults per spec §9 live in `modules/aisep-core/impact.ttl` (Composition = Both since v0.2). A module's overrides are loaded only from files its manifest lists in `aisep:impactFile`.
`impact --mode depends` (default) follows the declared direction; `--mode ripple` traverses every Forward/Backward/Both class both ways. In both modes None/undeclared classes are only listed at hop 1 as related. Default depth 3.

## Derived-only shortcut (spec §6.4)
L2 reports `[Warning] … derived-only relationship asserted` when the am4 tables permit a relationship only as a derivation (`am4rt:permits…` but not `am4rt:permitsDirect…`), unless the relationship class or a superclass carries `aisep:assertedShortcut true` **declared in a module file** (v0.2.1 R1: a model file declaring it is an L1 Violation and is not honoured).

## CLI (implemented by the aisep-core author in `tools/aisep.py`)
```
aisep.py build    [model files...]   -> build/graph.nq : sources + generated direct triples + derived aisep:notation and
                                        arch:approvalState (graph per model) ; prints counts and [Warning] build lines
                                        for ignored / ambiguous approval records
aisep.py check    [model files...]   -> L0+L1+L2 ; exit 1 on any Violation
aisep.py validate [model files...]   -> L3 per module scope (spec §10.2) on the BUILT graph ; exit 1 on Violation
aisep.py findings [model files...]   -> L4 (trace gaps: Must-priority requirements/criteria without a test; BPMN/UML
                                        nodes that are verified/implemented but reach no hub node via arch:Refines;
                                        arch:Refines to a deprecated/replaced node; isolated elements), never fails
aisep.py gate     [model files...]   -> L0..L4 ATOMICALLY on one build (check + validate + findings); one combined
                                        SUMMARY gate line (violations per layer, result=PASS|FAIL); exit 1 on any
                                        Violation in any layer (G10)
aisep.py query  FILE.rq|'SPARQL' [model files...]   -> over build graph + all ontologies + all alignments
aisep.py impact <element IRI or prefixed name> [--mode depends|ripple] [--depth N] [--allow-invalid] [model files...]
                                     -> runs L0+L1+L2 first; any Violation -> refuses (exit 1, "fix the violations or pass
                                        --allow-invalid"); with --allow-invalid prints the result plus a warning banner (G9)
aisep.py test                        -> runs every modules/*/tests and tests/acceptance/*.py ; summary table; exit 1 on failure
```
CI and pre-commit run **only** `aisep.py gate` (G10). `check` / `validate` / `findings` are partial, per-layer
diagnostics for humans: e.g. a hand-written direct triple passes `validate` (L3) and is caught only by L1, so a pipeline
that runs `validate` alone is not a gate.
Default model files = `models/**/*.ttl`. Output lines for problems start with `[Violation]`, `[Warning]`, `[Info]`. Prefixes above are pre-declared for `query`.
