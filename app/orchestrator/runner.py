from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional

from app.orchestrator.workflow import WorkflowInput, run_interview_prep_workflow


def _parse_rounds(rounds_args: Optional[List[str]], rounds_text: Optional[str]) -> List[str]:
    """
    Supports either:
    - multiple flags: --round "Round 1..." --round "Round 2..."
    - one string: --interview_rounds "Round1; Round2; Round3"
    """
    parsed: List[str] = []

    if rounds_args:
        parsed.extend([r.strip() for r in rounds_args if str(r).strip()])

    if rounds_text:
        # split on ; or newline
        for part in rounds_text.replace("\r", "\n").split("\n"):
            for p in part.split(";"):
                p = p.strip()
                if p:
                    parsed.append(p)

    # de-dup preserve order
    seen = set()
    deduped = []
    for r in parsed:
        if r not in seen:
            seen.add(r)
            deduped.append(r)

    return deduped


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="End-to-End Interview Prep System Orchestrator Runner (Agent1 -> Agent2 -> Agent3 -> Agent4)"
    )

    # Inputs
    parser.add_argument("--resume", required=True, help="Path to candidate resume file")
    parser.add_argument("--jd", required=False, help="Path to job description file (recommended)")
    parser.add_argument("--notes", required=False, help="Optional notes/interview notes file (reserved for future)")

    # Interview rounds (two styles)
    parser.add_argument(
        "--interview_rounds",
        required=False,
        help='Semicolon-separated rounds. Example: "Round 1 - Recruiter Screen; Round 2 - Technical"',
    )
    parser.add_argument(
        "--round",
        action="append",
        dest="rounds_list",
        help='Add one round (repeatable). Example: --round "Round 1 - Recruiter Screen"',
    )

    # Research overrides (optional)
    parser.add_argument("--company", required=False, help="Company override for Agent 2 (useful if resume only)")
    parser.add_argument("--role", required=False, help="Role override for Agent 2")

    # Output / run behavior
    parser.add_argument("--output_dir", default="app/output/runs", help="Base output directory for workflow runs")
    parser.add_argument("--run_id", required=False, help="Optional custom run id")
    parser.add_argument("--pdf_mode", choices=["single", "per_round"], default="single", help="PDF generation mode")

    # Email
    parser.add_argument("--send_email", action="store_true", help="Send email with PDF attachment")
    parser.add_argument("--to_email", required=False, help="Override recipient email (fallback if Agent1 misses email)")
    parser.add_argument("--email_subject", default="Your Interview Q&A Pack", help="Email subject")

    # Verbosity / output
    parser.add_argument("--print_full_result", action="store_true", help="Print full workflow result JSON")
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    rounds = _parse_rounds(args.rounds_list, args.interview_rounds)

    if not rounds:
        parser.error(
            "Please provide interview rounds using either --interview_rounds or one/more --round arguments."
        )

    wf_input = WorkflowInput(
        resume_path=args.resume,
        jd_path=args.jd,
        notes_path=args.notes,
        interview_rounds=rounds,
        company_override=args.company,
        role_override=args.role,
        output_dir=args.output_dir,
        run_id=args.run_id,
        pdf_mode=args.pdf_mode,
        send_email=bool(args.send_email),
        to_email=args.to_email,
        email_subject=args.email_subject,
    )

    try:
        result = run_interview_prep_workflow(wf_input)
    except Exception as e:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 1

    # Concise summary
    summary = {
        "success": result.success,
        "status": result.status,
        "run_id": result.run_id,
        "run_dir": result.run_dir,
        "candidate_name": result.candidate_name,
        "candidate_email": result.candidate_email,
        "email_target": result.email_target,
        "email_sent": result.email_sent,
        "outputs": result.outputs,
        "errors": result.errors,
        "warnings": result.warnings,
        "duration_sec": result.duration_sec,
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))

    if args.print_full_result:
        print("\n[Full Workflow Result]")
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))

    # Exit code: completed/partial_success => 0, failed => 1
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())


# 1) Single command (recommended)
# python -m app.orchestrator.runner ^
#   --resume "documents\03_Test_Case_Resume.pdf" ^
#   --jd "documents\03_Test_Case_JD.pdf" ^
#   --round "Round 1 - Recruiter Screen" ^
#   --round "Round 2 - Technical (Core Skills)" ^
#   --round "Round 3 - Technical (Project + Design)" ^
#   --round "Round 4 - Hiring Manager" ^
#   --round "Round 5 - Behavioral" ^
#   --pdf_mode single


# 2) Using one --interview_rounds string
# python -m app.orchestrator.runner ^
#   --resume "documents\03_Test_Case_Resume.pdf" ^
#   --jd "documents\03_Test_Case_JD.pdf" ^
#   --interview_rounds "Round 1 - Recruiter Screen; Round 2 - Technical (Core Skills); Round 3 - Technical (Project + Design); Round 4 - Hiring Manager; Round 5 - Behavioral"


# 3) Resume only + company override
# python -m app.orchestrator.runner ^
#   --resume "documents\resume.pdf" ^
#   --company "Stripe" ^
#   --role "Data Analyst" ^
#   --interview_rounds "Round 1 - Recruiter Screen; Round 2 - Technical; Round 3 - Hiring Manager; Round 4 - Behavioral"


# 4) Email send (requires SMTP env vars)
# python -m app.orchestrator.runner ^
#   --resume "documents\resume.pdf" ^
#   --jd "documents\jd.pdf" ^
#   --interview_rounds "Round 1 - Recruiter Screen; Round 2 - Technical; Round 3 - Behavioral" ^
#   --send_email ^
#   --to_email "candidate@example.com"


# 4) Email send (requires SMTP env vars)
# python -m app.orchestrator.runner ^
#   --resume "documents\02_Test_Case_Resume.pdf" ^
#   --jd "documents\jd.pdf" ^
#   --interview_rounds "Round 1 - Recruiter Screen; Round 2 - Technical; Round 3 - Behavioral" ^
#   --send_email ^
#   --to_email "candidate@example.com"