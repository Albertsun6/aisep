"""ADM 向导（docs/specs/adm-wizard.md 第 4 节出口标准 E1–E6）。模型文件复制到 tmp_path 后再改，真实检出只读。"""
import glob, os, shutil, subprocess

import pytest

from conftest import PY, ROOT
from aisep import adm
from aisep.errors import AisepError

WB = "https://aisep.example/model/workbench/"


def copy_models(tmp_path):
    dst = tmp_path / "models"
    shutil.copytree(os.path.join(ROOT, "models"), dst)
    return dst


def files(models_dir):
    return sorted(glob.glob(os.path.join(models_dir, "**", "*.ttl"), recursive=True))


def append(path, ttl):
    with open(path, "a", encoding="utf-8") as f:
        f.write("\n" + ttl)


def sections(result):
    return {s.split(" ", 1)[0]: (inv, gaps) for s, inv, gaps in result["sections"]}


def elements(rows):
    return {r["element"] for r in rows or []}


def gap_rows(result):
    return {(c["file"], r["element"]) for _, _, gaps in result["sections"] for c, rows in gaps for r in rows}


def test_e1_business_inventory_on_workbench(tmp_path):
    r = adm.run("02-business", "workbench", files(copy_models(tmp_path)))
    s = sections(r)
    assert "workbench:governanceSubdomain" in elements(s["1."][0])  # ddd:Subdomain 算能力
    assert elements(s["4."][0]) == {"workbench:gateApprovalFlow"}  # BPMN 流程不算 am4 流程
    assert elements(s["3."][0]) == {"workbench:approverRole"}
    assert s["2."][0] == []  # 价值流：空节


def test_e2_adding_missing_realization_removes_exactly_that_gap(tmp_path):
    m = copy_models(tmp_path)
    before = gap_rows(adm.run("02-business", "workbench", files(m)))
    gap = ("02-business-11-capability-no-requirement.rq", "workbench:governanceSubdomain")
    assert gap in before
    append(m / "workbench" / "am4.ttl", f"""
<{WB}rel-governanceSubdomain-realizes-reqApprovalProgress> a <https://meta.linked.archi/archimate4/onto#Realization> ;
    <https://meta.linked.archi/core#inModel> <{WB}> ;
    <https://meta.linked.archi/core#source> <{WB}governanceSubdomain> ;
    <https://meta.linked.archi/core#target> <{WB}reqApprovalProgress> .
""")
    after = gap_rows(adm.run("02-business", "workbench", files(m)))
    assert after == before - {gap}


def test_e3_adding_value_stream_fills_empty_section(tmp_path):
    m = copy_models(tmp_path)
    append(m / "workbench" / "am4.ttl", f"""
<{WB}vsApproval> a <https://meta.linked.archi/archimate4/onto#ValueStream> ;
    <https://meta.linked.archi/core#inModel> <{WB}> ;
    <http://www.w3.org/2004/02/skos/core#prefLabel> "从改动到合入"@zh .
""")
    s = sections(adm.run("02-business", "workbench", files(m)))
    assert elements(s["2."][0]) == {"workbench:vsApproval"}


def test_e4_cli_is_deterministic_and_writes_nothing():
    status = lambda: subprocess.run(["git", "-C", ROOT, "status", "--porcelain"], capture_output=True, text=True).stdout
    cmd = [PY, os.path.join(ROOT, "tools", "aisep.py"), "adm", "02-business", "--model", "workbench", "--deliverable"]
    s0 = status()
    a, b = (subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True) for _ in range(2))
    assert a.returncode == b.returncode == 0, a.stdout + a.stderr
    assert a.stdout == b.stdout
    assert "## 6. 待决问题与风险" in a.stdout and "<!-- 人工填写" in a.stdout  # 交付物带人写节的占位
    assert status() == s0


def test_e5_roadmap_on_workbench_is_empty_and_exits_zero(tmp_path):
    s = sections(adm.run("05-roadmap", "workbench", files(copy_models(tmp_path))))
    assert s["3."][0] == s["4."][0] == s["5."][0] == []
    p = subprocess.run([PY, os.path.join(ROOT, "tools", "aisep.py"), "adm", "05-roadmap", "--model", "workbench"],
                       cwd=ROOT, capture_output=True, text=True)
    assert p.returncode == 0 and "空节 3 个" in p.stdout, p.stdout + p.stderr


@pytest.mark.parametrize("slug", ["workbench", "procurement"])
def test_e6_every_phase_runs(tmp_path, slug):
    fs = files(copy_models(tmp_path))
    for phase in adm.PHASES:
        r = adm.run(phase, slug, fs)
        assert r["problems"] == [] and r["sections"], phase
        adm.render(phase, slug, r, deliverable=True)
    assert all(c["source"] for c in adm.load_checks() if c["kind"] == "gap")
    assert {c["phase"] for c in adm.load_checks()} == set(adm.PHASES)


def test_failed_latest_result_shows_as_governance_gap(tmp_path):
    m = copy_models(tmp_path)
    key = ("governance-31-must-not-passed.rq", "workbench:acApprovedReleasePushed")
    assert key not in gap_rows(adm.run("governance", "workbench", files(m)))
    append(m / "workbench" / "verification.ttl", f"""
<{WB}trReleaseEndToEndProbe> a <https://aisep.example/ont/aisep#TestResult> ;
    <https://meta.linked.archi/core#inModel> <{WB}> ;
    <http://www.w3.org/2004/02/skos/core#prefLabel> "探针：更晚的一次失败"@zh ;
    <https://aisep.example/ont/aisep#resultOf> <{WB}tcReleaseEndToEnd> ;
    <https://aisep.example/ont/aisep#verdict> <https://aisep.example/ont/aisep#VerdictFailed> ;
    <http://www.w3.org/ns/prov#generatedAtTime> "2026-12-01T00:00:00Z"^^<http://www.w3.org/2001/XMLSchema#dateTime> .
""")
    assert key in gap_rows(adm.run("governance", "workbench", files(m)))


def test_aligned_subclasses_of_other_notations_are_not_gaps(tmp_path):
    """评审发现：bpmn:DataObject ⊑ am4:BusinessObject、ddd:Team ⊑ am4:BusinessActor，不能被当成 am4 元素报缺口。"""
    m = copy_models(tmp_path)
    append(m / "workbench" / "bpmn.ttl", f"""
<{WB}doProbe> a <https://meta.linked.archi/bpmn/onto#DataObject> ;
    <https://meta.linked.archi/core#inModel> <{WB}> ;
    <http://www.w3.org/2004/02/skos/core#prefLabel> "探针数据对象"@zh .
""")
    append(m / "workbench" / "ddd.ttl", f"""
<{WB}teamProbe> a <https://aisep.example/ont/ddd#Team> ;
    <https://meta.linked.archi/core#inModel> <{WB}> ;
    <http://www.w3.org/2004/02/skos/core#prefLabel> "探针团队"@zh .
""")
    fs = files(m)
    got = gap_rows(adm.run("03-data", "workbench", fs)) | gap_rows(adm.run("02-business", "workbench", fs))
    assert not {e for _, e in got} & {"workbench:doProbe", "workbench:teamProbe"}
    s = sections(adm.run("02-business", "workbench", fs))
    assert "workbench:teamProbe" not in elements(s["3."][0]) and "workbench:doProbe" not in elements(s["5."][0])


def test_unknown_model_and_malformed_check_are_errors(tmp_path):
    with pytest.raises(AisepError):
        adm.run("02-business", "no-such-model", files(copy_models(tmp_path)))
    d = tmp_path / "root" / "docs" / "queries" / "adm"
    d.mkdir(parents=True)
    (d / "02-business-99-bad.rq").write_text("# adm-phase: 02-business\n# section: 1. x\n# kind: gap\n# title: t\n"
                                             "SELECT ?element WHERE { VALUES ?model { <urn:x> } }\n", encoding="utf-8")
    with pytest.raises(AisepError):  # gap 缺 source
        adm.load_checks(str(tmp_path / "root"))


def test_out_refuses_models_via_symlink_or_case(tmp_path):
    """--out 不能经符号链接或改大小写写进 models/（PR #108 评审遗留）。"""
    link = tmp_path / "link"
    link.symlink_to(os.path.join(ROOT, "models"))
    base = [PY, os.path.join(ROOT, "tools", "aisep.py"), "adm", "05-roadmap", "--model", "workbench", "--out"]
    for target in (str(link / "probe.md"), os.path.join(ROOT, "Models", "probe.md")):
        p = subprocess.run(base + [target], cwd=ROOT, capture_output=True, text=True)
        assert p.returncode == 2, target + p.stdout + p.stderr
        assert not os.path.exists(os.path.join(ROOT, "models", "probe.md"))
    ok = tmp_path / "out.md"
    p = subprocess.run(base + [str(ok)], cwd=ROOT, capture_output=True, text=True)
    assert p.returncode == 0 and ok.read_text(encoding="utf-8").startswith("# 路线图"), p.stdout + p.stderr


def test_check_option_runs_only_the_given_files(tmp_path):
    """--check 只跑给出的检查项文件，可在 docs/queries/adm/ 之外；阶段不符报错（issue #128）。"""
    base = [PY, os.path.join(ROOT, "tools", "aisep.py"), "adm", "02-business", "--model", "workbench"]
    src = os.path.join(ROOT, "docs", "queries", "adm", "02-business-11-capability-no-requirement.rq")
    probe = tmp_path / "02-business-98-probe.rq"
    probe.write_text(open(src, encoding="utf-8").read().replace("# title:", "# title: 探针", 1), encoding="utf-8")
    p = subprocess.run(base + ["--check", str(probe)], cwd=ROOT, capture_output=True, text=True)
    assert p.returncode == 0, p.stdout + p.stderr
    assert "只跑了指定的检查项：`02-business-98-probe.rq`" in p.stdout
    assert "缺口：探针" in p.stdout and "workbench:governanceSubdomain" in p.stdout
    assert p.stdout.count("缺口：") == 1 and "已有" not in p.stdout  # 别的检查项（含清单查询）都没跑
    r = adm.run("02-business", "workbench", files(copy_models(tmp_path)), check_files=[src, str(probe)])
    assert r["only"] == ["02-business-11-capability-no-requirement.rq", "02-business-98-probe.rq"]
    assert len([c for _, _, gaps in r["sections"] for c, _ in gaps]) == 2
    other = os.path.join(ROOT, "docs", "queries", "adm", "01-vision-10-stakeholders.rq")
    p = subprocess.run(base + ["--check", other], cwd=ROOT, capture_output=True, text=True)
    assert p.returncode != 0 and "adm-phase 不是 02-business" in p.stderr, p.stdout + p.stderr
