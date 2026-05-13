# # from __future__ import annotations

# # import os
# # import re
# # import json
# # import argparse
# # import smtplib
# # from datetime import datetime
# # from typing import Any, Dict, List, Optional, Tuple
# # from dotenv import load_dotenv
# # from xml.sax.saxutils import escape

# # load_dotenv()

# # from email.message import EmailMessage

# # from reportlab.lib.pagesizes import LETTER
# # from reportlab.lib.units import inch
# # from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
# # from reportlab.platypus import (
# #     SimpleDocTemplate,
# #     Paragraph,
# #     Spacer,
# #     PageBreak,
# #     ListFlowable,
# #     ListItem,
# #     Table,
# #     TableStyle,
# #     HRFlowable,
# #     KeepTogether,
# # )
# # from reportlab.lib.enums import TA_LEFT
# # from reportlab.lib import colors


# # # ----------------------------
# # # Helpers: JSON IO
# # # ----------------------------
# # def load_json(path: str) -> Dict[str, Any]:
# #     with open(path, "r", encoding="utf-8") as f:
# #         return json.load(f)


# # def safe_get(d: Dict[str, Any], keys: List[str], default=None):
# #     cur = d
# #     for k in keys:
# #         if not isinstance(cur, dict) or k not in cur:
# #             return default
# #         cur = cur[k]
# #     return cur


# # # ----------------------------
# # # Agent 1 parsing: email/name (robust)
# # # ----------------------------
# # EMAIL_REGEX = re.compile(r"[\w\.-]+@[\w\.-]+\.\w+")


# # def _find_email_in_any(value: Any) -> Optional[str]:
# #     """Recursively search for first email in nested strings/lists/dicts."""
# #     if value is None:
# #         return None

# #     if isinstance(value, str):
# #         match = EMAIL_REGEX.search(value)
# #         return match.group(0).strip() if match else None

# #     if isinstance(value, list):
# #         for item in value:
# #             found = _find_email_in_any(item)
# #             if found:
# #                 return found
# #         return None

# #     if isinstance(value, dict):
# #         for k in ["email", "candidate_email", "recipient_email", "mail"]:
# #             if k in value:
# #                 found = _find_email_in_any(value.get(k))
# #                 if found:
# #                     return found
# #         for v in value.values():
# #             found = _find_email_in_any(v)
# #             if found:
# #                 return found
# #         return None

# #     return None


# # def extract_candidate_contact(agent1: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
# #     """
# #     Extract candidate email + name from Agent 1 JSON.
# #     """
# #     email = None
# #     name = None

# #     for k in ["email", "candidate_email", "recipient_email"]:
# #         if k in agent1:
# #             email = _find_email_in_any(agent1.get(k))
# #             if email:
# #                 break

# #     entities = agent1.get("entities", {}) or {}
# #     if not email and isinstance(entities, dict):
# #         for k in [
# #             "Contact Information",
# #             "contact_information",
# #             "contact info",
# #             "contact",
# #             "Contact",
# #             "Personal Information",
# #             "personal_info",
# #         ]:
# #             if k in entities:
# #                 email = _find_email_in_any(entities[k])
# #                 if email:
# #                     break

# #         if not email:
# #             email = _find_email_in_any(entities)

# #     raw_preview = agent1.get("raw_text_preview", "") or ""
# #     if raw_preview:
# #         lines = raw_preview.splitlines()
# #         first_line = lines[0].strip() if lines else ""
# #         if first_line:
# #             name = first_line.split("|")[0].strip()

# #         if not email:
# #             email = _find_email_in_any(raw_preview)

# #     if not name:
# #         for k in ["name", "candidate_name", "full_name"]:
# #             if isinstance(agent1.get(k), str) and agent1.get(k).strip():
# #                 name = agent1[k].strip()
# #                 break

# #     return email, name


# # # ----------------------------
# # # Text cleaning / formatting helpers
# # # ----------------------------
# # def clean_text(text: Any) -> str:
# #     """Clean markdown-ish symbols and normalize spaces/newlines."""
# #     if text is None:
# #         return ""

# #     text = str(text).replace("\r\n", "\n").replace("\r", "\n")
# #     text = text.replace("\u2022", "- ")
# #     text = text.replace("•", "- ")

# #     # Remove markdown emphasis/code symbols
# #     text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
# #     text = re.sub(r"__(.*?)__", r"\1", text)
# #     text = re.sub(r"`([^`]*)`", r"\1", text)

# #     # Normalize repeated blank lines
# #     text = re.sub(r"\n{3,}", "\n\n", text)

# #     return text.strip()


# # def split_answer_into_blocks(answer: str) -> List[Dict[str, str]]:
# #     """
# #     Convert markdown-like answer text into structured blocks.
# #     Output blocks:
# #       {"type": "bullet", "title": "...", "body": "..."}
# #       {"type": "para", "body": "..."}
# #     """
# #     answer = clean_text(answer)
# #     if not answer:
# #         return []

# #     lines = [ln.strip() for ln in answer.split("\n") if ln.strip()]
# #     blocks: List[Dict[str, str]] = []

# #     bullet_re = re.compile(r"^[-*]\s+(.*)")
# #     numbered_re = re.compile(r"^\d+[\.\)]\s+(.*)")

# #     for line in lines:
# #         bullet_match = bullet_re.match(line)
# #         number_match = numbered_re.match(line)

# #         content = None
# #         if bullet_match:
# #             content = bullet_match.group(1).strip()
# #         elif number_match:
# #             content = number_match.group(1).strip()

# #         if content is not None:
# #             heading_match = re.match(r"^([^:]{1,80}):\s*(.*)$", content)
# #             if heading_match:
# #                 title = heading_match.group(1).strip()
# #                 body = heading_match.group(2).strip()
# #                 blocks.append({"type": "bullet", "title": title, "body": body})
# #             else:
# #                 blocks.append({"type": "bullet", "title": "", "body": content})
# #         else:
# #             blocks.append({"type": "para", "body": line})

# #     return blocks


# # def paragraph_html(text: str) -> str:
# #     """Escape text safely for ReportLab paragraph."""
# #     return escape(clean_text(text))


# # def render_answer_blocks(
# #     answer: str,
# #     bullet_style: ParagraphStyle,
# #     bullet_body_style: ParagraphStyle,
# #     para_style: ParagraphStyle,
# # ) -> List:
# #     """
# #     Turn answer string into formatted flowables.
# #     """
# #     flowables = []
# #     blocks = split_answer_into_blocks(answer)

# #     bullet_items = []

# #     for block in blocks:
# #         if block["type"] == "bullet":
# #             title = paragraph_html(block.get("title", ""))
# #             body = paragraph_html(block.get("body", ""))

# #             if title and body:
# #                 txt = f"<b>{title}:</b> {body}"
# #             elif title:
# #                 txt = f"<b>{title}</b>"
# #             else:
# #                 txt = body

# #             bullet_items.append(
# #                 ListItem(
# #                     Paragraph(txt, bullet_body_style),
# #                     leftIndent=0,
# #                 )
# #             )
# #         else:
# #             if bullet_items:
# #                 flowables.append(
# #                     ListFlowable(
# #                         bullet_items,
# #                         bulletType="bullet",
# #                         start="circle",
# #                         leftIndent=16,
# #                     )
# #                 )
# #                 flowables.append(Spacer(1, 0.06 * inch))
# #                 bullet_items = []

# #             flowables.append(Paragraph(paragraph_html(block["body"]), para_style))
# #             flowables.append(Spacer(1, 0.04 * inch))

# #     if bullet_items:
# #         flowables.append(
# #             ListFlowable(
# #                 bullet_items,
# #                 bulletType="bullet",
# #                 start="circle",
# #                 leftIndent=16,
# #             )
# #         )

# #     return flowables


# # # ----------------------------
# # # Header / Footer
# # # ----------------------------
# # def add_page_number(canvas, doc):
# #     canvas.saveState()
# #     canvas.setFont("Helvetica", 9)
# #     canvas.setFillColor(colors.HexColor("#666666"))

# #     page_num = canvas.getPageNumber()
# #     canvas.drawRightString(
# #         LETTER[0] - 0.75 * inch,
# #         0.45 * inch,
# #         f"Page {page_num}"
# #     )
# #     canvas.drawString(
# #         0.75 * inch,
# #         0.45 * inch,
# #         "Interview Q&A Pack"
# #     )
# #     canvas.restoreState()


# # # ----------------------------
# # # PDF Generation
# # # ----------------------------
# # def build_pdf(
# #     agent3: Dict[str, Any],
# #     out_path: str,
# #     candidate_name: Optional[str] = None,
# #     candidate_email: Optional[str] = None,
# # ) -> str:
# #     styles = getSampleStyleSheet()

# #     title_style = ParagraphStyle(
# #         "TitleStyle",
# #         parent=styles["Title"],
# #         fontName="Helvetica-Bold",
# #         fontSize=20,
# #         leading=24,
# #         textColor=colors.HexColor("#0F172A"),
# #         alignment=TA_LEFT,
# #         spaceAfter=8,
# #     )

# #     sub_title_style = ParagraphStyle(
# #         "SubTitleStyle",
# #         parent=styles["BodyText"],
# #         fontName="Helvetica",
# #         fontSize=10,
# #         leading=14,
# #         textColor=colors.HexColor("#475569"),
# #         spaceAfter=8,
# #     )

# #     section_style = ParagraphStyle(
# #         "SectionStyle",
# #         parent=styles["Heading2"],
# #         fontName="Helvetica-Bold",
# #         fontSize=14,
# #         leading=18,
# #         textColor=colors.HexColor("#0F172A"),
# #         spaceBefore=12,
# #         spaceAfter=8,
# #     )

# #     round_style = ParagraphStyle(
# #         "RoundStyle",
# #         parent=styles["Heading3"],
# #         fontName="Helvetica-Bold",
# #         fontSize=12,
# #         leading=16,
# #         textColor=colors.HexColor("#1D4ED8"),
# #         spaceBefore=10,
# #         spaceAfter=8,
# #     )

# #     q_style = ParagraphStyle(
# #         "QuestionStyle",
# #         parent=styles["Heading4"],
# #         fontName="Helvetica-Bold",
# #         fontSize=11.5,
# #         leading=15,
# #         textColor=colors.HexColor("#111827"),
# #         spaceBefore=8,
# #         spaceAfter=4,
# #     )

# #     tag_style = ParagraphStyle(
# #         "TagStyle",
# #         parent=styles["BodyText"],
# #         fontName="Helvetica-Oblique",
# #         fontSize=9.5,
# #         leading=12,
# #         textColor=colors.HexColor("#475569"),
# #         spaceAfter=6,
# #     )

# #     answer_para_style = ParagraphStyle(
# #         "AnswerParaStyle",
# #         parent=styles["BodyText"],
# #         fontName="Helvetica",
# #         fontSize=10.2,
# #         leading=15,
# #         textColor=colors.HexColor("#222222"),
# #         spaceAfter=4,
# #     )

# #     bullet_body_style = ParagraphStyle(
# #         "BulletBodyStyle",
# #         parent=styles["BodyText"],
# #         fontName="Helvetica",
# #         fontSize=10.2,
# #         leading=15,
# #         textColor=colors.HexColor("#222222"),
# #         leftIndent=0,
# #         spaceAfter=2,
# #     )

# #     meta_label_style = ParagraphStyle(
# #         "MetaLabelStyle",
# #         parent=styles["BodyText"],
# #         fontName="Helvetica-Bold",
# #         fontSize=9.8,
# #         leading=13,
# #         textColor=colors.HexColor("#0F172A"),
# #     )

# #     meta_value_style = ParagraphStyle(
# #         "MetaValueStyle",
# #         parent=styles["BodyText"],
# #         fontName="Helvetica",
# #         fontSize=9.8,
# #         leading=13,
# #         textColor=colors.HexColor("#334155"),
# #     )

# #     list_style = ParagraphStyle(
# #         "ListStyle",
# #         parent=styles["BodyText"],
# #         fontName="Helvetica",
# #         fontSize=10.2,
# #         leading=15,
# #         textColor=colors.HexColor("#222222"),
# #         spaceAfter=6,
# #     )

# #     doc = SimpleDocTemplate(
# #         out_path,
# #         pagesize=LETTER,
# #         rightMargin=0.70 * inch,
# #         leftMargin=0.70 * inch,
# #         topMargin=0.75 * inch,
# #         bottomMargin=0.70 * inch,
# #         title="Interview Q&A Pack",
# #         author="RecruitRiders",
# #     )

# #     story = []

# #     # Title
# #     story.append(Paragraph("Interview Q&A Pack", title_style))
# #     story.append(
# #         Paragraph(
# #             "Structured interview preparation document with clean formatting and readable answer flow.",
# #             sub_title_style,
# #         )
# #     )
# #     story.append(Spacer(1, 0.08 * inch))

# #     created_at = datetime.now().strftime("%Y-%m-%d %H:%M")
# #     rounds = safe_get(agent3, ["input", "rounds"], default=[]) or []
# #     rounds_text = ", ".join(rounds) if rounds else "N/A"

# #     meta_rows = [
# #         [
# #             Paragraph("Generated", meta_label_style),
# #             Paragraph(paragraph_html(created_at), meta_value_style),
# #         ],
# #         [
# #             Paragraph("Candidate", meta_label_style),
# #             Paragraph(paragraph_html(candidate_name or "N/A"), meta_value_style),
# #         ],
# #         [
# #             Paragraph("Email", meta_label_style),
# #             Paragraph(paragraph_html(candidate_email or "N/A"), meta_value_style),
# #         ],
# #         [
# #             Paragraph("Rounds", meta_label_style),
# #             Paragraph(paragraph_html(rounds_text), meta_value_style),
# #         ],
# #     ]

# #     meta_table = Table(meta_rows, colWidths=[1.25 * inch, 4.95 * inch])
# #     meta_table.setStyle(
# #         TableStyle(
# #             [
# #                 ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
# #                 ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#CBD5E1")),
# #                 ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#E2E8F0")),
# #                 ("VALIGN", (0, 0), (-1, -1), "TOP"),
# #                 ("LEFTPADDING", (0, 0), (-1, -1), 8),
# #                 ("RIGHTPADDING", (0, 0), (-1, -1), 8),
# #                 ("TOPPADDING", (0, 0), (-1, -1), 6),
# #                 ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
# #             ]
# #         )
# #     )

# #     story.append(meta_table)
# #     story.append(Spacer(1, 0.18 * inch))
# #     story.append(HRFlowable(width="100%", thickness=0.7, color=colors.HexColor("#CBD5E1")))
# #     story.append(Spacer(1, 0.18 * inch))

# #     # Section: Top 30 Q&A
# #     story.append(Paragraph("Top 30 Questions with Detailed Answers", section_style))

# #     top_30 = agent3.get("top_30", []) or []
# #     by_round: Dict[str, List[Dict[str, Any]]] = {}
# #     for item in top_30:
# #         r = item.get("round", "Unknown Round")
# #         by_round.setdefault(r, []).append(item)

# #     if not by_round:
# #         story.append(Paragraph("No Q&A content found.", answer_para_style))
# #     else:
# #         for round_name, items in by_round.items():
# #             story.append(Paragraph(f"Round: {paragraph_html(round_name)}", round_style))

# #             for idx, qa in enumerate(items, start=1):
# #                 q = str(qa.get("question", "")).strip()
# #                 a = str(qa.get("answer", "")).strip()
# #                 focus = str(qa.get("focus_area", "")).strip()
# #                 diff = str(qa.get("difficulty", "")).strip()

# #                 block = []

# #                 if q:
# #                     block.append(Paragraph(f"Q{idx}. {paragraph_html(q)}", q_style))

# #                 if focus or diff:
# #                     tags = "  |  ".join([t for t in [focus, diff] if t])
# #                     block.append(Paragraph(paragraph_html(tags), tag_style))

# #                 if a:
# #                     block.extend(
# #                         render_answer_blocks(
# #                             a,
# #                             bullet_style=list_style,
# #                             bullet_body_style=bullet_body_style,
# #                             para_style=answer_para_style,
# #                         )
# #                     )

# #                 block.append(Spacer(1, 0.10 * inch))
# #                 block.append(HRFlowable(width="100%", thickness=0.35, color=colors.HexColor("#E2E8F0")))
# #                 block.append(Spacer(1, 0.10 * inch))

# #                 story.append(KeepTogether(block))

# #     story.append(PageBreak())

# #     # Section: Top 20 Questions
# #     story.append(Paragraph("Top 20 Questions", section_style))
# #     top_20 = agent3.get("top_20_questions", []) or []

# #     if not top_20:
# #         story.append(Paragraph("No top_20_questions found in JSON.", answer_para_style))
# #     else:
# #         q_items = []
# #         for q in top_20:
# #             q_items.append(
# #                 ListItem(
# #                     Paragraph(paragraph_html(str(q)), list_style),
# #                     leftIndent=0,
# #                 )
# #             )
# #         story.append(
# #             ListFlowable(
# #                 q_items,
# #                 bulletType="1",
# #                 start="1",
# #                 leftIndent=18,
# #             )
# #         )

# #     # Notes
# #     notes = agent3.get("notes", []) or []
# #     if notes:
# #         story.append(Spacer(1, 0.22 * inch))
# #         story.append(Paragraph("Notes", section_style))

# #         note_items = []
# #         for n in notes:
# #             note_items.append(
# #                 ListItem(
# #                     Paragraph(paragraph_html(str(n)), list_style),
# #                     leftIndent=0,
# #                 )
# #             )

# #         story.append(
# #             ListFlowable(
# #                 note_items,
# #                 bulletType="bullet",
# #                 start="circle",
# #                 leftIndent=16,
# #             )
# #         )

# #     doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
# #     return out_path


# # # ----------------------------
# # # Email Sending (SMTP)
# # # ----------------------------
# # def send_email_with_attachment(
# #     to_email: str,
# #     subject: str,
# #     body: str,
# #     attachment_path: str,
# #     from_email: str,
# #     smtp_host: str,
# #     smtp_port: int,
# #     smtp_user: str,
# #     smtp_password: str,
# # ) -> None:
# #     msg = EmailMessage()
# #     msg["From"] = from_email
# #     msg["To"] = to_email
# #     msg["Subject"] = subject
# #     msg.set_content(body)

# #     with open(attachment_path, "rb") as f:
# #         data = f.read()

# #     filename = os.path.basename(attachment_path)
# #     msg.add_attachment(data, maintype="application", subtype="pdf", filename=filename)

# #     with smtplib.SMTP(smtp_host, smtp_port) as server:
# #         server.starttls()
# #         server.login(smtp_user, smtp_password)
# #         server.send_message(msg)


# # # ----------------------------
# # # Main CLI
# # # ----------------------------
# # def main():
# #     parser = argparse.ArgumentParser(
# #         description="Agent 4: Create PDF from Agent 3 JSON and email it to candidate."
# #     )
# #     parser.add_argument("--agent1_json", required=True, help="Path to Agent 1 output JSON")
# #     parser.add_argument("--agent3_json", required=True, help="Path to Agent 3 output JSON")
# #     parser.add_argument("--out_dir", default="app/output", help="Directory to save PDF")
# #     parser.add_argument("--pdf_name", default=None, help="Optional PDF filename")
# #     parser.add_argument("--send_email", action="store_true", help="If set, email will be sent")

# #     parser.add_argument(
# #         "--to_email",
# #         default=None,
# #         help="Override recipient email (otherwise extracted from Agent 1 resume JSON)",
# #     )
# #     parser.add_argument("--subject", default="Your Interview Q&A Pack", help="Email subject")

# #     args = parser.parse_args()

# #     agent1 = load_json(args.agent1_json)
# #     agent3 = load_json(args.agent3_json)

# #     extracted_email, candidate_name = extract_candidate_contact(agent1)
# #     recipient = (args.to_email or extracted_email or "").strip() or None

# #     os.makedirs(args.out_dir, exist_ok=True)

# #     pdf_filename = args.pdf_name or f"interview_qa_pack_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
# #     pdf_path = os.path.join(args.out_dir, pdf_filename)

# #     build_pdf(agent3, pdf_path, candidate_name=candidate_name, candidate_email=recipient)

# #     print(
# #         json.dumps(
# #             {
# #                 "status": "pdf_created",
# #                 "pdf_path": pdf_path,
# #                 "candidate_name": candidate_name,
# #                 "recipient_email": recipient,
# #                 "email_source": "cli_override" if args.to_email else ("agent1_resume" if extracted_email else None),
# #             },
# #             indent=2,
# #         )
# #     )

# #     if args.send_email:
# #         if not recipient:
# #             raise ValueError(
# #                 "No recipient email found.\n"
# #                 "Agent 1 did not extract a valid email from resume.\n"
# #                 "Pass --to_email 'candidate@example.com' or improve Agent 1 contact extraction."
# #             )

# #         smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
# #         smtp_port = int(os.getenv("SMTP_PORT", "587"))
# #         smtp_user = os.getenv("SMTP_USER", "")
# #         smtp_password = os.getenv("SMTP_PASSWORD", "")
# #         from_email = os.getenv("FROM_EMAIL", smtp_user)

# #         if not smtp_user or not smtp_password:
# #             raise EnvironmentError(
# #                 "Missing SMTP_USER / SMTP_PASSWORD env vars. "
# #                 "If using Gmail, use an App Password (not your normal password)."
# #             )

# #         greeting_name = candidate_name or "Candidate"
# #         body = (
# #             f"Hi {greeting_name},\n\n"
# #             "Please find attached your Interview Q&A Pack.\n\n"
# #             "Thanks,\n"
# #             "RecruitRiders Team"
# #         )

# #         send_email_with_attachment(
# #             to_email=recipient,
# #             subject=args.subject,
# #             body=body,
# #             attachment_path=pdf_path,
# #             from_email=from_email,
# #             smtp_host=smtp_host,
# #             smtp_port=smtp_port,
# #             smtp_user=smtp_user,
# #             smtp_password=smtp_password,
# #         )

# #         print(
# #             json.dumps(
# #                 {
# #                     "status": "email_sent",
# #                     "to": recipient,
# #                     "pdf_path": pdf_path,
# #                 },
# #                 indent=2,
# #             )
# #         )


# # if __name__ == "__main__":
# #     main()





# ##############################################################


# from __future__ import annotations

# import argparse
# import html
# import json
# import os
# import re
# import smtplib
# from datetime import datetime
# from email.message import EmailMessage
# from typing import Any, Dict, List, Optional, Tuple

# from dotenv import load_dotenv
# from reportlab.lib import colors
# from reportlab.lib.pagesizes import LETTER
# from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
# from reportlab.lib.units import inch
# from reportlab.platypus import (
#     HRFlowable,
#     ListFlowable,
#     ListItem,
#     PageBreak,
#     Paragraph,
#     SimpleDocTemplate,
#     Spacer,
#     Table,
#     TableStyle,
# )

# load_dotenv()


# # -----------------------------------------------------------------------------
# # Helpers: JSON IO
# # -----------------------------------------------------------------------------
# def load_json(path: str) -> Dict[str, Any]:
#     with open(path, "r", encoding="utf-8") as f:
#         return json.load(f)

# def validate_pdf_input(agent3: Dict[str, Any]) -> None:
#     if not isinstance(agent3, dict):
#         raise ValueError("Cannot build PDF: Agent 3 output is not a valid dictionary.")

#     if agent3.get("error"):
#         raise ValueError(f"Cannot build PDF: Agent 3 failed - {agent3.get('error')}")

#     top_30 = agent3.get("top_30")
#     top_20 = agent3.get("top_20_questions")

#     if not isinstance(top_30, list) or not top_30:
#         raise ValueError("Cannot build PDF: top_30 is empty.")

#     if not isinstance(top_20, list) or not top_20:
#         raise ValueError("Cannot build PDF: top_20_questions is empty.")

# def safe_get(d: Dict[str, Any], keys: List[str], default: Any = None) -> Any:
#     cur: Any = d
#     for k in keys:
#         if not isinstance(cur, dict) or k not in cur:
#             return default
#         cur = cur[k]
#     return cur


# # -----------------------------------------------------------------------------
# # Agent 1 parsing: email/name extraction
# # -----------------------------------------------------------------------------
# EMAIL_REGEX = re.compile(r"[\w\.-]+@[\w\.-]+\.\w+")


# def _find_email_in_any(value: Any) -> Optional[str]:
#     """Recursively search for the first email in nested strings/lists/dicts."""
#     if value is None:
#         return None

#     if isinstance(value, str):
#         match = EMAIL_REGEX.search(value)
#         return match.group(0).strip() if match else None

#     if isinstance(value, list):
#         for item in value:
#             found = _find_email_in_any(item)
#             if found:
#                 return found
#         return None

#     if isinstance(value, dict):
#         # Prefer direct contact-like fields first.
#         for k in ["email", "candidate_email", "recipient_email", "mail"]:
#             if k in value:
#                 found = _find_email_in_any(value.get(k))
#                 if found:
#                     return found

#         # Fallback: scan every nested value.
#         for v in value.values():
#             found = _find_email_in_any(v)
#             if found:
#                 return found
#         return None

#     return None


# def extract_candidate_contact(agent1: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
#     """Extract candidate email and name from Agent 1 JSON."""
#     email: Optional[str] = None
#     name: Optional[str] = None

#     for k in ["email", "candidate_email", "recipient_email"]:
#         if k in agent1:
#             email = _find_email_in_any(agent1.get(k))
#             if email:
#                 break

#     entities = agent1.get("entities", {}) or {}
#     if not email and isinstance(entities, dict):
#         for k in [
#             "Contact Information",
#             "contact_information",
#             "contact info",
#             "contact",
#             "Contact",
#             "Personal Information",
#             "personal_info",
#         ]:
#             if k in entities:
#                 email = _find_email_in_any(entities[k])
#                 if email:
#                     break

#         if not email:
#             email = _find_email_in_any(entities)

#     raw_preview = agent1.get("raw_text_preview", "") or ""
#     if raw_preview:
#         lines = raw_preview.splitlines()
#         first_line = lines[0].strip() if lines else ""
#         if first_line:
#             name = first_line.split("|")[0].strip()

#         if not email:
#             email = _find_email_in_any(raw_preview)

#     if not name:
#         for k in ["name", "candidate_name", "full_name"]:
#             if isinstance(agent1.get(k), str) and agent1.get(k).strip():
#                 name = agent1[k].strip()
#                 break

#     return email, name


# # -----------------------------------------------------------------------------
# # PDF design constants
# # -----------------------------------------------------------------------------
# _NAVY = colors.HexColor("#0F172A")
# _BLUE = colors.HexColor("#1D4ED8")
# _BLUE_LIGHT = colors.HexColor("#EFF6FF")
# _BLUE_MID = colors.HexColor("#BFDBFE")
# _SLATE = colors.HexColor("#475569")
# _SLATE_LIGHT = colors.HexColor("#F1F5F9")
# _BORDER = colors.HexColor("#CBD5E1")
# _BORDER_LITE = colors.HexColor("#E2E8F0")
# _TEXT_DARK = colors.HexColor("#111827")
# _TEXT_BODY = colors.HexColor("#1E293B")
# _CARD_BG = colors.HexColor("#F8FAFC")
# _WHITE = colors.white

# _EASY_BG = colors.HexColor("#DCFCE7")
# _EASY_FG = colors.HexColor("#166534")
# _MED_BG = colors.HexColor("#FEF9C3")
# _MED_FG = colors.HexColor("#854D0E")
# _HARD_BG = colors.HexColor("#FEE2E2")
# _HARD_FG = colors.HexColor("#991B1B")

# _DIFF_ACCENT: Dict[str, Any] = {
#     "easy": colors.HexColor("#22C55E"),
#     "medium": colors.HexColor("#EAB308"),
#     "hard": colors.HexColor("#EF4444"),
# }
# _DIFF_BADGE: Dict[str, Tuple[Any, Any]] = {
#     "easy": (_EASY_BG, _EASY_FG),
#     "medium": (_MED_BG, _MED_FG),
#     "hard": (_HARD_BG, _HARD_FG),
# }


# # -----------------------------------------------------------------------------
# # Text cleaning / formatting helpers
# # -----------------------------------------------------------------------------
# def _esc(text: Any) -> str:
#     """Escape plain text for ReportLab Paragraph HTML."""
#     return html.escape(str(text), quote=False)


# def clean_text(text: Any) -> str:
#     """Clean markdown-ish symbols while preserving readable answer structure."""
#     if text is None:
#         return ""

#     value = str(text).replace("\r\n", "\n").replace("\r", "\n")
#     value = value.replace("\u2022", "- ").replace("•", "- ")

#     # Remove common Markdown emphasis/code wrappers.
#     value = re.sub(r"\*\*(.*?)\*\*", r"\1", value)
#     value = re.sub(r"__(.*?)__", r"\1", value)
#     value = re.sub(r"`([^`]*)`", r"\1", value)

#     # Normalize bullets that came back as long dashes or strange symbols.
#     value = re.sub(r"^[\s]*[–—]\s+", "- ", value, flags=re.MULTILINE)

#     # Keep paragraph separation but remove excessive empty lines.
#     value = re.sub(r"\n{3,}", "\n\n", value)
#     return value.strip()


# def split_answer_into_blocks(answer: Any) -> List[Dict[str, str]]:
#     """
#     Convert answer text into structured blocks:
#       {"type": "bullet", "title": "...", "body": "..."}
#       {"type": "para", "body": "..."}
#     """
#     answer = clean_text(answer)
#     if not answer:
#         return []

#     bullet_re = re.compile(r"^[-*]\s+(.*)")
#     numbered_re = re.compile(r"^\d+[\.)]\s+(.*)")

#     blocks: List[Dict[str, str]] = []
#     para_buffer: List[str] = []

#     def flush_para() -> None:
#         nonlocal para_buffer
#         if para_buffer:
#             blocks.append({"type": "para", "body": " ".join(para_buffer).strip()})
#             para_buffer = []

#     for raw_line in answer.split("\n"):
#         line = raw_line.strip()
#         if not line:
#             flush_para()
#             continue

#         bullet_match = bullet_re.match(line)
#         number_match = numbered_re.match(line)

#         content: Optional[str] = None
#         if bullet_match:
#             content = bullet_match.group(1).strip()
#         elif number_match:
#             content = number_match.group(1).strip()

#         if content is not None:
#             flush_para()
#             heading_match = re.match(r"^([^:]{1,80}):\s*(.*)$", content)
#             if heading_match:
#                 blocks.append(
#                     {
#                         "type": "bullet",
#                         "title": heading_match.group(1).strip(),
#                         "body": heading_match.group(2).strip(),
#                     }
#                 )
#             else:
#                 blocks.append({"type": "bullet", "title": "", "body": content})
#         else:
#             para_buffer.append(line)

#     flush_para()
#     return blocks


# def _normalize_difficulty(diff: Any) -> str:
#     value = clean_text(diff).lower()
#     if value in {"easy", "medium", "hard"}:
#         return value
#     return "medium"


# def _question_text(item: Any) -> str:
#     if isinstance(item, dict):
#         for key in ["question", "text", "title"]:
#             if item.get(key):
#                 return clean_text(item.get(key))
#         return clean_text(json.dumps(item, ensure_ascii=False))
#     return clean_text(item)


# def _select_answer(qa: Dict[str, Any], answer_key: Optional[str]) -> str:
#     """
#     Pick the answer version requested by agent3.input.answer_length.
#     Falls back safely for older Agent 3 outputs that only have `answer`.
#     """
#     candidate_keys = []
#     if answer_key:
#         candidate_keys.append(answer_key)

#     candidate_keys.extend([
#         "answer",
#         "answer_medium",
#         "answer_large",
#         "answer_small",
#     ])

#     for key in candidate_keys:
#         value = qa.get(key)
#         if isinstance(value, str) and value.strip():
#             return value.strip()

#     return ""


# # -----------------------------------------------------------------------------
# # Page header / footer
# # -----------------------------------------------------------------------------
# def _header_footer(canvas, doc) -> None:
#     canvas.saveState()
#     page_width, _ = LETTER

#     canvas.setStrokeColor(_BORDER)
#     canvas.setLineWidth(0.5)
#     canvas.line(0.70 * inch, 0.55 * inch, page_width - 0.70 * inch, 0.55 * inch)

#     canvas.setFont("Helvetica", 8)
#     canvas.setFillColor(_SLATE)
#     canvas.drawString(0.70 * inch, 0.38 * inch, "Interview Q&A Pack  |  RecruitRiders")
#     canvas.drawRightString(page_width - 0.70 * inch, 0.38 * inch, f"Page {doc.page}")
#     canvas.restoreState()


# # -----------------------------------------------------------------------------
# # PDF card builders
# # -----------------------------------------------------------------------------
# def _difficulty_badge(diff: str) -> str:
#     bg, fg = _DIFF_BADGE.get(diff, _DIFF_BADGE["medium"])
#     # ReportLab Paragraph does not support rounded pill backgrounds reliably.
#     # So we use a readable color label and keep the real color cue in the card accent.
#     _ = bg
#     return f'<font color="{fg.hexval()}"><b>{diff.capitalize()}</b></font>'


# def _answer_flowables(answer: str, answer_style: ParagraphStyle) -> List[Paragraph]:
#     blocks = split_answer_into_blocks(answer)
#     if not blocks:
#         return [Paragraph("No answer found.", answer_style)]

#     rendered: List[Paragraph] = []
#     for block in blocks:
#         if block["type"] == "bullet":
#             title = _esc(block.get("title", ""))
#             body = _esc(block.get("body", ""))
#             if title and body:
#                 text = f'<font color="#1D4ED8">&#8226;</font>&nbsp; <b>{title}:</b> {body}'
#             elif title:
#                 text = f'<font color="#1D4ED8">&#8226;</font>&nbsp; <b>{title}</b>'
#             else:
#                 text = f'<font color="#1D4ED8">&#8226;</font>&nbsp; {body}'
#         else:
#             text = _esc(block.get("body", ""))

#         rendered.append(Paragraph(text, answer_style))

#     return rendered


# def _question_card(
#     idx: int,
#     qa: Dict[str, Any],
#     answer_key: Optional[str],
#     page_width: float,
#     styles: Dict[str, ParagraphStyle],
# ) -> Table:
#     question = clean_text(qa.get("question", ""))
#     answer = _select_answer(qa, answer_key)
#     focus = clean_text(qa.get("focus_area", ""))
#     diff = _normalize_difficulty(qa.get("difficulty", ""))
#     accent = _DIFF_ACCENT.get(diff, _DIFF_ACCENT["medium"])

#     rows: List[List[Any]] = []
#     rows.append([
#         Paragraph(
#             f'<font color="#1D4ED8"><b>Q{idx}.</b></font>&nbsp; <b>{_esc(question or "Question not available")}</b>',
#             styles["question"],
#         )
#     ])

#     tag_parts = []
#     if focus:
#         tag_parts.append(f'<b>Focus:</b> {_esc(focus)}')
#     tag_parts.append(f'<b>Difficulty:</b> {_difficulty_badge(diff)}')
#     rows.append([Paragraph(" &nbsp;&nbsp; | &nbsp;&nbsp; ".join(tag_parts), styles["tag"])])

#     answer_start = len(rows)
#     for para in _answer_flowables(answer, styles["answer"]):
#         rows.append([para])

#     table = Table(rows, colWidths=[page_width], splitByRow=1)
#     table.setStyle(
#         TableStyle(
#             [
#                 ("BACKGROUND", (0, 0), (-1, -1), _CARD_BG),
#                 ("BOX", (0, 0), (-1, -1), 0.6, _BORDER),
#                 ("LINEBEFORE", (0, 0), (0, -1), 5, accent),
#                 ("LINEABOVE", (0, answer_start), (0, answer_start), 0.4, _BORDER_LITE),
#                 ("VALIGN", (0, 0), (-1, -1), "TOP"),
#                 ("LEFTPADDING", (0, 0), (-1, -1), 14),
#                 ("RIGHTPADDING", (0, 0), (-1, -1), 12),
#                 ("TOPPADDING", (0, 0), (-1, 0), 10),
#                 ("BOTTOMPADDING", (0, 0), (-1, 0), 7),
#                 ("TOPPADDING", (0, 1), (-1, 1), 4),
#                 ("BOTTOMPADDING", (0, 1), (-1, 1), 8),
#                 ("TOPPADDING", (0, answer_start), (-1, -1), 5),
#                 ("BOTTOMPADDING", (0, answer_start), (-1, -1), 4),
#             ]
#         )
#     )
#     return table


# def _paragraph_list(items: List[Any], style: ParagraphStyle) -> ListFlowable:
#     return ListFlowable(
#         [ListItem(Paragraph(_esc(_question_text(item)), style), leftIndent=0) for item in items],
#         bulletType="1",
#         start="1",
#         leftIndent=18,
#     )


# # -----------------------------------------------------------------------------
# # PDF Generation
# # -----------------------------------------------------------------------------
# def build_pdf(
#     agent3: Dict[str, Any],
#     out_path: str,
#     candidate_name: Optional[str] = None,
#     candidate_email: Optional[str] = None,
# ) -> str:
#     validate_pdf_input(agent3)
#     """
#     Generate a clean, candidate-friendly Interview Q&A Pack PDF.

#     This version keeps the existing Agent 4 function signature, but improves:
#       - cover page
#       - metadata block
#       - grouped rounds
#       - card-based Q&A layout
#       - answer version selection via input.answer_length
#       - top-20 quick reference section
#       - safer long-answer handling than a single non-splittable custom Flowable
#     """
#     base = getSampleStyleSheet()
    

#     def s(name: str, **kwargs: Any) -> ParagraphStyle:
#         parent = kwargs.pop("parent", base["Normal"])
#         return ParagraphStyle(name, parent=parent, **kwargs)

#     styles = {
#         "cover_title": s(
#             "CoverTitle",
#             fontName="Helvetica-Bold",
#             fontSize=28,
#             leading=34,
#             textColor=_WHITE,
#             spaceAfter=6,
#         ),
#         "cover_sub": s(
#             "CoverSub",
#             fontName="Helvetica",
#             fontSize=12,
#             leading=17,
#             textColor=_BLUE_MID,
#         ),
#         "section": s(
#             "SectionHead",
#             fontName="Helvetica-Bold",
#             fontSize=15,
#             leading=20,
#             textColor=_NAVY,
#             spaceBefore=14,
#             spaceAfter=10,
#         ),
#         "round": s(
#             "RoundLabel",
#             fontName="Helvetica-Bold",
#             fontSize=12,
#             leading=16,
#             textColor=_BLUE,
#         ),
#         "meta_label": s(
#             "MetaLabel",
#             fontName="Helvetica-Bold",
#             fontSize=9.5,
#             leading=14,
#             textColor=_NAVY,
#         ),
#         "meta_value": s(
#             "MetaValue",
#             fontName="Helvetica",
#             fontSize=9.5,
#             leading=14,
#             textColor=colors.HexColor("#334155"),
#         ),
#         "body": s(
#             "Body",
#             fontName="Helvetica",
#             fontSize=10.2,
#             leading=15.5,
#             textColor=_TEXT_BODY,
#             spaceAfter=4,
#         ),
#         "note": s(
#             "Note",
#             fontName="Helvetica",
#             fontSize=9.8,
#             leading=14.5,
#             textColor=_SLATE,
#             spaceAfter=3,
#         ),
#         "question": s(
#             "Question",
#             fontName="Helvetica-Bold",
#             fontSize=11.2,
#             leading=15.5,
#             textColor=_TEXT_DARK,
#         ),
#         "tag": s(
#             "Tag",
#             fontName="Helvetica",
#             fontSize=9.3,
#             leading=13,
#             textColor=_SLATE,
#         ),
#         "answer": s(
#             "Answer",
#             fontName="Helvetica",
#             fontSize=10.1,
#             leading=15.2,
#             textColor=_TEXT_BODY,
#         ),
#     }

#     left_margin = right_margin = 0.70 * inch
#     usable_width = LETTER[0] - left_margin - right_margin

#     doc = SimpleDocTemplate(
#         out_path,
#         pagesize=LETTER,
#         leftMargin=left_margin,
#         rightMargin=right_margin,
#         topMargin=0.75 * inch,
#         bottomMargin=0.80 * inch,
#         title="Interview Q&A Pack",
#         author="RecruitRiders",
#     )

#     story: List[Any] = []

#     created_at = datetime.now().strftime("%B %d, %Y | %H:%M")
#     rounds = safe_get(agent3, ["input", "rounds"], default=[]) or []
#     rounds_text = ", ".join(map(str, rounds)) if rounds else "N/A"
#     answer_key = safe_get(agent3, ["input", "answer_length"], default=None)
#     doc_type = safe_get(agent3, ["input", "doc_type"], default="N/A")

#     top_30 = agent3.get("top_30", []) or []
#     top_20 = agent3.get("top_20_questions", []) or []
#     notes = agent3.get("notes", []) or []
#     if isinstance(notes, str):
#         notes = [notes]

#     # Cover banner
#     cover_table = Table(
#         [
#             [
#                 [
#                     Paragraph("Interview Q&A Pack", styles["cover_title"]),
#                     Paragraph(
#                         f"Structured preparation document | Tailored answers | {_esc(rounds_text)}",
#                         styles["cover_sub"],
#                     ),
#                     Spacer(1, 0.16 * inch),
#                 ]
#             ]
#         ],
#         colWidths=[usable_width],
#     )
#     cover_table.setStyle(
#         TableStyle(
#             [
#                 ("BACKGROUND", (0, 0), (-1, -1), _NAVY),
#                 ("TOPPADDING", (0, 0), (-1, -1), 22),
#                 ("BOTTOMPADDING", (0, 0), (-1, -1), 22),
#                 ("LEFTPADDING", (0, 0), (-1, -1), 20),
#                 ("RIGHTPADDING", (0, 0), (-1, -1), 20),
#             ]
#         )
#     )
#     story.append(cover_table)
#     story.append(Spacer(1, 0.18 * inch))

#     # Metadata card
#     meta_rows = [
#         [Paragraph("Candidate", styles["meta_label"]), Paragraph(_esc(candidate_name or "N/A"), styles["meta_value"])],
#         [Paragraph("Email", styles["meta_label"]), Paragraph(_esc(candidate_email or "N/A"), styles["meta_value"])],
#         [Paragraph("Round(s)", styles["meta_label"]), Paragraph(_esc(rounds_text), styles["meta_value"])],
#         [Paragraph("Answer Length", styles["meta_label"]), Paragraph(_esc(answer_key or "answer"), styles["meta_value"])],
#         [Paragraph("Document Type", styles["meta_label"]), Paragraph(_esc(doc_type), styles["meta_value"])],
#         [Paragraph("Generated", styles["meta_label"]), Paragraph(_esc(created_at), styles["meta_value"])],
#     ]
#     meta_table = Table(meta_rows, colWidths=[1.25 * inch, usable_width - 1.25 * inch])
#     meta_table.setStyle(
#         TableStyle(
#             [
#                 ("BACKGROUND", (0, 0), (-1, -1), _SLATE_LIGHT),
#                 ("BOX", (0, 0), (-1, -1), 0.6, _BORDER),
#                 ("INNERGRID", (0, 0), (-1, -1), 0.35, _BORDER_LITE),
#                 ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
#                 ("LEFTPADDING", (0, 0), (-1, -1), 10),
#                 ("RIGHTPADDING", (0, 0), (-1, -1), 10),
#                 ("TOPPADDING", (0, 0), (-1, -1), 7),
#                 ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
#             ]
#         )
#     )
#     story.append(meta_table)
#     story.append(Spacer(1, 0.22 * inch))

#     # Contents
#     story.append(HRFlowable(width="100%", thickness=0.7, color=_BORDER))
#     story.append(Spacer(1, 0.12 * inch))
#     story.append(Paragraph("Contents", styles["section"]))

#     toc_rows = [
#         [Paragraph("Section", styles["meta_label"]), Paragraph("Description", styles["meta_label"])],
#         [Paragraph("Top 30 Q&A", styles["meta_label"]), Paragraph("Detailed questions with structured answers, focus tags, and difficulty markers", styles["meta_value"])],
#         [Paragraph("Top 20 Questions", styles["meta_label"]), Paragraph("Quick-reference list of the most important questions", styles["meta_value"])],
#         [Paragraph("Notes", styles["meta_label"]), Paragraph("Generation notes and additional context, when available", styles["meta_value"])],
#     ]
#     toc_table = Table(toc_rows, colWidths=[1.7 * inch, usable_width - 1.7 * inch])
#     toc_table.setStyle(
#         TableStyle(
#             [
#                 ("BACKGROUND", (0, 0), (-1, 0), _NAVY),
#                 ("TEXTCOLOR", (0, 0), (-1, 0), _WHITE),
#                 ("BACKGROUND", (0, 1), (-1, -1), colors.white),
#                 ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _SLATE_LIGHT]),
#                 ("BOX", (0, 0), (-1, -1), 0.6, _BORDER),
#                 ("INNERGRID", (0, 0), (-1, -1), 0.35, _BORDER_LITE),
#                 ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
#                 ("LEFTPADDING", (0, 0), (-1, -1), 10),
#                 ("RIGHTPADDING", (0, 0), (-1, -1), 10),
#                 ("TOPPADDING", (0, 0), (-1, -1), 7),
#                 ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
#             ]
#         )
#     )
#     story.append(toc_table)
#     story.append(Spacer(1, 0.10 * inch))
#     story.append(
#         Paragraph(
#             '<b>Difficulty key:</b> '
#             '<font color="#166534">Easy</font> | '
#             '<font color="#854D0E">Medium</font> | '
#             '<font color="#991B1B">Hard</font>',
#             styles["note"],
#         )
#     )
#     story.append(PageBreak())

#     # Top 30 Q&A section
#     story.append(Paragraph("Top 30 Questions with Detailed Answers", styles["section"]))

#     by_round: Dict[str, List[Dict[str, Any]]] = {}
#     for item in top_30:
#         if isinstance(item, dict):
#             round_name = clean_text(item.get("round", "Unknown Round")) or "Unknown Round"
#             by_round.setdefault(round_name, []).append(item)

#     if not by_round:
#         story.append(Paragraph("No Q&amp;A content found.", styles["body"]))
#     else:
#         global_idx = 1
#         for round_name, items in by_round.items():
#             round_table = Table(
#                 [[Paragraph(f"Round: {_esc(round_name)}", styles["round"])]],
#                 colWidths=[usable_width],
#             )
#             round_table.setStyle(
#                 TableStyle(
#                     [
#                         ("BACKGROUND", (0, 0), (-1, -1), _BLUE_LIGHT),
#                         ("BOX", (0, 0), (-1, -1), 0.6, _BLUE_MID),
#                         ("TOPPADDING", (0, 0), (-1, -1), 8),
#                         ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
#                         ("LEFTPADDING", (0, 0), (-1, -1), 12),
#                         ("RIGHTPADDING", (0, 0), (-1, -1), 12),
#                     ]
#                 )
#             )
#             story.append(round_table)
#             story.append(Spacer(1, 0.12 * inch))

#             for qa in items:
#                 story.append(_question_card(global_idx, qa, answer_key, usable_width, styles))
#                 story.append(Spacer(1, 0.13 * inch))
#                 global_idx += 1

#     story.append(PageBreak())

#     # Top 20 quick reference section
#     story.append(Paragraph("Top 20 Questions - Quick Reference", styles["section"]))
#     story.append(Paragraph("Review these questions before the interview for a final confidence check.", styles["note"]))
#     story.append(Spacer(1, 0.10 * inch))

#     if not top_20:
#         story.append(Paragraph("No top_20_questions found.", styles["body"]))
#     else:
#         # Two-column grid for compact readability.
#         col_width = (usable_width - 0.15 * inch) / 2
#         grid_rows: List[List[Any]] = []
#         for i in range(0, len(top_20), 2):
#             left = _question_text(top_20[i])
#             right = _question_text(top_20[i + 1]) if i + 1 < len(top_20) else ""
#             grid_rows.append(
#                 [
#                     Paragraph(f"<b>{i + 1}.</b> {_esc(left)}", styles["body"]),
#                     Paragraph(f"<b>{i + 2}.</b> {_esc(right)}", styles["body"]) if right else Paragraph("", styles["body"]),
#                 ]
#             )
#         grid_table = Table(grid_rows, colWidths=[col_width, col_width], splitByRow=1)
#         grid_table.setStyle(
#             TableStyle(
#                 [
#                     ("VALIGN", (0, 0), (-1, -1), "TOP"),
#                     ("LEFTPADDING", (0, 0), (-1, -1), 10),
#                     ("RIGHTPADDING", (0, 0), (-1, -1), 10),
#                     ("TOPPADDING", (0, 0), (-1, -1), 7),
#                     ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
#                     ("BOX", (0, 0), (-1, -1), 0.5, _BORDER),
#                     ("INNERGRID", (0, 0), (-1, -1), 0.3, _BORDER_LITE),
#                     ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, _SLATE_LIGHT]),
#                 ]
#             )
#         )
#         story.append(grid_table)

#     # Notes section
#     if notes:
#         story.append(Spacer(1, 0.25 * inch))
#         story.append(HRFlowable(width="100%", thickness=0.6, color=_BORDER))
#         story.append(Spacer(1, 0.12 * inch))
#         story.append(Paragraph("Notes", styles["section"]))
#         story.append(
#             ListFlowable(
#                 [ListItem(Paragraph(_esc(str(n)), styles["note"]), leftIndent=0) for n in notes],
#                 bulletType="bullet",
#                 start="square",
#                 leftIndent=14,
#             )
#         )

#     doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
#     return out_path


# # -----------------------------------------------------------------------------
# # Email Sending (SMTP)
# # -----------------------------------------------------------------------------
# def send_email_with_attachment(
#     to_email: str,
#     subject: str,
#     body: str,
#     attachment_path: str,
#     from_email: str,
#     smtp_host: str,
#     smtp_port: int,
#     smtp_user: str,
#     smtp_password: str,
# ) -> None:
#     msg = EmailMessage()
#     msg["From"] = from_email
#     msg["To"] = to_email
#     msg["Subject"] = subject
#     msg.set_content(body)

#     with open(attachment_path, "rb") as f:
#         data = f.read()

#     filename = os.path.basename(attachment_path)
#     msg.add_attachment(data, maintype="application", subtype="pdf", filename=filename)

#     if smtp_port == 465:
#         with smtplib.SMTP_SSL(smtp_host, smtp_port) as server:
#             server.login(smtp_user, smtp_password)
#             server.send_message(msg)
#     else:
#         with smtplib.SMTP(smtp_host, smtp_port) as server:
#             server.starttls()
#             server.login(smtp_user, smtp_password)
#             server.send_message(msg)
#     # with smtplib.SMTP(smtp_host, smtp_port) as server:
#     #     server.starttls()
#         # server.login(smtp_user, smtp_password)
#         # server.send_message(msg)


# # -----------------------------------------------------------------------------
# # Main CLI
# # -----------------------------------------------------------------------------
# def main() -> None:
#     parser = argparse.ArgumentParser(
#         description="Agent 4: Create PDF from Agent 3 JSON and optionally email it to the candidate."
#     )
#     parser.add_argument("--agent1_json", required=True, help="Path to Agent 1 output JSON")
#     parser.add_argument("--agent3_json", required=True, help="Path to Agent 3 output JSON")
#     parser.add_argument("--out_dir", default="app/output", help="Directory to save PDF")
#     parser.add_argument("--pdf_name", default=None, help="Optional PDF filename")
#     parser.add_argument("--send_email", action="store_true", help="If set, email will be sent")

#     parser.add_argument(
#         "--to_email",
#         default=None,
#         help="Override recipient email, otherwise extracted from Agent 1 resume JSON",
#     )
#     parser.add_argument("--subject", default="Your Interview Q&A Pack", help="Email subject")

#     args = parser.parse_args()

#     agent1 = load_json(args.agent1_json)
#     agent3 = load_json(args.agent3_json)

#     extracted_email, candidate_name = extract_candidate_contact(agent1)
#     recipient = (args.to_email or extracted_email or "").strip() or None

#     os.makedirs(args.out_dir, exist_ok=True)

#     pdf_filename = args.pdf_name or f"interview_qa_pack_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
#     pdf_path = os.path.join(args.out_dir, pdf_filename)

#     build_pdf(agent3, pdf_path, candidate_name=candidate_name, candidate_email=recipient)

#     print(
#         json.dumps(
#             {
#                 "status": "pdf_created",
#                 "pdf_path": pdf_path,
#                 "candidate_name": candidate_name,
#                 "recipient_email": recipient,
#                 "email_source": "cli_override" if args.to_email else ("agent1_resume" if extracted_email else None),
#             },
#             indent=2,
#         )
#     )

#     if args.send_email:
#         if not recipient:
#             raise ValueError(
#                 "No recipient email found.\n"
#                 "Agent 1 did not extract a valid email from resume.\n"
#                 "Pass --to_email 'candidate@example.com' or improve Agent 1 contact extraction."
#             )

#         smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
#         smtp_port = int(os.getenv("SMTP_PORT", "587"))
#         smtp_user = os.getenv("SMTP_USER", "")
#         smtp_password = os.getenv("SMTP_PASSWORD", "")
#         from_email = os.getenv("FROM_EMAIL", smtp_user)

#         if not smtp_user or not smtp_password:
#             raise EnvironmentError(
#                 "Missing SMTP_USER / SMTP_PASSWORD env vars. "
#                 "If using Gmail, use an App Password instead of your normal password."
#             )

#         greeting_name = candidate_name or "Candidate"
#         body = (
#             f"Hi {greeting_name},\n\n"
#             "Please find attached your Interview Q&A Pack.\n\n"
#             "Thanks,\n"
#             "RecruitRiders Team"
#         )

#         send_email_with_attachment(
#             to_email=recipient,
#             subject=args.subject,
#             body=body,
#             attachment_path=pdf_path,
#             from_email=from_email,
#             smtp_host=smtp_host,
#             smtp_port=smtp_port,
#             smtp_user=smtp_user,
#             smtp_password=smtp_password,
#         )

#         print(
#             json.dumps(
#                 {
#                     "status": "email_sent",
#                     "to": recipient,
#                     "pdf_path": pdf_path,
#                 },
#                 indent=2,
#             )
#         )


# if __name__ == "__main__":
#     main()
















####################################################################################################




from __future__ import annotations

import argparse
import html
import json
import os
import re
import smtplib
from datetime import datetime
from email.message import EmailMessage
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv
from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

load_dotenv()


# -----------------------------------------------------------------------------
# Helpers: JSON IO
# -----------------------------------------------------------------------------
def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def validate_pdf_input(agent3: Dict[str, Any]) -> None:
    if not isinstance(agent3, dict):
        raise ValueError("Cannot build PDF: Agent 3 output is not a valid dictionary.")

    if agent3.get("error"):
        raise ValueError(f"Cannot build PDF: Agent 3 failed - {agent3.get('error')}")

    top_30 = agent3.get("top_30")
    top_20 = agent3.get("top_20_questions")

    if not isinstance(top_30, list) or not top_30:
        raise ValueError("Cannot build PDF: top_30 is empty.")

    if not isinstance(top_20, list) or not top_20:
        raise ValueError("Cannot build PDF: top_20_questions is empty.")

def safe_get(d: Dict[str, Any], keys: List[str], default: Any = None) -> Any:
    cur: Any = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


# -----------------------------------------------------------------------------
# Agent 1 parsing: email/name extraction
# -----------------------------------------------------------------------------
EMAIL_REGEX = re.compile(r"[\w\.-]+@[\w\.-]+\.\w+")


def _find_email_in_any(value: Any) -> Optional[str]:
    """Recursively search for the first email in nested strings/lists/dicts."""
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
        # Prefer direct contact-like fields first.
        for k in ["email", "candidate_email", "recipient_email", "mail"]:
            if k in value:
                found = _find_email_in_any(value.get(k))
                if found:
                    return found

        # Fallback: scan every nested value.
        for v in value.values():
            found = _find_email_in_any(v)
            if found:
                return found
        return None

    return None


def extract_candidate_contact(agent1: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """Extract candidate email and name from Agent 1 JSON."""
    email: Optional[str] = None
    name: Optional[str] = None

    for k in ["email", "candidate_email", "recipient_email"]:
        if k in agent1:
            email = _find_email_in_any(agent1.get(k))
            if email:
                break

    entities = agent1.get("entities", {}) or {}
    if not email and isinstance(entities, dict):
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

        if not email:
            email = _find_email_in_any(entities)

    raw_preview = agent1.get("raw_text_preview", "") or ""
    if raw_preview:
        lines = raw_preview.splitlines()
        first_line = lines[0].strip() if lines else ""
        if first_line:
            name = first_line.split("|")[0].strip()

        if not email:
            email = _find_email_in_any(raw_preview)

    if not name:
        for k in ["name", "candidate_name", "full_name"]:
            if isinstance(agent1.get(k), str) and agent1.get(k).strip():
                name = agent1[k].strip()
                break

    return email, name


# -----------------------------------------------------------------------------
# PDF design constants
# -----------------------------------------------------------------------------
_NAVY = colors.HexColor("#0F172A")
_BLUE = colors.HexColor("#1D4ED8")
_BLUE_LIGHT = colors.HexColor("#EFF6FF")
_BLUE_MID = colors.HexColor("#BFDBFE")
_SLATE = colors.HexColor("#475569")
_SLATE_LIGHT = colors.HexColor("#F1F5F9")
_BORDER = colors.HexColor("#CBD5E1")
_BORDER_LITE = colors.HexColor("#E2E8F0")
_TEXT_DARK = colors.HexColor("#111827")
_TEXT_BODY = colors.HexColor("#1E293B")
_CARD_BG = colors.HexColor("#F8FAFC")
_WHITE = colors.white

_EASY_BG = colors.HexColor("#DCFCE7")
_EASY_FG = colors.HexColor("#166534")
_MED_BG = colors.HexColor("#FEF9C3")
_MED_FG = colors.HexColor("#854D0E")
_HARD_BG = colors.HexColor("#FEE2E2")
_HARD_FG = colors.HexColor("#991B1B")

_DIFF_ACCENT: Dict[str, Any] = {
    "easy": colors.HexColor("#22C55E"),
    "medium": colors.HexColor("#EAB308"),
    "hard": colors.HexColor("#EF4444"),
}
_DIFF_BADGE: Dict[str, Tuple[Any, Any]] = {
    "easy": (_EASY_BG, _EASY_FG),
    "medium": (_MED_BG, _MED_FG),
    "hard": (_HARD_BG, _HARD_FG),
}


# -----------------------------------------------------------------------------
# Text cleaning / formatting helpers
# -----------------------------------------------------------------------------
def _esc(text: Any) -> str:
    """Escape plain text for ReportLab Paragraph HTML."""
    return html.escape(str(text), quote=False)


def clean_text(text: Any) -> str:
    """Clean markdown-ish symbols while preserving readable answer structure."""
    if text is None:
        return ""

    value = str(text).replace("\r\n", "\n").replace("\r", "\n")
    value = value.replace("\u2022", "- ").replace("•", "- ")

    # Remove common Markdown emphasis/code wrappers.
    value = re.sub(r"\*\*(.*?)\*\*", r"\1", value)
    value = re.sub(r"__(.*?)__", r"\1", value)
    value = re.sub(r"`([^`]*)`", r"\1", value)

    # Normalize bullets that came back as long dashes or strange symbols.
    value = re.sub(r"^[\s]*[–—]\s+", "- ", value, flags=re.MULTILINE)

    # Keep paragraph separation but remove excessive empty lines.
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def split_answer_into_blocks(answer: Any) -> List[Dict[str, str]]:
    """
    Convert answer text into structured blocks:
      {"type": "bullet", "title": "...", "body": "..."}
      {"type": "para", "body": "..."}
    """
    answer = clean_text(answer)
    if not answer:
        return []

    bullet_re = re.compile(r"^[-*]\s+(.*)")
    numbered_re = re.compile(r"^\d+[\.)]\s+(.*)")

    blocks: List[Dict[str, str]] = []
    para_buffer: List[str] = []

    def flush_para() -> None:
        nonlocal para_buffer
        if para_buffer:
            blocks.append({"type": "para", "body": " ".join(para_buffer).strip()})
            para_buffer = []

    for raw_line in answer.split("\n"):
        line = raw_line.strip()
        if not line:
            flush_para()
            continue

        bullet_match = bullet_re.match(line)
        number_match = numbered_re.match(line)

        content: Optional[str] = None
        if bullet_match:
            content = bullet_match.group(1).strip()
        elif number_match:
            content = number_match.group(1).strip()

        if content is not None:
            flush_para()
            heading_match = re.match(r"^([^:]{1,80}):\s*(.*)$", content)
            if heading_match:
                blocks.append(
                    {
                        "type": "bullet",
                        "title": heading_match.group(1).strip(),
                        "body": heading_match.group(2).strip(),
                    }
                )
            else:
                blocks.append({"type": "bullet", "title": "", "body": content})
        else:
            para_buffer.append(line)

    flush_para()
    return blocks


def _normalize_difficulty(diff: Any) -> str:
    value = clean_text(diff).lower()
    if value in {"easy", "medium", "hard"}:
        return value
    return "medium"


def _question_text(item: Any) -> str:
    if isinstance(item, dict):
        for key in ["question", "text", "title"]:
            if item.get(key):
                return clean_text(item.get(key))
        return clean_text(json.dumps(item, ensure_ascii=False))
    return clean_text(item)


def _select_answer(qa: Dict[str, Any], answer_key: Optional[str]) -> str:
    """
    Pick the answer version requested by agent3.input.answer_length.
    Falls back safely for older Agent 3 outputs that only have `answer`.
    """
    candidate_keys = []
    if answer_key:
        candidate_keys.append(answer_key)

    candidate_keys.extend([
        "answer",
        "answer_medium",
        "answer_large",
        "answer_small",
    ])

    for key in candidate_keys:
        value = qa.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    return ""


# -----------------------------------------------------------------------------
# Page header / footer
# -----------------------------------------------------------------------------
def _header_footer(canvas, doc) -> None:
    canvas.saveState()
    page_width, _ = LETTER

    canvas.setStrokeColor(_BORDER)
    canvas.setLineWidth(0.5)
    canvas.line(0.70 * inch, 0.55 * inch, page_width - 0.70 * inch, 0.55 * inch)

    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(_SLATE)
    canvas.drawString(0.70 * inch, 0.38 * inch, "Interview Q&A Pack  |  RecruitRiders")
    canvas.drawRightString(page_width - 0.70 * inch, 0.38 * inch, f"Page {doc.page}")
    canvas.restoreState()


# -----------------------------------------------------------------------------
# PDF card builders
# -----------------------------------------------------------------------------
def _difficulty_badge(diff: str) -> str:
    bg, fg = _DIFF_BADGE.get(diff, _DIFF_BADGE["medium"])
    # ReportLab Paragraph does not support rounded pill backgrounds reliably.
    # So we use a readable color label and keep the real color cue in the card accent.
    _ = bg
    return f'<font color="{fg.hexval()}"><b>{diff.capitalize()}</b></font>'


def _answer_flowables(answer: str, answer_style: ParagraphStyle) -> List[Paragraph]:
    blocks = split_answer_into_blocks(answer)
    if not blocks:
        return [Paragraph("No answer found.", answer_style)]

    rendered: List[Paragraph] = []
    for block in blocks:
        if block["type"] == "bullet":
            title = _esc(block.get("title", ""))
            body = _esc(block.get("body", ""))
            if title and body:
                text = f'<font color="#1D4ED8">&#8226;</font>&nbsp; <b>{title}:</b> {body}'
            elif title:
                text = f'<font color="#1D4ED8">&#8226;</font>&nbsp; <b>{title}</b>'
            else:
                text = f'<font color="#1D4ED8">&#8226;</font>&nbsp; {body}'
        else:
            text = _esc(block.get("body", ""))

        rendered.append(Paragraph(text, answer_style))

    return rendered


def _question_card(
    idx: int,
    qa: Dict[str, Any],
    answer_key: Optional[str],
    page_width: float,
    styles: Dict[str, ParagraphStyle],
) -> Table:
    question = clean_text(qa.get("question", ""))
    answer = _select_answer(qa, answer_key)
    focus = clean_text(qa.get("focus_area", ""))
    diff = _normalize_difficulty(qa.get("difficulty", ""))
    accent = _DIFF_ACCENT.get(diff, _DIFF_ACCENT["medium"])

    rows: List[List[Any]] = []
    rows.append([
        Paragraph(
            f'<font color="#1D4ED8"><b>Q{idx}.</b></font>&nbsp; <b>{_esc(question or "Question not available")}</b>',
            styles["question"],
        )
    ])

    tag_parts = []
    if focus:
        tag_parts.append(f'<b>Focus:</b> {_esc(focus)}')
    tag_parts.append(f'<b>Difficulty:</b> {_difficulty_badge(diff)}')
    rows.append([Paragraph(" &nbsp;&nbsp; | &nbsp;&nbsp; ".join(tag_parts), styles["tag"])])

    answer_start = len(rows)
    for para in _answer_flowables(answer, styles["answer"]):
        rows.append([para])

    table = Table(rows, colWidths=[page_width], splitByRow=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), _CARD_BG),
                ("BOX", (0, 0), (-1, -1), 0.6, _BORDER),
                ("LINEBEFORE", (0, 0), (0, -1), 5, accent),
                ("LINEABOVE", (0, answer_start), (0, answer_start), 0.4, _BORDER_LITE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 14),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, 0), 10),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 7),
                ("TOPPADDING", (0, 1), (-1, 1), 4),
                ("BOTTOMPADDING", (0, 1), (-1, 1), 8),
                ("TOPPADDING", (0, answer_start), (-1, -1), 5),
                ("BOTTOMPADDING", (0, answer_start), (-1, -1), 4),
            ]
        )
    )
    return table


def _paragraph_list(items: List[Any], style: ParagraphStyle) -> ListFlowable:
    return ListFlowable(
        [ListItem(Paragraph(_esc(_question_text(item)), style), leftIndent=0) for item in items],
        bulletType="1",
        start="1",
        leftIndent=18,
    )


# -----------------------------------------------------------------------------
# PDF Generation
# -----------------------------------------------------------------------------
def build_pdf_to_bytes(
    agent3: Dict[str, Any],
    candidate_name: Optional[str] = None,
    candidate_email: Optional[str] = None,
) -> bytes:
    """
    Generate the Interview Q&A Pack PDF entirely in memory.
    Returns raw PDF bytes — nothing is written to disk.
    """
    import io
    buffer = io.BytesIO()
    _render_pdf(agent3, buffer, candidate_name=candidate_name, candidate_email=candidate_email)
    return buffer.getvalue()


def build_pdf(
    agent3: Dict[str, Any],
    out_path: str,
    candidate_name: Optional[str] = None,
    candidate_email: Optional[str] = None,
) -> str:
    """
    Legacy helper — writes PDF to a file path.
    Prefer build_pdf_to_bytes() for in-memory / cloud deployments.
    """
    _render_pdf(agent3, out_path, candidate_name=candidate_name, candidate_email=candidate_email)
    return out_path


def _render_pdf(
    agent3: Dict[str, Any],
    dest,                        # str file path  OR  io.BytesIO buffer
    candidate_name: Optional[str] = None,
    candidate_email: Optional[str] = None,
) -> None:
    """
    Core rendering logic shared by build_pdf() and build_pdf_to_bytes().
    `dest` is passed directly to SimpleDocTemplate — ReportLab accepts both
    a file-system path (str) and any writable file-like object (BytesIO).
    """
    validate_pdf_input(agent3)
    base = getSampleStyleSheet()
    

    def s(name: str, **kwargs: Any) -> ParagraphStyle:
        parent = kwargs.pop("parent", base["Normal"])
        return ParagraphStyle(name, parent=parent, **kwargs)

    styles = {
        "cover_title": s(
            "CoverTitle",
            fontName="Helvetica-Bold",
            fontSize=28,
            leading=34,
            textColor=_WHITE,
            spaceAfter=6,
        ),
        "cover_sub": s(
            "CoverSub",
            fontName="Helvetica",
            fontSize=12,
            leading=17,
            textColor=_BLUE_MID,
        ),
        "section": s(
            "SectionHead",
            fontName="Helvetica-Bold",
            fontSize=15,
            leading=20,
            textColor=_NAVY,
            spaceBefore=14,
            spaceAfter=10,
        ),
        "round": s(
            "RoundLabel",
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=16,
            textColor=_BLUE,
        ),
        "meta_label": s(
            "MetaLabel",
            fontName="Helvetica-Bold",
            fontSize=9.5,
            leading=14,
            textColor=_NAVY,
        ),
        "meta_value": s(
            "MetaValue",
            fontName="Helvetica",
            fontSize=9.5,
            leading=14,
            textColor=colors.HexColor("#334155"),
        ),
        "body": s(
            "Body",
            fontName="Helvetica",
            fontSize=10.2,
            leading=15.5,
            textColor=_TEXT_BODY,
            spaceAfter=4,
        ),
        "note": s(
            "Note",
            fontName="Helvetica",
            fontSize=9.8,
            leading=14.5,
            textColor=_SLATE,
            spaceAfter=3,
        ),
        "question": s(
            "Question",
            fontName="Helvetica-Bold",
            fontSize=11.2,
            leading=15.5,
            textColor=_TEXT_DARK,
        ),
        "tag": s(
            "Tag",
            fontName="Helvetica",
            fontSize=9.3,
            leading=13,
            textColor=_SLATE,
        ),
        "answer": s(
            "Answer",
            fontName="Helvetica",
            fontSize=10.1,
            leading=15.2,
            textColor=_TEXT_BODY,
        ),
    }

    left_margin = right_margin = 0.70 * inch
    usable_width = LETTER[0] - left_margin - right_margin

    doc = SimpleDocTemplate(
        dest,
        pagesize=LETTER,
        leftMargin=left_margin,
        rightMargin=right_margin,
        topMargin=0.75 * inch,
        bottomMargin=0.80 * inch,
        title="Interview Q&A Pack",
        author="RecruitRiders",
    )

    story: List[Any] = []

    created_at = datetime.now().strftime("%B %d, %Y | %H:%M")
    rounds = safe_get(agent3, ["input", "rounds"], default=[]) or []
    rounds_text = ", ".join(map(str, rounds)) if rounds else "N/A"
    answer_key = safe_get(agent3, ["input", "answer_length"], default=None)
    doc_type = safe_get(agent3, ["input", "doc_type"], default="N/A")

    top_30 = agent3.get("top_30", []) or []
    top_20 = agent3.get("top_20_questions", []) or []
    notes = agent3.get("notes", []) or []
    if isinstance(notes, str):
        notes = [notes]

    # Cover banner
    cover_table = Table(
        [
            [
                [
                    Paragraph("Interview Q&A Pack", styles["cover_title"]),
                    Paragraph(
                        f"Structured preparation document | Tailored answers | {_esc(rounds_text)}",
                        styles["cover_sub"],
                    ),
                    Spacer(1, 0.16 * inch),
                ]
            ]
        ],
        colWidths=[usable_width],
    )
    cover_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), _NAVY),
                ("TOPPADDING", (0, 0), (-1, -1), 22),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 22),
                ("LEFTPADDING", (0, 0), (-1, -1), 20),
                ("RIGHTPADDING", (0, 0), (-1, -1), 20),
            ]
        )
    )
    story.append(cover_table)
    story.append(Spacer(1, 0.18 * inch))

    # Metadata card
    meta_rows = [
        [Paragraph("Candidate", styles["meta_label"]), Paragraph(_esc(candidate_name or "N/A"), styles["meta_value"])],
        [Paragraph("Email", styles["meta_label"]), Paragraph(_esc(candidate_email or "N/A"), styles["meta_value"])],
        [Paragraph("Round(s)", styles["meta_label"]), Paragraph(_esc(rounds_text), styles["meta_value"])],
        [Paragraph("Answer Length", styles["meta_label"]), Paragraph(_esc(answer_key or "answer"), styles["meta_value"])],
        [Paragraph("Document Type", styles["meta_label"]), Paragraph(_esc(doc_type), styles["meta_value"])],
        [Paragraph("Generated", styles["meta_label"]), Paragraph(_esc(created_at), styles["meta_value"])],
    ]
    meta_table = Table(meta_rows, colWidths=[1.25 * inch, usable_width - 1.25 * inch])
    meta_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), _SLATE_LIGHT),
                ("BOX", (0, 0), (-1, -1), 0.6, _BORDER),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, _BORDER_LITE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.append(meta_table)
    story.append(Spacer(1, 0.22 * inch))

    # Contents
    story.append(HRFlowable(width="100%", thickness=0.7, color=_BORDER))
    story.append(Spacer(1, 0.12 * inch))
    story.append(Paragraph("Contents", styles["section"]))

    toc_rows = [
        [Paragraph("Section", styles["meta_label"]), Paragraph("Description", styles["meta_label"])],
        [Paragraph("Top 30 Q&A", styles["meta_label"]), Paragraph("Detailed questions with structured answers, focus tags, and difficulty markers", styles["meta_value"])],
        [Paragraph("Top 20 Questions", styles["meta_label"]), Paragraph("Quick-reference list of the most important questions", styles["meta_value"])],
        [Paragraph("Notes", styles["meta_label"]), Paragraph("Generation notes and additional context, when available", styles["meta_value"])],
    ]
    toc_table = Table(toc_rows, colWidths=[1.7 * inch, usable_width - 1.7 * inch])
    toc_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), _NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), _WHITE),
                ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _SLATE_LIGHT]),
                ("BOX", (0, 0), (-1, -1), 0.6, _BORDER),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, _BORDER_LITE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.append(toc_table)
    story.append(Spacer(1, 0.10 * inch))
    story.append(
        Paragraph(
            '<b>Difficulty key:</b> '
            '<font color="#166534">Easy</font> | '
            '<font color="#854D0E">Medium</font> | '
            '<font color="#991B1B">Hard</font>',
            styles["note"],
        )
    )
    story.append(PageBreak())

    # Top 30 Q&A section
    story.append(Paragraph("Top 30 Questions with Detailed Answers", styles["section"]))

    by_round: Dict[str, List[Dict[str, Any]]] = {}
    for item in top_30:
        if isinstance(item, dict):
            round_name = clean_text(item.get("round", "Unknown Round")) or "Unknown Round"
            by_round.setdefault(round_name, []).append(item)

    if not by_round:
        story.append(Paragraph("No Q&amp;A content found.", styles["body"]))
    else:
        global_idx = 1
        for round_name, items in by_round.items():
            round_table = Table(
                [[Paragraph(f"Round: {_esc(round_name)}", styles["round"])]],
                colWidths=[usable_width],
            )
            round_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), _BLUE_LIGHT),
                        ("BOX", (0, 0), (-1, -1), 0.6, _BLUE_MID),
                        ("TOPPADDING", (0, 0), (-1, -1), 8),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                        ("LEFTPADDING", (0, 0), (-1, -1), 12),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                    ]
                )
            )
            story.append(round_table)
            story.append(Spacer(1, 0.12 * inch))

            for qa in items:
                story.append(_question_card(global_idx, qa, answer_key, usable_width, styles))
                story.append(Spacer(1, 0.13 * inch))
                global_idx += 1

    story.append(PageBreak())

    # Top 20 quick reference section
    story.append(Paragraph("Top 20 Questions - Quick Reference", styles["section"]))
    story.append(Paragraph("Review these questions before the interview for a final confidence check.", styles["note"]))
    story.append(Spacer(1, 0.10 * inch))

    if not top_20:
        story.append(Paragraph("No top_20_questions found.", styles["body"]))
    else:
        # Two-column grid for compact readability.
        col_width = (usable_width - 0.15 * inch) / 2
        grid_rows: List[List[Any]] = []
        for i in range(0, len(top_20), 2):
            left = _question_text(top_20[i])
            right = _question_text(top_20[i + 1]) if i + 1 < len(top_20) else ""
            grid_rows.append(
                [
                    Paragraph(f"<b>{i + 1}.</b> {_esc(left)}", styles["body"]),
                    Paragraph(f"<b>{i + 2}.</b> {_esc(right)}", styles["body"]) if right else Paragraph("", styles["body"]),
                ]
            )
        grid_table = Table(grid_rows, colWidths=[col_width, col_width], splitByRow=1)
        grid_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                    ("BOX", (0, 0), (-1, -1), 0.5, _BORDER),
                    ("INNERGRID", (0, 0), (-1, -1), 0.3, _BORDER_LITE),
                    ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, _SLATE_LIGHT]),
                ]
            )
        )
        story.append(grid_table)

    # Notes section
    if notes:
        story.append(Spacer(1, 0.25 * inch))
        story.append(HRFlowable(width="100%", thickness=0.6, color=_BORDER))
        story.append(Spacer(1, 0.12 * inch))
        story.append(Paragraph("Notes", styles["section"]))
        story.append(
            ListFlowable(
                [ListItem(Paragraph(_esc(str(n)), styles["note"]), leftIndent=0) for n in notes],
                bulletType="bullet",
                start="square",
                leftIndent=14,
            )
        )

    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    # _render_pdf returns None — callers use dest directly


# -----------------------------------------------------------------------------
# Email Sending (SMTP)
# -----------------------------------------------------------------------------
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

    if smtp_port == 465:
        with smtplib.SMTP_SSL(smtp_host, smtp_port) as server:
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
    else:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
    # with smtplib.SMTP(smtp_host, smtp_port) as server:
    #     server.starttls()
        # server.login(smtp_user, smtp_password)
        # server.send_message(msg)


def send_email_from_bytes(
    to_email: str,
    subject: str,
    body: str,
    pdf_bytes: bytes,
    pdf_filename: str,
    from_email: str,
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_password: str,
) -> None:
    """
    Send the PDF as an email attachment from an in-memory bytes buffer.
    No file is written to disk.
    """
    msg = EmailMessage()
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)
    msg.add_attachment(
        pdf_bytes,
        maintype="application",
        subtype="pdf",
        filename=pdf_filename,
    )

    if smtp_port == 465:
        with smtplib.SMTP_SSL(smtp_host, smtp_port) as server:
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
    else:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)


# -----------------------------------------------------------------------------
# Main CLI
# -----------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Agent 4: Create PDF from Agent 3 JSON and optionally email it to the candidate."
    )
    parser.add_argument("--agent1_json", required=True, help="Path to Agent 1 output JSON")
    parser.add_argument("--agent3_json", required=True, help="Path to Agent 3 output JSON")
    parser.add_argument("--out_dir", default="app/output", help="Directory to save PDF")
    parser.add_argument("--pdf_name", default=None, help="Optional PDF filename")
    parser.add_argument("--send_email", action="store_true", help="If set, email will be sent")

    parser.add_argument(
        "--to_email",
        default=None,
        help="Override recipient email, otherwise extracted from Agent 1 resume JSON",
    )
    parser.add_argument("--subject", default="Your Interview Q&A Pack", help="Email subject")

    args = parser.parse_args()

    agent1 = load_json(args.agent1_json)
    agent3 = load_json(args.agent3_json)

    extracted_email, candidate_name = extract_candidate_contact(agent1)
    recipient = (args.to_email or extracted_email or "").strip() or None

    os.makedirs(args.out_dir, exist_ok=True)

    pdf_filename = args.pdf_name or f"interview_qa_pack_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    pdf_path = os.path.join(args.out_dir, pdf_filename)

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
                "If using Gmail, use an App Password instead of your normal password."
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
