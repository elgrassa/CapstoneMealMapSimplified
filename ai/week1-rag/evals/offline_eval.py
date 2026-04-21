"""Offline eval CLI — runs GT queries through the agent + judge, offline or live.

Usage:
    python3 ai/week1-rag/evals/offline_eval.py --mode offline --fixtures fixtures/mock_llm_responses.json
    python3 ai/week1-rag/evals/offline_eval.py --mode live        # requires OPENAI_API_KEY

Writes a summary JSON and a short markdown report under `ai/week1-rag/logs/`.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

# Make sibling modules importable. THIS_DIR = ai/week1-rag/evals
THIS_DIR = Path(__file__).resolve().parent
AI_DIR = THIS_DIR.parent  # ai/week1-rag
CAPSTONE_ROOT = AI_DIR.parent.parent  # SimplifiedMealMasterCapstone
sys.path.insert(0, str(AI_DIR))
sys.path.insert(0, str(CAPSTONE_ROOT / "src"))
sys.path.insert(0, str(CAPSTONE_ROOT))

from pydantic_agent import run_agent  # noqa: E402
from agent_config import AgentConfig  # noqa: E402
from backend.services.corpus_manager import load_all_demo_indexes  # noqa: E402
from evals.llm_judge import judge_response_offline, judge_response_live, JUDGE_CRITERIA  # noqa: E402

load_all_demo_indexes()


def load_fixtures(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["offline", "live"], default="offline")
    ap.add_argument("--gt", default=str(AI_DIR / "evals" / "ground_truth_handcrafted.json"))
    ap.add_argument("--fixtures", default=str(AI_DIR.parent / "fixtures" / "mock_llm_responses.json"))
    ap.add_argument("--out", default=str(AI_DIR / "logs" / f"eval-{time.strftime('%Y%m%d-%H%M%S')}.json"))
    args = ap.parse_args()

    gt_path = Path(args.gt)
    if not gt_path.exists():
        print(f"[eval] ground truth not found at {gt_path}; exiting cleanly with 0 cases")
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps({"cases": 0, "note": "ground truth missing"}))
        return 0

    with open(gt_path, encoding="utf-8") as f:
        gt_payload = json.load(f)
    cases = gt_payload.get("cases") if isinstance(gt_payload, dict) else gt_payload

    fixtures = load_fixtures(Path(args.fixtures)) if args.mode == "offline" and Path(args.fixtures).exists() else {}

    cfg = AgentConfig.from_env()
    all_results = []
    for case in cases:
        query = case["query"]
        agent_out = run_agent(query, cfg)
        response_text = agent_out.answer
        if args.mode == "live":
            judge = judge_response_live(query, response_text)
        else:
            judge = judge_response_offline(query, response_text, fixtures)
        all_results.append({
            "query": query,
            "response": response_text,
            "evidence_tier": agent_out.evidence_tier,
            "confidence": agent_out.confidence,
            "judge_total": judge.total,
            "judge_max": judge.max,
            "judge_passed": judge.passed,
            "per_criterion": [s.model_dump() for s in judge.scores],
        })

    n = len(all_results) or 1
    summary = {
        "mode": args.mode,
        "n": len(all_results),
        "judge_pass_rate": sum(1 for r in all_results if r["judge_passed"]) / n,
        "avg_judge_total": sum(r["judge_total"] for r in all_results) / n,
        "criteria": [c["id"] for c in JUDGE_CRITERIA],
        "results": all_results,
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=2))
    print(f"[eval] wrote {out_path}  |  pass-rate={summary['judge_pass_rate']:.1%}  avg={summary['avg_judge_total']:.2f}/{len(JUDGE_CRITERIA)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
