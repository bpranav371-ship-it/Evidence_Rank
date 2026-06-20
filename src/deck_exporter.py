from __future__ import annotations

import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape


SLIDES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "EvidenceRank — Candidate Proof Engine",
        (
            "INDIA RUNS Track 1",
            "Not another résumé matcher — a proof-based candidate ranking system.",
            "CPU-only · Offline · Deterministic",
        ),
    ),
    (
        "Keyword overlap is not candidate quality",
        (
            "Self-reported skills are often treated as verified facts.",
            "Keyword stuffing can dominate simple similarity scores.",
            "Hidden gems may describe strong shipped work in plain language.",
            "Top-10 candidates need contradiction and risk protection.",
        ),
    ),
    (
        "Do not just match skills. Prove them.",
        (
            "Fingerprint: stream every profile into a compact evidence record.",
            "Verify: connect claims to titles, projects, achievements, and career text.",
            "Rank: combine relevance, proof, production depth, risk, and calibration.",
        ),
    ),
    (
        "A streaming, two-stage ranking architecture",
        (
            "Candidate Dataset → Streaming Profiler → Candidate Fingerprints",
            "Job Description → JD Parser → Candidate Proof Graph",
            "Baseline Ranker → Honeypot Firewall → Evidence Calibration",
            "Risk-Aware Final Ranking → CSV + Audits + Submission Package",
        ),
    ),
    (
        "Candidate Proof Graph separates claims from evidence",
        (
            "Supported: direct title, project, achievement, or career proof.",
            "Weakly supported: broad profile or education mention.",
            "Unsupported: claim exists without matching evidence.",
            "Every top result carries proof alignment and real snippets.",
        ),
    ),
    (
        "Honeypot Firewall protects top-rank quality",
        (
            "Zero-duration expert claims with no tenure or career proof.",
            "Dense keyword stuffing paired with weak evidence alignment.",
            "Impossible or suspicious experience and timeline patterns.",
            "Unsupported seniority and title-career contradictions.",
        ),
    ),
    (
        "Evidence calibration rewards depth, not vocabulary",
        (
            "Production depth: deployment, APIs, cloud, monitoring, and scale.",
            "Retrieval and ranking: search, embeddings, and recommendation.",
            "Evaluation: NDCG, MRR, MAP, and experimentation.",
            "Hireability remains bounded; missing behavior stays neutral.",
        ),
    ),
    (
        "Transparent scoring with bounded adjustments",
        (
            "25% JD relevance · 20% must-have skills · 25% proof alignment",
            "10% retrieval/evaluation · 10% production · 10% hireability",
            "Base score − honeypot penalty + bounded calibration = final score",
            "Every component remains visible in score_breakdown.csv.",
        ),
    ),
    (
        "Evaluation focuses on sanity and submission safety",
        (
            "Offline benchmark: {benchmark_pass}",
            "Four ablation variants and eight weight-sensitivity variants.",
            "Severe-risk, unsupported-skill, and top-10 safety checks.",
            "Final submission safety: {safety_status}",
        ),
    ),
    (
        "Every decision has a corresponding audit artifact",
        (
            "ranked_candidates.csv — final answer",
            "score_breakdown.csv — transparent component scores",
            "top_candidate_proofs.jsonl — evidence graph",
            "Risk, calibration, runtime, reproducibility, and package reports",
        ),
    ),
    (
        "Designed for practical local execution",
        (
            "Measured ranking for 5,000 fingerprints: {runtime_5k}",
            "Projected ranking for 100,000 fingerprints: {runtime_100k}",
            "Observed peak RSS: {peak_rss}",
            "No APIs, network calls, GPU, or external LLM.",
        ),
    ),
    (
        "From résumé matching to candidate proof",
        (
            "Safer top ranks",
            "Visible evidence",
            "Reproducible decisions",
            "Human review remains the final hiring decision.",
        ),
    ),
)


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _metrics(output: Path) -> dict[str, str]:
    runtime = _load_json(output / "runtime_profile_report.json")
    safety = _load_json(output / "final_submission_safety_report.json")
    benchmark = _load_json(output / "benchmark_report.json")
    seconds = runtime.get("ranking_runtime_seconds")
    projected = runtime.get("estimated_100000_candidate_ranking_seconds")
    memory = runtime.get("peak_rss_memory_mb")
    return {
        "runtime_5k": f"{float(seconds):.2f} seconds" if seconds is not None else "Not measured",
        "runtime_100k": f"{float(projected):.0f} seconds" if projected is not None else "Not measured",
        "peak_rss": f"{float(memory):.2f} MB" if memory is not None else "Not measured",
        "safety_status": "PASSED" if safety.get("passed") else "Not available",
        "benchmark_pass": (
            f"{float(benchmark.get('pass_rate', 0)):.0%} pass rate"
            if benchmark else "Not available"
        ),
    }


def _slides_from_markdown(
    docs_dir: Path,
    metrics: dict[str, str],
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    source = docs_dir / "approach_deck.md"
    if not source.exists():
        return SLIDES
    text = source.read_text(encoding="utf-8")
    matches = list(
        re.finditer(
            r"^## Slide\s+\d+\s+[—-]\s+(.+?)\s*$([\s\S]*?)(?=^---\s*$|\Z)",
            text,
            flags=re.MULTILINE,
        )
    )
    parsed: list[tuple[str, tuple[str, ...]]] = []
    for match in matches:
        title = match.group(1).strip()
        bullets = tuple(
            line[2:].strip()
            for line in match.group(2).splitlines()
            if line.startswith("- ")
        )
        if bullets:
            parsed.append((title, bullets[:5]))
    if not 10 <= len(parsed) <= 12:
        return SLIDES
    # The authored Markdown remains the narrative source; measured values make
    # the evaluation and performance slides current without editing the docs.
    for index, (title, bullets) in enumerate(parsed):
        lowered = title.lower()
        if "evaluation" in lowered:
            parsed[index] = (
                title,
                (
                    f"Offline benchmark: {metrics['benchmark_pass']}",
                    *bullets[:3],
                    f"Final submission safety: {metrics['safety_status']}",
                ),
            )
        elif "performance" in lowered:
            parsed[index] = (
                title,
                (
                    f"Measured ranking for 5,000 fingerprints: {metrics['runtime_5k']}",
                    f"Projected ranking for 100,000 fingerprints: {metrics['runtime_100k']}",
                    f"Observed peak RSS: {metrics['peak_rss']}",
                    "CPU-only, offline, and independent of external APIs.",
                ),
            )
    return tuple(parsed)


def _xml_text(value: str) -> str:
    return escape(value, {'"': "&quot;"})


def _slide_xml(title: str, bullets: tuple[str, ...], number: int) -> str:
    body_runs = []
    for index, bullet in enumerate(bullets):
        y = 2_350_000 + index * 930_000
        body_runs.append(
            f"""
            <p:sp>
              <p:nvSpPr><p:cNvPr id="{index + 4}" name="Bullet {index + 1}"/>
              <p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>
              <p:spPr><a:xfrm><a:off x="900000" y="{y}"/><a:ext cx="10300000" cy="700000"/></a:xfrm>
              <a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/><a:ln><a:noFill/></a:ln></p:spPr>
              <p:txBody><a:bodyPr anchor="ctr"/><a:lstStyle/>
                <a:p><a:r><a:rPr lang="en-US" sz="2100"><a:solidFill><a:srgbClr val="EAF4FF"/></a:solidFill></a:rPr>
                <a:t>• {_xml_text(bullet)}</a:t></a:r></a:p>
              </p:txBody>
            </p:sp>"""
        )
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
 xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
 <p:cSld><p:bg><p:bgPr><a:solidFill><a:srgbClr val="07111F"/></a:solidFill><a:effectLst/></p:bgPr></p:bg>
  <p:spTree>
   <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
   <p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
   <p:sp><p:nvSpPr><p:cNvPr id="2" name="Title"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>
    <p:spPr><a:xfrm><a:off x="700000" y="620000"/><a:ext cx="10800000" cy="900000"/></a:xfrm>
    <a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/><a:ln><a:noFill/></a:ln></p:spPr>
    <p:txBody><a:bodyPr anchor="ctr"/><a:lstStyle/><a:p><a:r><a:rPr lang="en-US" sz="3500" b="1">
    <a:solidFill><a:srgbClr val="F7FBFF"/></a:solidFill></a:rPr><a:t>{_xml_text(title)}</a:t></a:r></a:p></p:txBody>
   </p:sp>
   <p:sp><p:nvSpPr><p:cNvPr id="3" name="Kicker"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>
    <p:spPr><a:xfrm><a:off x="700000" y="280000"/><a:ext cx="3000000" cy="300000"/></a:xfrm>
    <a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/><a:ln><a:noFill/></a:ln></p:spPr>
    <p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:rPr lang="en-US" sz="1200" b="1">
    <a:solidFill><a:srgbClr val="31D6C8"/></a:solidFill></a:rPr><a:t>EVIDENCERANK</a:t></a:r></a:p></p:txBody>
   </p:sp>
   {''.join(body_runs)}
   <p:sp><p:nvSpPr><p:cNvPr id="20" name="Footer"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>
    <p:spPr><a:xfrm><a:off x="700000" y="6600000"/><a:ext cx="10800000" cy="250000"/></a:xfrm>
    <a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/><a:ln><a:noFill/></a:ln></p:spPr>
    <p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:rPr lang="en-US" sz="1000">
    <a:solidFill><a:srgbClr val="91A9BE"/></a:solidFill></a:rPr>
    <a:t>EvidenceRank | INDIA RUNS Track 1                                               {number:02d}</a:t>
    </a:r></a:p></p:txBody></p:sp>
  </p:spTree>
 </p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sld>"""


def _write_pptx(
    path: Path,
    slides_source: tuple[tuple[str, tuple[str, ...]], ...],
    metrics: dict[str, str],
    deck_config: dict[str, Any],
) -> None:
    slides = [
        (
            title.format(**metrics),
            tuple(item.format(**metrics) for item in bullets),
        )
        for title, bullets in slides_source
    ]
    content_types = "".join(
        f'<Override PartName="/ppt/slides/slide{i}.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        for i in range(1, len(slides) + 1)
    )
    structural_types = """
<Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>
<Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>
<Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>"""
    presentation_ids = "".join(
        f'<p:sldId id="{255 + i}" r:id="rId{i + 2}"/>' for i in range(1, len(slides) + 1)
    )
    presentation_rels = "".join(
        f'<Relationship Id="rId{i + 2}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" '
        f'Target="slides/slide{i}.xml"/>' for i in range(1, len(slides) + 1)
    )
    created = datetime.now(timezone.utc).isoformat()
    files = {
        "[Content_Types].xml": f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>
<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
{structural_types}{content_types}</Types>""",
        "_rels/.rels": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>""",
        "ppt/presentation.xml": f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
 xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
<p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId2"/></p:sldMasterIdLst>
<p:sldIdLst>{presentation_ids}</p:sldIdLst>
<p:sldSz cx="12192000" cy="6858000" type="screen16x9"/>
<p:notesSz cx="6858000" cy="9144000"/></p:presentation>""",
        "ppt/_rels/presentation.xml.rels": f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="theme/theme1.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/>
{presentation_rels}</Relationships>""",
        "docProps/core.xml": f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
 xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<dc:title>{_xml_text(str(deck_config.get('title', 'EvidenceRank — Candidate Proof Engine')))}</dc:title>
<dc:creator>EvidenceRank</dc:creator><dcterms:created xsi:type="dcterms:W3CDTF">{created}</dcterms:created>
</cp:coreProperties>""",
        "docProps/app.xml": f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
 xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
<Application>EvidenceRank Deck Exporter</Application><Slides>{len(slides)}</Slides></Properties>""",
        "ppt/theme/theme1.xml": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<a:theme name="EvidenceRank" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
<a:themeElements>
<a:clrScheme name="EvidenceRank">
<a:dk1><a:srgbClr val="07111F"/></a:dk1><a:lt1><a:srgbClr val="F7FBFF"/></a:lt1>
<a:dk2><a:srgbClr val="102136"/></a:dk2><a:lt2><a:srgbClr val="EAF4FF"/></a:lt2>
<a:accent1><a:srgbClr val="31D6C8"/></a:accent1><a:accent2><a:srgbClr val="58A6FF"/></a:accent2>
<a:accent3><a:srgbClr val="F6C85F"/></a:accent3><a:accent4><a:srgbClr val="FF7B72"/></a:accent4>
<a:accent5><a:srgbClr val="A9BDD0"/></a:accent5><a:accent6><a:srgbClr val="24405D"/></a:accent6>
<a:hlink><a:srgbClr val="58A6FF"/></a:hlink><a:folHlink><a:srgbClr val="A9BDD0"/></a:folHlink>
</a:clrScheme>
<a:fontScheme name="Aptos"><a:majorFont><a:latin typeface="Aptos Display"/><a:ea typeface=""/><a:cs typeface=""/></a:majorFont>
<a:minorFont><a:latin typeface="Aptos"/><a:ea typeface=""/><a:cs typeface=""/></a:minorFont></a:fontScheme>
<a:fmtScheme name="EvidenceRank">
<a:fillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:fillStyleLst>
<a:lnStyleLst><a:ln w="12700"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:prstDash val="solid"/></a:ln></a:lnStyleLst>
<a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst>
<a:bgFillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:bgFillStyleLst>
</a:fmtScheme></a:themeElements></a:theme>""",
        "ppt/slideMasters/slideMaster1.xml": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
 xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
<p:cSld name="EvidenceRank Master"><p:spTree>
<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
</p:spTree></p:cSld>
<p:clrMap accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4"
 accent5="accent5" accent6="accent6" bg1="lt1" bg2="lt2" folHlink="folHlink"
 hlink="hlink" tx1="dk1" tx2="dk2"/>
<p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst>
<p:txStyles><p:titleStyle/><p:bodyStyle/><p:otherStyle/></p:txStyles>
</p:sldMaster>""",
        "ppt/slideMasters/_rels/slideMaster1.xml.rels": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/>
</Relationships>""",
        "ppt/slideLayouts/slideLayout1.xml": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
 xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" type="blank" preserve="1">
<p:cSld name="Blank"><p:spTree>
<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sldLayout>""",
        "ppt/slideLayouts/_rels/slideLayout1.xml.rels": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/>
</Relationships>""",
    }
    for index, (title, bullets) in enumerate(slides, 1):
        files[f"ppt/slides/slide{index}.xml"] = _slide_xml(title, bullets, index)
        files[f"ppt/slides/_rels/slide{index}.xml.rels"] = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" '
            'Target="../slideLayouts/slideLayout1.xml"/></Relationships>'
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)


def _write_pdf(
    path: Path,
    slides_source: tuple[tuple[str, tuple[str, ...]], ...],
    metrics: dict[str, str],
) -> tuple[bool, str | None]:
    try:
        from reportlab.lib.colors import HexColor  # type: ignore
        from reportlab.lib.pagesizes import landscape  # type: ignore
        from reportlab.pdfgen import canvas  # type: ignore
    except ImportError:
        return False, "ReportLab is not installed."
    page = landscape((720, 405))
    pdf = canvas.Canvas(str(path), pagesize=page)
    for number, (title, bullets) in enumerate(slides_source, 1):
        pdf.setFillColor(HexColor("#07111F"))
        pdf.rect(0, 0, page[0], page[1], fill=1, stroke=0)
        pdf.setFillColor(HexColor("#31D6C8"))
        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawString(38, 376, "EVIDENCERANK")
        pdf.setFillColor(HexColor("#F7FBFF"))
        pdf.setFont("Helvetica-Bold", 22)
        pdf.drawString(38, 338, title.format(**metrics)[:78])
        y = 280
        pdf.setFont("Helvetica", 13)
        for bullet in bullets:
            text = bullet.format(**metrics)
            wrapped = re.findall(r".{1,82}(?:\s+|$)", text)
            pdf.setFillColor(HexColor("#58A6FF"))
            pdf.circle(46, y + 4, 3, fill=1, stroke=0)
            pdf.setFillColor(HexColor("#EAF4FF"))
            for line in wrapped:
                pdf.drawString(62, y, line.strip())
                y -= 18
            y -= 16
        pdf.setFillColor(HexColor("#91A9BE"))
        pdf.setFont("Helvetica", 7)
        pdf.drawString(38, 18, "EvidenceRank | INDIA RUNS Track 1")
        pdf.drawRightString(682, 18, f"{number:02d}")
        pdf.showPage()
    pdf.save()
    return True, None


def export_deck(
    docs_dir: Path | str,
    output_dir: Path | str,
    config: dict[str, Any],
    *,
    output_format: str = "pptx",
) -> dict[str, Any]:
    docs = Path(docs_dir)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    deck_config = config.get("final_deck", {})
    pptx_path = output / str(deck_config.get("pptx_name", "EvidenceRank_Approach_Deck.pptx"))
    pdf_path = output / str(deck_config.get("pdf_name", "EvidenceRank_Approach_Deck.pdf"))
    instructions_path = output / "pdf_export_instructions.txt"
    metrics = _metrics(output)
    slides_source = _slides_from_markdown(docs, metrics)
    requested = output_format.lower()
    if requested not in {"pptx", "pdf", "all"}:
        raise ValueError("--format must be pptx, pdf, or all.")
    created: dict[str, str] = {}
    warnings: list[str] = []
    if requested in {"pptx", "all"}:
        _write_pptx(pptx_path, slides_source, metrics, deck_config)
        created["pptx"] = str(pptx_path)
    if requested in {"pdf", "all"}:
        ok, warning = _write_pdf(pdf_path, slides_source, metrics)
        if ok:
            created["pdf"] = str(pdf_path)
            instructions_path.unlink(missing_ok=True)
        else:
            instructions_path.write_text(
                "PDF export requires ReportLab. Install requirements.txt, rerun "
                "`python run.py --export-deck --format pdf`, or open the PPTX and "
                "choose Export as PDF.\n",
                encoding="utf-8",
            )
            created["pdf_instructions"] = str(instructions_path)
            warnings.append(warning or "PDF export was unavailable.")
    return {
        "created_files": created,
        "warnings": warnings,
        "slide_count": len(slides_source),
        "metrics_used": metrics,
    }
