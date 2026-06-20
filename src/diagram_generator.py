from __future__ import annotations

from pathlib import Path


DIAGRAMS = {
    "architecture_diagram.mmd": """flowchart TD
    A["Candidate Dataset"] --> B["Streaming Candidate Profiler"]
    B --> C["Candidate Fingerprints"]
    J["Job Description"] --> D["JD Parser"]
    C --> E["Candidate Proof Graph"]
    D --> E
    E --> F["Baseline Ranker"]
    F --> G["Honeypot Firewall"]
    G --> H["Evidence Calibration"]
    H --> I["Risk-Aware Final Ranking"]
    I --> O["CSV Output + Audit Reports + Submission Package"]
""",
    "scoring_pipeline_diagram.mmd": """flowchart LR
    A["JD Relevance"] --> S["Base Score"]
    B["Must-Have Skills"] --> S
    C["Proof Alignment"] --> S
    D["Retrieval / Evaluation Depth"] --> S
    E["Production Readiness"] --> S
    F["Hireability"] --> S
    S --> R["Subtract Honeypot Penalty"]
    R --> K["Apply Evidence Calibration"]
    K --> Z["Final Score"]
""",
    "evidence_flow_diagram.mmd": """flowchart TD
    A["Claimed Skill"] --> B["Career Evidence Search"]
    B --> C{"Evidence strength"}
    C -->|Direct career proof| D["Supported"]
    C -->|Broad profile mention| E["Weakly Supported"]
    C -->|No matching proof| F["Unsupported"]
    D --> G["Proof Alignment"]
    E --> G
    F --> G
    G --> H["Score + Explanation"]
""",
}


def generate_diagrams(docs_dir: Path | str) -> dict[str, Path]:
    target = Path(docs_dir)
    target.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for filename, content in DIAGRAMS.items():
        path = target / filename
        path.write_text(content, encoding="utf-8")
        paths[path.stem] = path
    return paths
