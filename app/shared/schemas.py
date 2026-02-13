from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional, Dict

# --- Agent 1 Output Models ---
class Agent1ParsedDoc(BaseModel):
    file_path: str = Field(..., description="Path to the processed file.")
    doc_type: str = Field(..., description="resume | job_description | interview_notes | policy | unknown")
    summary: str = Field(..., description="Short summary of the document.")
    key_points: list[str] = Field(default_factory=list, description="Key points as bullets.")
    entities: Dict[str, list[str]] = Field(
        default_factory=dict,
        description="Grouped entities e.g. {'skills':[], 'tools':[], 'companies':[], 'roles':[]}",
    )
    raw_text_preview: str = Field(..., description="First ~1200 chars preview of extracted text.")

# class JobInfo(BaseModel):
#     title: str = Field(..., description="The job title or role")
#     skills_required: List[str] = Field(..., description="List of technical and soft skills")
#     responsibilities: List[str] = Field(..., description="Main duties of the role")
#     interview_rounds: Optional[str] = Field(None, description="Info on the interview process")
#     company_name: str = Field(..., description="The name of the hiring company")

# class CandidateInfo(BaseModel):
#     name: str
#     email: EmailStr
#     education: List[str]
#     key_skills: List[str]
#     experience_years: int
#     resume_summary: str

# --- Agent 2 Output Model ---
class CompanyInfo(BaseModel):
    description: str = Field(..., description="What the company does")
    mission_values: List[str] = Field(default_factory=list)
    recent_news: List[str] = Field(default_factory=list, description="Key recent events or projects")
    culture_notes: Optional[str] = None

# --- Agent 3 Output Models ---
class InterviewQA(BaseModel):
    question: str
    detailed_answer: str

class PrepPackage(BaseModel):
    top_20_qa: List[InterviewQA]
    additional_questions: List[str] = Field(..., description="Extra questions without answers")
