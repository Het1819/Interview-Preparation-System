from __future__ import annotations

import shutil
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.orchestrator.workflow import run_full_workflow

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "app" / "output"
UPLOAD_DIR = OUTPUT_DIR / "uploads"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".jpg", ".jpeg", ".png"}


class WorkflowRequest(BaseModel):
    resume_path: str = Field(..., description="Local path to candidate resume")
    jd_path: str = Field(..., description="Local path to job description")
    interview_rounds: str = Field(
        ...,
        description="Example: 'Recruiter Screen; Technical Round 1; Hiring Manager'",
    )
    answer_length: str = Field(default="answer_medium")
    company: Optional[str] = None
    role: Optional[str] = None
    send_email: bool = False
    to_email: Optional[str] = None
    out_dir: str = "app/output"


class WorkflowResponse(BaseModel):
    success: bool
    message: str
    run_id: str
    candidate_name: Optional[str] = None
    recipient_email: Optional[str] = None
    company: Optional[str] = None
    role: Optional[str] = None
    pdf_path: Optional[str] = None
    pdf_download_url: Optional[str] = None
    outputs: Dict[str, str] = Field(default_factory=dict)
    agent1_output: Dict[str, Any] = Field(default_factory=dict)
    agent2_output: Dict[str, Any] = Field(default_factory=dict)
    agent3_output: Dict[str, Any] = Field(default_factory=dict)


def validate_extension(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {sorted(ALLOWED_EXTENSIONS)}",
        )
    return ext


def save_upload(file: UploadFile, request_id: str, prefix: str) -> Path:
    ext = validate_extension(file.filename or "")
    destination = UPLOAD_DIR / f"{prefix}_{request_id}{ext}"

    with destination.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return destination


@asynccontextmanager
async def lifespan(app: FastAPI):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title="Interview Preparation System API",
    description="FastAPI wrapper for the multi-agent interview preparation workflow.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(OUTPUT_DIR)), name="static")


@app.get("/", tags=["Root"])
async def root() -> Dict[str, Any]:
    return {
        "message": "Interview Preparation System API is running",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health", tags=["Health"])
async def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/workflow/run", response_model=WorkflowResponse, tags=["Workflow"])
async def run_workflow_with_uploads(
    resume: UploadFile = File(..., description="Candidate resume file"),
    jd: UploadFile = File(..., description="Job description file"),
    interview_rounds: str = Form(...),
    answer_length: str = Form("answer_medium"),
    company: Optional[str] = Form(None),
    role: Optional[str] = Form(None),
    send_email: bool = Form(False),
    to_email: Optional[str] = Form(None),
) -> WorkflowResponse:
    request_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    try:
        resume_path = save_upload(resume, request_id, "resume")
        jd_path = save_upload(jd, request_id, "jd")

        result = run_full_workflow(
            resume_path=str(resume_path),
            jd_path=str(jd_path),
            interview_rounds=interview_rounds,
            answer_length=answer_length,
            company=company,
            role=role,
            out_dir=str(OUTPUT_DIR),
            send_email=send_email,
            to_email=to_email,
        )
        return WorkflowResponse(**result)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        try:
            await resume.close()
        except Exception:
            pass

        try:
            await jd.close()
        except Exception:
            pass


@app.post("/workflow/run-from-paths", response_model=WorkflowResponse, tags=["Workflow"])
async def run_workflow_from_paths(payload: WorkflowRequest) -> WorkflowResponse:
    if not Path(payload.resume_path).exists():
        raise HTTPException(status_code=400, detail="resume_path does not exist")

    if not Path(payload.jd_path).exists():
        raise HTTPException(status_code=400, detail="jd_path does not exist")

    try:
        result = run_full_workflow(
            resume_path=payload.resume_path,
            jd_path=payload.jd_path,
            interview_rounds=payload.interview_rounds,
            answer_length=payload.answer_length,
            company=payload.company,
            role=payload.role,
            out_dir=payload.out_dir,
            send_email=payload.send_email,
            to_email=payload.to_email,
        )
        return WorkflowResponse(**result)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/downloads/{run_id}/{filename}", tags=["Downloads"])
async def download_generated_file(run_id: str, filename: str):
    file_path = OUTPUT_DIR / run_id / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type="application/octet-stream",
    )


@app.get("/runs/{run_id}", tags=["Runs"])
async def get_run_metadata(run_id: str):
    run_dir = OUTPUT_DIR / run_id

    if not run_dir.exists():
        raise HTTPException(status_code=404, detail="Run not found")

    files = [str(p.name) for p in run_dir.iterdir() if p.is_file()]
    return {
        "run_id": run_id,
        "files": files,
        "path": str(run_dir),
    }


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "Unexpected server error",
            "detail": str(exc),
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )












###############################################################################################
###############################################################################################
###############################################################################################
###############################################################################################


# import os
# import shutil
# import json
# from datetime import datetime
# from contextlib import asynccontextmanager

# from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.responses import JSONResponse, FileResponse
# from pydantic import BaseModel

# # Import your existing agent and database functions
# from app.agents.agent_1_parser import run_agent1
# from app.agents.agent_2_researcher import run_agent2
# from app.agents.agent_3_qa_gen import run_agent3
# from app.agents.agent_4_dispatcher import extract_candidate_contact, build_pdf, send_email_with_attachment
# from app.database.relational import init_db, save_candidate_run
# # from app.database.vector_store import store_document_in_vector_db

# # ---------------------------------------------------------
# # Application Lifespan (Startup/Shutdown)
# # ---------------------------------------------------------
# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     # Initialize relational database on startup
#     print("Initializing Database...")
#     init_db()
    
#     # Ensure necessary directories exist
#     os.makedirs("app/uploads", exist_ok=True)
#     os.makedirs("app/output", exist_ok=True)
#     yield
#     # Clean up operations can go here during shutdown

# # Initialize FastAPI App
# app = FastAPI(
#     title="Multi-Agent Interview Prep API",
#     description="API for the AI-powered Interview Preparation System.",
#     version="1.0.0",
#     lifespan=lifespan
# )

# # ---------------------------------------------------------
# # CORS Middleware (To allow frontend requests)
# # ---------------------------------------------------------
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],  # In production, replace "*" with your frontend URL (e.g., ["http://localhost:3000"])
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # ---------------------------------------------------------
# # Helper function to save uploaded files
# # ---------------------------------------------------------
# def save_upload_file(upload_file: UploadFile, destination: str) -> str:
#     try:
#         file_path = os.path.join(destination, upload_file.filename)
#         with open(file_path, "wb") as buffer:
#             shutil.copyfileobj(upload_file.file, buffer)
#         return file_path
#     finally:
#         upload_file.file.close()

# # ---------------------------------------------------------
# # Core API Endpoint
# # ---------------------------------------------------------
# @app.post("/api/v1/generate-prep")
# async def generate_prep(
#     resume: UploadFile = File(..., description="The candidate's Resume (PDF/DOCX)"),
#     jd: UploadFile = File(..., description="The Job Description (PDF/DOCX)"),
#     interview_rounds: str = Form(..., description="Interview rounds separated by ';' or ','"),
#     answer_length: str = Form("answer_medium", description="Length of generated answers"),
#     company: str = Form(None, description="Company name override"),
#     role: str = Form(None, description="Role override"),
#     send_email: bool = Form(False, description="Whether to send the generated PDF via email"),
#     to_email: str = Form(None, description="Email address override")
# ):
#     try:
#         timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
#         upload_dir = "app/uploads"
#         out_dir = "app/output"

#         # 1. Save uploaded files locally
#         resume_path = save_upload_file(resume, upload_dir)
#         jd_path = save_upload_file(jd, upload_dir)

#         print(f"[{timestamp}] Starting Workflow for Resume: {resume.filename} | JD: {jd.filename}")

#         # ---------------------------------------------------------
#         # Agent 1: Parse Documents
#         # ---------------------------------------------------------
#         print("[1/4] Running Agent 1 (Document Parser)...")
#         resume_out = run_agent1(resume_path)
#         jd_out = run_agent1(jd_path)
        
#         combined_agent1_out = {
#             "doc_type": "combined_resume_and_jd",
#             "resume_data": resume_out,
#             "jd_data": jd_out
#         }

#         # Save to Vector DB
#         resume_text = resume_out.get("raw_text_preview", "")
#         jd_text = jd_out.get("raw_text_preview", "")
        
#         # if resume_text:
#         #     store_document_in_vector_db(doc_id=f"res_{timestamp}", text=resume_text, doc_type="resume", candidate_id=timestamp)
#         # if jd_text:
#         #     store_document_in_vector_db(doc_id=f"jd_{timestamp}", text=jd_text, doc_type="job_description", candidate_id=timestamp)

#         # ---------------------------------------------------------
#         # Agent 2: Company Researcher
#         # ---------------------------------------------------------
#         print("[2/4] Running Agent 2 (Company Researcher)...")
#         agent2_out = run_agent2(jd_out, company_override=company, role_override=role)

#         # ---------------------------------------------------------
#         # Agent 3: QA Generator
#         # ---------------------------------------------------------
#         print("[3/4] Running Agent 3 (Q&A Generator)...")
#         agent3_out = run_agent3(
#             agent1_data=combined_agent1_out,
#             agent2_data=agent2_out,
#             agent1_path=resume_path,
#             agent2_path=jd_path,
#             interview_rounds=interview_rounds,
#             answer_length=answer_length
#         )

#         # ---------------------------------------------------------
#         # Agent 4: Dispatcher (PDF Generation & Email)
#         # ---------------------------------------------------------
#         print("[4/4] Running Agent 4 (Dispatcher)...")
#         extracted_email, candidate_name = extract_candidate_contact(resume_out)
#         recipient = (to_email or extracted_email or "").strip() or None

#         pdf_filename = f"interview_qa_pack_{timestamp}.pdf"
#         pdf_path = os.path.join(out_dir, pdf_filename)

#         build_pdf(agent3_out, pdf_path, candidate_name=candidate_name, candidate_email=recipient)

#         email_status = "Not Requested"
#         if send_email:
#             if not recipient:
#                 email_status = "Failed: No recipient email provided or extracted."
#             else:
#                 try:
#                     smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
#                     smtp_port = int(os.getenv("SMTP_PORT", "587"))
#                     smtp_user = os.getenv("SMTP_USER")
#                     smtp_password = os.getenv("SMTP_PASSWORD")
#                     from_email = os.getenv("FROM_EMAIL", smtp_user)

#                     if not smtp_user or not smtp_password:
#                         email_status = "Failed: Missing SMTP credentials in .env."
#                     else:
#                         greeting_name = candidate_name or "Candidate"
#                         body = (
#                             f"Hi {greeting_name},\n\n"
#                             "Please find attached your personalized Interview Q&A Pack.\n\n"
#                             "Best of luck,\nRecruitRiders Team"
#                         )
#                         send_email_with_attachment(
#                             to_email=recipient,
#                             subject="Your Interview Q&A Pack",
#                             body=body,
#                             attachment_path=pdf_path,
#                             from_email=from_email,
#                             smtp_host=smtp_host,
#                             smtp_port=smtp_port,
#                             smtp_user=smtp_user,
#                             smtp_password=smtp_password,
#                         )
#                         email_status = "Success"
#                 except Exception as e:
#                     email_status = f"Failed: {str(e)}"

#         # ---------------------------------------------------------
#         # Save Run to Relational DB
#         # ---------------------------------------------------------
#         final_company = agent2_out.get("company_name", company)
#         final_role = agent2_out.get("role_title", role)
        
#         save_candidate_run(
#             name=candidate_name,
#             email=recipient,
#             company=final_company,
#             role=final_role,
#             resume_path=resume_path,
#             jd_path=jd_path,
#             pdf_path=pdf_path
#         )

#         return JSONResponse(status_code=200, content={
#             "status": "success",
#             "message": "Interview Prep Package generated successfully.",
#             "candidate_name": candidate_name,
#             "company_researched": final_company,
#             "email_status": email_status,
#             "qa_data": agent3_out,  # Return the full Q&A JSON to the frontend
#             "pdf_download_url": f"/api/v1/download-pdf/{pdf_filename}" # Expose PDF for frontend download
#         })

#     except Exception as e:
#         print(f"Error during execution: {e}")
#         raise HTTPException(status_code=500, detail=str(e))


# # ---------------------------------------------------------
# # Endpoint to Download the Generated PDF
# # ---------------------------------------------------------
# @app.get("/api/v1/download-pdf/{filename}")
# async def download_pdf(filename: str):
#     file_path = os.path.join("app/output", filename)
#     if os.path.exists(file_path):
#         return FileResponse(file_path, media_type='application/pdf', filename=filename)
#     raise HTTPException(status_code=404, detail="PDF not found.")












###############################################################################################
###############################################################################################
###############################################################################################
###############################################################################################




# from __future__ import annotations

# import json
# import os
# import re
# import shutil
# from contextlib import asynccontextmanager
# from datetime import datetime
# from pathlib import Path
# from typing import Any, Dict, Optional

# from dotenv import load_dotenv
# from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.responses import FileResponse, JSONResponse
# from fastapi.staticfiles import StaticFiles
# from pydantic import BaseModel, Field

# from app.agents.agent_1_parser import run_agent1
# from app.agents.agent_2_researcher import run_agent2
# from app.agents.agent_3_qa_gen import run_agent3
# from app.agents.agent_4_dispatcher import (
#     build_pdf,
#     extract_candidate_contact,
#     send_email_with_attachment,
# )
# from app.database.relational import init_db, save_candidate_run
# # from app.database.vector_store import store_document_in_vector_db

# load_dotenv()

# # -------------------------------------------------------------------
# # Paths / constants
# # -------------------------------------------------------------------
# BASE_DIR = Path(__file__).resolve().parent.parent
# OUTPUT_DIR = BASE_DIR / "app" / "output"
# UPLOAD_DIR = OUTPUT_DIR / "uploads"

# OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
# UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".jpg", ".jpeg", ".png"}
# ALLOWED_ANSWER_LENGTHS = {"answer_small", "answer_medium", "answer_large"}

# EMAIL_REGEX = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


# # -------------------------------------------------------------------
# # Pydantic models
# # -------------------------------------------------------------------
# class WorkflowRequest(BaseModel):
#     resume_path: str = Field(..., description="Local path to candidate resume")
#     jd_path: str = Field(..., description="Local path to job description")
#     interview_rounds: str = Field(
#         ...,
#         description="Example: 'Recruiter Screen; Technical Round 1; Hiring Manager'",
#     )
#     answer_length: str = Field(
#         default="answer_medium",
#         description="One of: answer_small, answer_medium, answer_large",
#     )
#     company: Optional[str] = Field(default=None)
#     role: Optional[str] = Field(default=None)
#     send_email: bool = Field(default=False)
#     to_email: Optional[str] = Field(default=None)


# class WorkflowResponse(BaseModel):
#     success: bool
#     message: str
#     run_id: str
#     candidate_name: Optional[str] = None
#     recipient_email: Optional[str] = None
#     company: Optional[str] = None
#     role: Optional[str] = None
#     pdf_path: Optional[str] = None
#     pdf_download_url: Optional[str] = None
#     outputs: Dict[str, str] = Field(default_factory=dict)
#     agent1_output: Dict[str, Any] = Field(default_factory=dict)
#     agent2_output: Dict[str, Any] = Field(default_factory=dict)
#     agent3_output: Dict[str, Any] = Field(default_factory=dict)


# # -------------------------------------------------------------------
# # Helpers
# # -------------------------------------------------------------------
# def _validate_extension(filename: str) -> str:
#     ext = Path(filename).suffix.lower()
#     if ext not in ALLOWED_EXTENSIONS:
#         raise HTTPException(
#             status_code=400,
#             detail=f"Unsupported file type '{ext}'. Allowed: {sorted(ALLOWED_EXTENSIONS)}",
#         )
#     return ext


# def _normalize_email(value: Optional[str]) -> Optional[str]:
#     if value is None:
#         return None

#     cleaned = str(value).strip()

#     invalid_placeholders = {
#         "",
#         "string",
#         "null",
#         "none",
#         "n/a",
#         "na",
#         "-",
#         "test",
#         "example@example.com",
#     }

#     if cleaned.lower() in invalid_placeholders:
#         return None

#     if not EMAIL_REGEX.match(cleaned):
#         return None

#     return cleaned


# def _save_upload(file: UploadFile, run_id: str, prefix: str) -> Path:
#     ext = _validate_extension(file.filename or "")
#     safe_name = f"{prefix}_{run_id}{ext}"
#     destination = UPLOAD_DIR / safe_name

#     with destination.open("wb") as buffer:
#         shutil.copyfileobj(file.file, buffer)

#     return destination


# def _write_json(path: Path, payload: Dict[str, Any]) -> None:
#     with path.open("w", encoding="utf-8") as f:
#         json.dump(payload, f, indent=2, ensure_ascii=False, default=str)


# def _send_email_if_requested(
#     send_email: bool,
#     recipient: Optional[str],
#     candidate_name: Optional[str],
#     pdf_path: Path,
# ) -> Optional[str]:
#     if not send_email:
#         return None

#     recipient = _normalize_email(recipient)

#     if not recipient:
#         raise HTTPException(
#             status_code=400,
#             detail=(
#                 "send_email=True but no valid recipient email was provided. "
#                 "Please enter a real email address in 'to_email' or make sure the resume contains a valid email."
#             ),
#         )

#     smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
#     smtp_port = int(os.getenv("SMTP_PORT", "587"))
#     smtp_user = os.getenv("SMTP_USER", "")
#     smtp_password = os.getenv("SMTP_PASSWORD", "")
#     from_email = os.getenv("FROM_EMAIL", smtp_user)

#     if not smtp_user or not smtp_password:
#         raise HTTPException(
#             status_code=500,
#             detail="Missing SMTP_USER / SMTP_PASSWORD in environment variables.",
#         )

#     greeting_name = candidate_name or "Candidate"
#     body = (
#         f"Hi {greeting_name},\n\n"
#         "Please find attached your personalized Interview Q&A Pack "
#         "tailored to your resume and the job description.\n\n"
#         "Best of luck,\n"
#         "RecruitRiders Team"
#     )

#     try:
#         send_email_with_attachment(
#             to_email=recipient,
#             subject="Your Interview Q&A Pack",
#             body=body,
#             attachment_path=str(pdf_path),
#             from_email=from_email,
#             smtp_host=smtp_host,
#             smtp_port=smtp_port,
#             smtp_user=smtp_user,
#             smtp_password=smtp_password,
#         )
#         return f"Email sent successfully to {recipient}"
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Failed to send email: {e}") from e


# def run_full_workflow(
#     *,
#     resume_path: str,
#     jd_path: str,
#     interview_rounds: str,
#     answer_length: str = "answer_medium",
#     company: Optional[str] = None,
#     role: Optional[str] = None,
#     send_email: bool = False,
#     to_email: Optional[str] = None,
# ) -> WorkflowResponse:
#     if answer_length not in ALLOWED_ANSWER_LENGTHS:
#         raise HTTPException(
#             status_code=400,
#             detail=f"Invalid answer_length. Use one of: {sorted(ALLOWED_ANSWER_LENGTHS)}",
#         )

#     run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
#     run_output_dir = OUTPUT_DIR / run_id
#     run_output_dir.mkdir(parents=True, exist_ok=True)

#     # ---------------------------------------------------------
#     # 1. Agent 1: Parse Resume + JD
#     # ---------------------------------------------------------
#     try:
#         resume_out = run_agent1(resume_path)
#         jd_out = run_agent1(jd_path)
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Agent 1 failed: {e}") from e

#     combined_agent1_out: Dict[str, Any] = {
#         "doc_type": "combined_resume_and_jd",
#         "resume_data": resume_out,
#         "jd_data": jd_out,
#     }

#     agent1_out_path = run_output_dir / f"agent1_combined_out_{run_id}.json"
#     _write_json(agent1_out_path, combined_agent1_out)

#     resume_text = resume_out.get("raw_text_preview", "") or ""
#     jd_text = jd_out.get("raw_text_preview", "") or ""



#     # Best effort vector storage
#     # try:
#     #     if resume_text:
#     #         store_document_in_vector_db(
#     #             doc_id=f"res_{run_id}",
#     #             text=resume_text,
#     #             doc_type="resume",
#     #             candidate_id=run_id,
#     #         )
#     #     if jd_text:
#     #         store_document_in_vector_db(
#     #             doc_id=f"jd_{run_id}",
#     #             text=jd_text,
#     #             doc_type="job_description",
#     #             candidate_id=run_id,
#     #         )
#     # except Exception as e:
#     #     print(f"[Warning] Vector store write failed: {e}")

#     # ---------------------------------------------------------
#     # 2. Agent 2: Company Research
#     # ---------------------------------------------------------
#     try:
#         agent2_out = run_agent2(
#             jd_out,
#             company_override=company,
#             role_override=role,
#         )
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Agent 2 failed: {e}") from e

#     agent2_out_path = run_output_dir / f"agent2_out_{run_id}.json"
#     _write_json(agent2_out_path, agent2_out)

#     # ---------------------------------------------------------
#     # 3. Agent 3: Q&A Generator
#     # ---------------------------------------------------------
#     try:
#         agent3_out = run_agent3(
#             agent1_data=combined_agent1_out,
#             agent2_data=agent2_out,
#             agent1_path=str(agent1_out_path),
#             agent2_path=str(agent2_out_path),
#             interview_rounds=interview_rounds,
#             answer_length=answer_length,
#         )
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Agent 3 failed: {e}") from e

#     agent3_out_path = run_output_dir / f"agent3_out_{run_id}.json"
#     _write_json(agent3_out_path, agent3_out)

#     # ---------------------------------------------------------
#     # 4. Agent 4: Build PDF + optional email
#     # ---------------------------------------------------------
#     try:
#         extracted_email, candidate_name = extract_candidate_contact(resume_out)

#         recipient = _normalize_email(to_email) or _normalize_email(extracted_email)

#         pdf_filename = f"interview_qa_pack_{run_id}.pdf"
#         pdf_path = run_output_dir / pdf_filename

#         build_pdf(
#             agent3_out,
#             str(pdf_path),
#             candidate_name=candidate_name,
#             candidate_email=recipient,
#         )

#         email_status = _send_email_if_requested(
#             send_email=send_email,
#             recipient=recipient,
#             candidate_name=candidate_name,
#             pdf_path=pdf_path,
#         )

#         # Best effort relational save
#         try:
#             save_candidate_run(
#                 name=candidate_name,
#                 email=recipient,
#                 company=agent2_out.get("company_name", company),
#                 role=agent2_out.get("role_title", role),
#                 resume_path=resume_path,
#                 jd_path=jd_path,
#                 pdf_path=str(pdf_path),
#             )
#         except Exception as e:
#             print(f"[Warning] Relational DB save failed: {e}")

#     except HTTPException:
#         raise
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Dispatcher failed: {e}") from e

#     message = "Workflow completed successfully."
#     if email_status:
#         message = f"{message} {email_status}"

#     return WorkflowResponse(
#         success=True,
#         message=message,
#         run_id=run_id,
#         candidate_name=candidate_name,
#         recipient_email=recipient,
#         company=agent2_out.get("company_name", company),
#         role=agent2_out.get("role_title", role),
#         pdf_path=str(pdf_path),
#         pdf_download_url=f"/downloads/{run_id}/{pdf_filename}",
#         outputs={
#             "agent1_json": str(agent1_out_path),
#             "agent2_json": str(agent2_out_path),
#             "agent3_json": str(agent3_out_path),
#             "pdf": str(pdf_path),
#         },
#         agent1_output=combined_agent1_out,
#         agent2_output=agent2_out,
#         agent3_output=agent3_out,
#     )


# # -------------------------------------------------------------------
# # FastAPI lifespan
# # -------------------------------------------------------------------
# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
#     UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

#     try:
#         init_db()
#         print("[Startup] Relational DB initialized successfully.")
#     except Exception as e:
#         print(f"[Startup Warning] DB init failed: {e}")

#     yield

#     print("[Shutdown] FastAPI app shutting down.")


# # -------------------------------------------------------------------
# # FastAPI app
# # -------------------------------------------------------------------
# app = FastAPI(
#     title="Interview Preparation System API",
#     description="FastAPI wrapper for the multi-agent interview preparation workflow.",
#     version="1.0.0",
#     lifespan=lifespan,
# )

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# app.mount("/static", StaticFiles(directory=str(OUTPUT_DIR)), name="static")


# # -------------------------------------------------------------------
# # Routes
# # -------------------------------------------------------------------
# @app.get("/", tags=["Root"])
# async def root() -> Dict[str, Any]:
#     return {
#         "message": "Interview Preparation System API is running",
#         "docs": "/docs",
#         "health": "/health",
#     }


# @app.get("/health", tags=["Health"])
# async def health() -> Dict[str, str]:
#     return {"status": "ok"}


# @app.post("/workflow/run", response_model=WorkflowResponse, tags=["Workflow"])
# async def run_workflow_with_uploads(
#     resume: UploadFile = File(..., description="Candidate resume file"),
#     jd: UploadFile = File(..., description="Job description file"),
#     interview_rounds: str = Form(...),
#     answer_length: str = Form("answer_medium"),
#     company: Optional[str] = Form(None),
#     role: Optional[str] = Form(None),
#     send_email: bool = Form(False),
#     to_email: Optional[str] = Form(None),
# ) -> WorkflowResponse:
#     run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

#     try:
#         resume_path = _save_upload(resume, run_id, "resume")
#         jd_path = _save_upload(jd, run_id, "jd")

#         return run_full_workflow(
#             resume_path=str(resume_path),
#             jd_path=str(jd_path),
#             interview_rounds=interview_rounds,
#             answer_length=answer_length,
#             company=company,
#             role=role,
#             send_email=send_email,
#             to_email=to_email,
#         )
#     finally:
#         try:
#             await resume.close()
#         except Exception:
#             pass

#         try:
#             await jd.close()
#         except Exception:
#             pass


# @app.post("/workflow/run-from-paths", response_model=WorkflowResponse, tags=["Workflow"])
# async def run_workflow_from_paths(payload: WorkflowRequest) -> WorkflowResponse:
#     if not Path(payload.resume_path).exists():
#         raise HTTPException(status_code=400, detail="resume_path does not exist")

#     if not Path(payload.jd_path).exists():
#         raise HTTPException(status_code=400, detail="jd_path does not exist")

#     return run_full_workflow(
#         resume_path=payload.resume_path,
#         jd_path=payload.jd_path,
#         interview_rounds=payload.interview_rounds,
#         answer_length=payload.answer_length,
#         company=payload.company,
#         role=payload.role,
#         send_email=payload.send_email,
#         to_email=payload.to_email,
#     )


# @app.get("/downloads/{run_id}/{filename}", tags=["Downloads"])
# async def download_generated_file(run_id: str, filename: str):
#     file_path = OUTPUT_DIR / run_id / filename

#     if not file_path.exists():
#         raise HTTPException(status_code=404, detail="File not found")

#     return FileResponse(
#         path=str(file_path),
#         filename=filename,
#         media_type="application/octet-stream",
#     )


# @app.get("/runs/{run_id}", tags=["Runs"])
# async def get_run_metadata(run_id: str):
#     run_dir = OUTPUT_DIR / run_id

#     if not run_dir.exists():
#         raise HTTPException(status_code=404, detail="Run not found")

#     files = [str(p.name) for p in run_dir.iterdir() if p.is_file()]
#     return {
#         "run_id": run_id,
#         "files": files,
#         "path": str(run_dir),
#     }


# @app.exception_handler(Exception)
# async def unhandled_exception_handler(request: Request, exc: Exception):
#     return JSONResponse(
#         status_code=500,
#         content={
#             "success": False,
#             "message": "Unexpected server error",
#             "detail": str(exc),
#         },
#     )


# # -------------------------------------------------------------------
# # Local run
# # -------------------------------------------------------------------
# if __name__ == "__main__":
#     import uvicorn

#     uvicorn.run(
#         "app.main:app",
#         host="0.0.0.0",
#         port=8000,
#         reload=True,
#     )