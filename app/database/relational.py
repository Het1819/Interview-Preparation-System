import os
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

Base = declarative_base()

class CandidateRecord(Base):
    __tablename__ = 'candidates'
    id = Column(Integer, primary_key=True, autoincrement=True)
    candidate_name = Column(String, nullable=True)
    candidate_email = Column(String, nullable=True)
    job_company = Column(String, nullable=True)
    job_role = Column(String, nullable=True)
    resume_path = Column(String, nullable=False)
    jd_path = Column(String, nullable=False)
    pdf_output_path = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

# Setup SQLite database in the output folder
DB_PATH = "sqlite:///app/database_output/interview_system.db"
engine = create_engine(DB_PATH)
SessionLocal = sessionmaker(bind=engine)

def init_db():
    Base.metadata.create_all(engine)

def save_candidate_run(name, email, company, role, resume_path, jd_path, pdf_path):
    session = SessionLocal()
    new_record = CandidateRecord(
        candidate_name=name,
        candidate_email=email,
        job_company=company,
        job_role=role,
        resume_path=resume_path,
        jd_path=jd_path,
        pdf_output_path=pdf_path
    )
    session.add(new_record)
    session.commit()
    session.close()