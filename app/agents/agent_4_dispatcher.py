from __future__ import annotations

import os
import json
import argparse
import smtplib
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

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
# Agent 1 parsing: email/name
# ----------------------------
def extract_candidate_contact(agent1: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """
    Tries multiple common locations:
    - entities["Contact Information"] list
    - entities["contact_information"] list
    - raw_text_preview search (fallback)
    """
    entities = agent1.get("entities", {}) or {}
    contact_list = None

    # Common keys
    for k in ["Contact Information", "contact_information", "contact info", "contact"]:
        if k in entities and isinstance(entities[k], list):
            contact_list = entities[k]
            break

    email = None
    name = None

    # Try from contact list
    if contact_list:
        for item in contact_list:
            if isinstance(item, str) and "@" in item and "." in item:
                email = item.strip()
                break

    # Name: try raw_text_preview first line
    raw_preview = agent1.get("raw_text_preview", "") or ""
    if raw_preview:
        first_line = raw_preview.splitlines()[0].strip()
        if first_line:
            # Often "Name | Title"
            name = first_line.split("|")[0].strip()

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
    if agent1_file:
        story.append(Paragraph(f"<b>Resume File:</b> {agent1_file}", meta_style))
    if agent2_file:
        story.append(Paragraph(f"<b>Research File:</b> {agent2_file}", meta_style))

    story.append(Spacer(1, 0.25 * inch))

    # Section: Top 30 Q&A (group by round)
    story.append(Paragraph("Top 30 Questions with Detailed Answers", h_style))

    top_30 = agent3.get("top_30", []) or []
    # group by round
    by_round: Dict[str, List[Dict[str, Any]]] = {}
    for item in top_30:
        r = item.get("round", "Unknown Round")
        by_round.setdefault(r, []).append(item)

    for r, items in by_round.items():
        story.append(Paragraph(f"Round: {r}", h_style))
        for idx, qa in enumerate(items, start=1):
            q = qa.get("question", "").strip()
            a = qa.get("answer", "").strip()
            focus = qa.get("focus_area", "")
            diff = qa.get("difficulty", "")

            if q:
                story.append(Paragraph(f"Q{idx}. {q}", q_style))
            if focus or diff:
                tags = " | ".join([t for t in [focus, diff] if t])
                story.append(Paragraph(f"<i>{tags}</i>", meta_style))
            if a:
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
            story.append(Paragraph(f"{i}. {q}", a_style))

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
    parser = argparse.ArgumentParser(description="Agent 4: Create PDF from Agent 3 JSON and email it to candidate.")
    parser.add_argument("--agent1_json", required=True, help="Path to Agent 1 output JSON")
    parser.add_argument("--agent3_json", required=True, help="Path to Agent 3 output JSON")
    parser.add_argument("--out_dir", default="app/output", help="Directory to save PDF")
    parser.add_argument("--pdf_name", default=None, help="Optional PDF filename")
    parser.add_argument("--send_email", action="store_true", help="If set, email will be sent")

    # Email config (env-based)
    parser.add_argument("--to_email", default=None, help="Override recipient email (else extracted from Agent 1)")
    parser.add_argument("--subject", default="Your Interview Q&A Pack", help="Email subject")

    args = parser.parse_args()

    agent1 = load_json(args.agent1_json)
    agent3 = load_json(args.agent3_json)

    extracted_email, candidate_name = extract_candidate_contact(agent1)
    recipient = args.to_email or extracted_email

    if not os.path.exists(args.out_dir):
        os.makedirs(args.out_dir, exist_ok=True)

    pdf_filename = args.pdf_name or f"interview_qa_pack_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    pdf_path = os.path.join(args.out_dir, pdf_filename)

    # Create PDF
    build_pdf(agent3, pdf_path, candidate_name=candidate_name, candidate_email=recipient)

    print(json.dumps({
        "status": "pdf_created",
        "pdf_path": pdf_path,
        "candidate_name": candidate_name,
        "recipient_email": recipient
    }, indent=2))

    # Send email if requested
    if args.send_email:
        if not recipient:
            raise ValueError("No recipient email found. Provide --to_email or ensure Agent1 has an email.")

        smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        smtp_user = os.getenv("SMTP_USER", "")
        smtp_password = os.getenv("SMTP_PASSWORD", "")
        from_email = os.getenv("FROM_EMAIL", smtp_user)

        if not smtp_user or not smtp_password:
            raise EnvironmentError("Missing SMTP_USER / SMTP_PASSWORD env vars (use Gmail App Password).")

        body = (
            f"Hi {candidate_name or ''},\n\n"
            "Please find attached your Interview Q&A Pack.\n\n"
            "Thanks,\nRecruitRiders Team"
        ).strip()

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

        print(json.dumps({
            "status": "email_sent",
            "to": recipient,
            "pdf_path": pdf_path
        }, indent=2))


if __name__ == "__main__":
    main()