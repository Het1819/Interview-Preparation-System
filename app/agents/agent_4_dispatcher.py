from __future__ import annotations

import os
import re
import json
import argparse
import smtplib
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from dotenv import load_dotenv

load_dotenv()

from email.message import EmailMessage

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.enums import TA_LEFT
from reportlab.lib import colors


# ----------------------------
# Helpers: JSON IO
# ----------------------------
def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def safe_get(d: Dict[str, Any], keys: List[str], default=None):
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


# ----------------------------
# Agent 1 parsing: email/name (robust)
# ----------------------------
EMAIL_REGEX = re.compile(r"[\w\.-]+@[\w\.-]+\.\w+")


def _find_email_in_any(value: Any) -> Optional[str]:
    """Recursively search for first email in nested strings/lists/dicts."""
    if value is None:
        return None

    if isinstance(value, str):
        match = EMAIL_REGEX.search(value)
        return match.group(0).strip() if match else None

    if isinstance(value, list):
        for item in value:
            found = _find_email_in_any(item)
            if found:
                return found
        return None

    if isinstance(value, dict):
        # Try common direct keys first
        for k in ["email", "candidate_email", "recipient_email", "mail"]:
            if k in value:
                found = _find_email_in_any(value.get(k))
                if found:
                    return found
        # Then scan all values
        for v in value.values():
            found = _find_email_in_any(v)
            if found:
                return found
        return None

    return None


def extract_candidate_contact(agent1: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract candidate email + name from Agent 1 JSON.

    Priority:
    1) Top-level common keys
    2) entities (common labels + recursive fallback)
    3) raw_text_preview (email + first line name)
    4) top-level name fallback
    """
    email = None
    name = None

    # 1) Top-level direct keys
    for k in ["email", "candidate_email", "recipient_email"]:
        if k in agent1:
            email = _find_email_in_any(agent1.get(k))
            if email:
                break

    # 2) Entities search
    entities = agent1.get("entities", {}) or {}
    if not email and isinstance(entities, dict):
        # Common contact sections
        for k in [
            "Contact Information",
            "contact_information",
            "contact info",
            "contact",
            "Contact",
            "Personal Information",
            "personal_info",
        ]:
            if k in entities:
                email = _find_email_in_any(entities[k])
                if email:
                    break

        # Fallback: scan all entities
        if not email:
            email = _find_email_in_any(entities)

    # 3) raw_text_preview fallback
    raw_preview = agent1.get("raw_text_preview", "") or ""
    if raw_preview:
        lines = raw_preview.splitlines()
        first_line = lines[0].strip() if lines else ""
        if first_line:
            # Example: "Naval Dhandha | Data Analyst & Engineer"
            name = first_line.split("|")[0].strip()

        if not email:
            email = _find_email_in_any(raw_preview)

    # 4) Top-level name fallback
    if not name:
        for k in ["name", "candidate_name", "full_name"]:
            if isinstance(agent1.get(k), str) and agent1.get(k).strip():
                name = agent1[k].strip()
                break

    return email, name


# ----------------------------
# PDF Generation
# ----------------------------
def build_pdf(
    agent3: Dict[str, Any],
    out_path: str,
    candidate_name: Optional[str] = None,
    candidate_email: Optional[str] = None,
) -> str:
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "TitleStyle",
        parent=styles["Title"],
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#111111"),
        alignment=TA_LEFT,
    )

    h_style = ParagraphStyle(
        "HeaderStyle",
        parent=styles["Heading2"],
        fontSize=13,
        leading=16,
        spaceBefore=10,
        spaceAfter=6,
        textColor=colors.HexColor("#111111"),
    )

    q_style = ParagraphStyle(
        "QuestionStyle",
        parent=styles["Heading4"],
        fontSize=11,
        leading=14,
        spaceBefore=6,
        spaceAfter=4,
        textColor=colors.HexColor("#000000"),
    )

    a_style = ParagraphStyle(
        "AnswerStyle",
        parent=styles["BodyText"],
        fontSize=10,
        leading=14,
        spaceAfter=8,
        textColor=colors.HexColor("#222222"),
    )

    meta_style = ParagraphStyle(
        "MetaStyle",
        parent=styles["BodyText"],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#444444"),
    )

    doc = SimpleDocTemplate(
        out_path,
        pagesize=LETTER,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        title="Interview Q&A Pack",
    )

    story = []

    # Title
    story.append(Paragraph("Interview Q&A Pack", title_style))
    story.append(Spacer(1, 0.15 * inch))

    created_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    rounds = safe_get(agent3, ["input", "rounds"], default=[]) or []
    rounds_text = ", ".join(rounds) if rounds else "N/A"

    story.append(Paragraph(f"<b>Generated:</b> {created_at}", meta_style))
    if candidate_name:
        story.append(Paragraph(f"<b>Candidate:</b> {candidate_name}", meta_style))
    if candidate_email:
        story.append(Paragraph(f"<b>Email:</b> {candidate_email}", meta_style))
    story.append(Paragraph(f"<b>Rounds:</b> {rounds_text}", meta_style))

    agent1_file = safe_get(agent3, ["input", "agent1_file"], default=None)
    agent2_file = safe_get(agent3, ["input", "agent2_file"], default=None)
    # if agent1_file:
    #     story.append(Paragraph(f"<b>Resume File:</b> {agent1_file}", meta_style))
    # if agent2_file:
    #     story.append(Paragraph(f"<b>Research File:</b> {agent2_file}", meta_style))

    story.append(Spacer(1, 0.25 * inch))

    # Section: Top 30 Q&A (group by round)
    story.append(Paragraph("Top 30 Questions with Detailed Answers", h_style))

    top_30 = agent3.get("top_30", []) or []
    by_round: Dict[str, List[Dict[str, Any]]] = {}
    for item in top_30:
        r = item.get("round", "Unknown Round")
        by_round.setdefault(r, []).append(item)

    for round_name, items in by_round.items():
        story.append(Paragraph(f"Round: {round_name}", h_style))

        for idx, qa in enumerate(items, start=1):
            q = str(qa.get("question", "")).strip()
            a = str(qa.get("answer", "")).strip()
            focus = str(qa.get("focus_area", "")).strip()
            diff = str(qa.get("difficulty", "")).strip()

            if q:
                story.append(Paragraph(f"Q{idx}. {q}", q_style))

            if focus or diff:
                tags = " | ".join([t for t in [focus, diff] if t])
                story.append(Paragraph(f"<i>{tags}</i>", meta_style))

            if a:
                # Preserve line breaks for readable PDF output
                story.append(Paragraph(a.replace("\n", "<br/>"), a_style))

        story.append(Spacer(1, 0.1 * inch))

    story.append(PageBreak())

    # Section: Top 20 Questions List
    story.append(Paragraph("Top 20 Questions", h_style))
    top_20 = agent3.get("top_20_questions", []) or []
    if not top_20:
        story.append(Paragraph("No top_20_questions found in JSON.", meta_style))
    else:
        for i, q in enumerate(top_20, start=1):
            story.append(Paragraph(f"{i}. {str(q)}", a_style))

    # Notes
    notes = agent3.get("notes", []) or []
    if notes:
        story.append(Spacer(1, 0.25 * inch))
        story.append(Paragraph("Notes", h_style))
        for n in notes:
            story.append(Paragraph(f"- {str(n)}", a_style))

    doc.build(story)
    return out_path


# ----------------------------
# Email Sending (SMTP)
# ----------------------------
def send_email_with_attachment(
    to_email: str,
    subject: str,
    body: str,
    attachment_path: str,
    from_email: str,
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_password: str,
) -> None:
    msg = EmailMessage()
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    with open(attachment_path, "rb") as f:
        data = f.read()

    filename = os.path.basename(attachment_path)
    msg.add_attachment(data, maintype="application", subtype="pdf", filename=filename)

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(msg)


# ----------------------------
# Main CLI
# ----------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Agent 4: Create PDF from Agent 3 JSON and email it to candidate."
    )
    parser.add_argument("--agent1_json", required=True, help="Path to Agent 1 output JSON")
    parser.add_argument("--agent3_json", required=True, help="Path to Agent 3 output JSON")
    parser.add_argument("--out_dir", default="app/output", help="Directory to save PDF")
    parser.add_argument("--pdf_name", default=None, help="Optional PDF filename")
    parser.add_argument("--send_email", action="store_true", help="If set, email will be sent")

    # Email config (env-based + optional override)
    parser.add_argument(
        "--to_email",
        default=None,
        help="Override recipient email (otherwise extracted from Agent 1 resume JSON)",
    )
    parser.add_argument("--subject", default="Your Interview Q&A Pack", help="Email subject")

    args = parser.parse_args()

    # Load JSONs
    agent1 = load_json(args.agent1_json)
    agent3 = load_json(args.agent3_json)

    # Extract candidate details from Agent 1
    extracted_email, candidate_name = extract_candidate_contact(agent1)

    # CLI override takes priority, then Agent1 extracted email
    recipient = (args.to_email or extracted_email or "").strip() or None

    # Output dir
    os.makedirs(args.out_dir, exist_ok=True)

    # PDF name
    pdf_filename = args.pdf_name or f"interview_qa_pack_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    pdf_path = os.path.join(args.out_dir, pdf_filename)

    # Create PDF
    build_pdf(agent3, pdf_path, candidate_name=candidate_name, candidate_email=recipient)

    print(
        json.dumps(
            {
                "status": "pdf_created",
                "pdf_path": pdf_path,
                "candidate_name": candidate_name,
                "recipient_email": recipient,
                "email_source": "cli_override" if args.to_email else ("agent1_resume" if extracted_email else None),
            },
            indent=2,
        )
    )

    # Send email only if flag is provided
    if args.send_email:
        if not recipient:
            raise ValueError(
                "No recipient email found.\n"
                "Agent 1 did not extract a valid email from resume.\n"
                "Pass --to_email 'candidate@example.com' or improve Agent 1 contact extraction."
            )

        smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        smtp_user = os.getenv("SMTP_USER", "")
        smtp_password = os.getenv("SMTP_PASSWORD", "")
        from_email = os.getenv("FROM_EMAIL", smtp_user)

        if not smtp_user or not smtp_password:
            raise EnvironmentError(
                "Missing SMTP_USER / SMTP_PASSWORD env vars. "
                "If using Gmail, use an App Password (not your normal password)."
            )

        greeting_name = candidate_name or "Candidate"
        body = (
            f"Hi {greeting_name},\n\n"
            "Please find attached your Interview Q&A Pack.\n\n"
            "Thanks,\n"
            "RecruitRiders Team"
        )

        send_email_with_attachment(
            to_email=recipient,
            subject=args.subject,
            body=body,
            attachment_path=pdf_path,
            from_email=from_email,
            smtp_host=smtp_host,
            smtp_port=smtp_port,
            smtp_user=smtp_user,
            smtp_password=smtp_password,
        )

        print(
            json.dumps(
                {
                    "status": "email_sent",
                    "to": recipient,
                    "pdf_path": pdf_path,
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()


# ----------------------------
# Usage Examples
# ----------------------------
# Only create the PDF
# python -m app.agents.agent_4_dispatcher --agent1_json "app/output/agent1.json" --agent3_json "app/output/agent_3_output.json"

# Create PDF and send email (email extracted from Agent1 resume)
# python -m app.agents.agent_4_dispatcher --agent1_json "app/output/agent1.json" --agent3_json "app/output/agent_3_output.json" --send_email




# Create PDF and send email to manually provided recipient (fallback / override)
# python -m app.agents.agent_4_dispatcher --agent1_json "app/output/agent1.json" --agent3_json "app/output/agent_3_output.json" --send_email --to_email "candidate@example.com"