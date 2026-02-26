import os
import json
import argparse
from datetime import datetime

from app.agents.agent_1_parser import run_agent1
from app.agents.agent_2_researcher import run_agent2
from app.agents.agent_3_qa_gen import run_agent3
from app.agents.agent_4_dispatcher import extract_candidate_contact, build_pdf, send_email_with_attachment
from app.database.relational import init_db, save_candidate_run
from app.database.vector_store import store_document_in_vector_db

def main():
    init_db()
    parser = argparse.ArgumentParser(description="End-to-End Interview Preparation Workflow Orchestrator")
    parser.add_argument("--resume_path", type=str, required=True, help="Path to the candidate's Resume")
    parser.add_argument("--jd_path", type=str, required=True, help="Path to the Job Description document")
    parser.add_argument("--interview_rounds", type=str, required=True, help="Interview rounds (separate by ';' or ',')")
    parser.add_argument("--company", type=str, default=None, help="Company override (if JD doesn't state it)")
    parser.add_argument("--role", type=str, default=None, help="Role override")
    parser.add_argument("--out_dir", type=str, default="app/output", help="Directory to save intermediate JSONs and PDF")
    parser.add_argument("--send_email", action="store_true", help="Send email with the generated PDF to the candidate")
    parser.add_argument("--to_email", type=str, default=None, help="Override recipient email (otherwise extracted from resume)")
    
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    print(f"--- Starting Orchestrator Workflow ---")
    print(f"Resume Input: {args.resume_path}")
    print(f"JD Input: {args.jd_path}")

    # ---------------------------------------------------------
    # 1. Agent 1: Parse Documents (Run twice: Resume & JD)
    # ---------------------------------------------------------
    print("\n[1/4] Running Agent 1 (Document Parser)...")
    
    print("      -> Parsing Resume...")
    resume_out = run_agent1(args.resume_path)
    
    print("      -> Parsing Job Description...")
    jd_out = run_agent1(args.jd_path)
    
    # Combine outputs for downstream agents
    combined_agent1_out = {
        "doc_type": "combined_resume_and_jd",
        "resume_data": resume_out,
        "jd_data": jd_out
    }

    agent1_out_path = os.path.join(args.out_dir, f"agent1_combined_out_{timestamp}.json")
    with open(agent1_out_path, "w", encoding="utf-8") as f:
        json.dump(combined_agent1_out, f, indent=2, ensure_ascii=False)
    print(f"Agent 1 combined output saved to {agent1_out_path}")

    resume_text = resume_out.get("raw_text_preview", "")
    jd_text = jd_out.get("raw_text_preview", "")
    candidate_id = timestamp # using timestamp as a unique ID for this run

    if resume_text:
        store_document_in_vector_db(doc_id=f"res_{timestamp}", text=resume_text, doc_type="resume", candidate_id=candidate_id)
    if jd_text:
        store_document_in_vector_db(doc_id=f"jd_{timestamp}", text=jd_text, doc_type="job_description", candidate_id=candidate_id)
    # ---------------------------------------------------------
    # 2. Agent 2: Company Researcher
    # ---------------------------------------------------------
    print("\n[2/4] Running Agent 2 (Company Researcher)...")
    # We pass the JD output to Agent 2, because JD contains the company/role better than a resume
    agent2_out = run_agent2(jd_out, company_override=args.company, role_override=args.role)
    
    agent2_out_path = os.path.join(args.out_dir, f"agent2_out_{timestamp}.json")
    with open(agent2_out_path, "w", encoding="utf-8") as f:
        json.dump(agent2_out, f, indent=2, ensure_ascii=False)
    print(f"Agent 2 output saved to {agent2_out_path}")

    # ---------------------------------------------------------
    # 3. Agent 3: QA Generator
    # ---------------------------------------------------------
    print("\n[3/4] Running Agent 3 (Q&A Generator)...")
    # Pass the combined Resume + JD data so Agent 3 can match candidate skills to job requirements
    agent3_out = run_agent3(
        agent1_data=combined_agent1_out,
        agent2_data=agent2_out,
        agent1_path=agent1_out_path,
        agent2_path=agent2_out_path,
        interview_rounds=args.interview_rounds
    )
    
    agent3_out_path = os.path.join(args.out_dir, f"agent3_out_{timestamp}.json")
    with open(agent3_out_path, "w", encoding="utf-8") as f:
        json.dump(agent3_out, f, indent=2, ensure_ascii=False)
    print(f"Agent 3 output saved to {agent3_out_path}")

    # ---------------------------------------------------------
    # 4. Agent 4: Dispatcher (PDF generation and Email)
    # ---------------------------------------------------------
    print("\n[4/4] Running Agent 4 (Dispatcher)...")
    # Extract candidate contact details specifically from the parsed Resume
    extracted_email, candidate_name = extract_candidate_contact(resume_out)
    recipient = (args.to_email or extracted_email or "").strip() or None

    pdf_filename = f"interview_qa_pack_{timestamp}.pdf"
    pdf_path = os.path.join(args.out_dir, pdf_filename)

    build_pdf(agent3_out, pdf_path, candidate_name=candidate_name, candidate_email=recipient)
    print(f"PDF successfully generated at: {pdf_path}")

    if args.send_email:
        if not recipient:
            print("Error: No recipient email found in the document. Pass --to_email to manually provide it.")
        else:
            smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
            smtp_port = int(os.getenv("SMTP_PORT", "587"))
            smtp_user = os.getenv("SMTP_USER", "")
            smtp_password = os.getenv("SMTP_PASSWORD", "")
            from_email = os.getenv("FROM_EMAIL", smtp_user)

            if not smtp_user or not smtp_password:
                print("Error: Missing SMTP_USER / SMTP_PASSWORD in environment variables. Cannot send email.")
            else:
                greeting_name = candidate_name or "Candidate"
                body = (
                    f"Hi {greeting_name},\n\n"
                    "Please find attached your personalized Interview Q&A Pack tailored to your resume and the job description.\n\n"
                    "Best of luck,\n"
                    "RecruitRiders Team"
                )
                try:
                    send_email_with_attachment(
                        to_email=recipient,
                        subject="Your Interview Q&A Pack",
                        body=body,
                        attachment_path=pdf_path,
                        from_email=from_email,
                        smtp_host=smtp_host,
                        smtp_port=smtp_port,
                        smtp_user=smtp_user,
                        smtp_password=smtp_password,
                    )
                    print(f"Email sent successfully to {recipient}")
                except Exception as e:
                    print(f"Failed to send email: {e}")

    print("\n--- Workflow Completed Successfully! ---")
    save_candidate_run(
    name=candidate_name,
    email=recipient,
    company=agent2_out.get("company_name", args.company),
    role=agent2_out.get("role_title", args.role),
    resume_path=args.resume_path,
    jd_path=args.jd_path,
    pdf_path=pdf_path
    )
if __name__ == "__main__":
    main()



# python -m app.orchestrator.workflow \
#   --resume_path "documents/03_Test_Case_Resume.pdf" \
#   --jd_path "documents/03_Test_Case_JD.pdf" \
#   --interview_rounds "Recruiter Screen; Technical Round 1; Hiring Manager; Behavioral"


# python -m app.orchestrator.workflow \
#   --file_path "documents/03_Test_Case_Resume.pdf" \
#   --company "Microsoft" \
#   --interview_rounds "Recruiter Screen; Technical Round 1; Behavioral" \
#   --send_email \
#   --to_email "candidate@example.com"



# python -m app.orchestrator.workflow --resume_path "documents/03_Test_Case_Resume.pdf" --jd_path "documents/03_Test_Case_JD.pdf" --interview_rounds "Round 2 - Technical Round" --send_email --to_email "phet6011@gmail.com"
# python -m app.orchestrator.workflow --resume_path "documents/Het/02_Test_Case_Resume.pdf" --jd_path "documents/Het/JD.pdf" --interview_rounds "Round 1 - Recruiter Screen" --company "Microsoft" --role "Software Engineering" --send_email