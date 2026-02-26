from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional, Dict, Any

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

class NewsItem(BaseModel):
    title: str = Field(..., description="News headline")
    source: str = Field(..., description="Publisher/source name")
    date: Optional[str] = Field(None, description="Publish date if available")
    url: str = Field(..., description="Source URL")
    summary: str = Field(..., description="1-2 line summary")

class CompanyResearchReport(BaseModel):
    company_name: str = Field(..., description="Company name")
    role_title: Optional[str] = Field(None, description="Role title if available")

    overview: str = Field(..., description="What the company does in 2-4 lines")
    mission_values: List[str] = Field(default_factory=list, description="Mission/values bullets")
    products_services: List[str] = Field(default_factory=list, description="Key products/services")
    business_model: List[str] = Field(default_factory=list, description="How they make money (high-level)")

    interview_focus: List[str] = Field(default_factory=list, description="Likely interview focus areas")
    interview_process: List[str] = Field(default_factory=list, description="Stages/rounds if found")

    recent_news: List[NewsItem] = Field(default_factory=list, description="Recent relevant news")
    sources: List[str] = Field(default_factory=list, description="URLs used")

    notes: Optional[str] = Field(None, description="Caveats / missing info")


# class CompanyInfo(BaseModel):
#     description: str = Field(..., description="What the company does")
#     mission_values: List[str] = Field(default_factory=list)
#     recent_news: List[str] = Field(default_factory=list, description="Key recent events or projects")
#     culture_notes: Optional[str] = None





# --- Agent 3 Output Models ---
class QAItem(BaseModel):
    round: str = Field(..., description="Which interview round this Q/A belongs to (must be one of provided rounds).")
    question: str = Field(..., description="Interview question.")
    answer: str = Field(..., description="Detailed answer with examples/steps where relevant.")
    focus_area: str = Field(..., description="Skill/area assessed e.g. SQL, Python, Power BI, ETL, Stakeholder mgmt, System design, Behavioral.")
    difficulty: str = Field(..., description="easy | medium | hard")

class Agent3QAOutput(BaseModel):
    input: Dict[str, Any] = Field(..., description="Inputs summary: file paths, doc_type, rounds used.")
    top_30: List[QAItem] = Field(..., description="Top 30 detailed questions and answers.")
    top_20_questions: List[str] = Field(..., description="Top 20 questions only (shortlist).")
    notes: List[str] = Field(default_factory=list, description="Any assumptions/notes.")


# class InterviewQA(BaseModel):
#     question: str
#     detailed_answer: str

# class PrepPackage(BaseModel):
#     top_20_qa: List[InterviewQA]
#     additional_questions: List[str] = Field(..., description="Extra questions without answers")
