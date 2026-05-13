# # import os
# # from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
# # from sqlalchemy.orm import declarative_base, sessionmaker
# # from datetime import datetime

# # Base = declarative_base()

# # class CandidateRecord(Base):
# #     __tablename__ = 'candidates'
# #     id = Column(Integer, primary_key=True, autoincrement=True)
# #     candidate_name = Column(String, nullable=True)
# #     candidate_email = Column(String, nullable=True)
# #     job_company = Column(String, nullable=True)
# #     job_role = Column(String, nullable=True)
# #     resume_path = Column(String, nullable=False)
# #     jd_path = Column(String, nullable=False)
# #     pdf_output_path = Column(String, nullable=True)
# #     created_at = Column(DateTime, default=datetime.utcnow)

# # # Setup SQLite database in the output folder
# # DB_PATH = "sqlite:///app/database_output/interview_system.db"
# # engine = create_engine(DB_PATH)
# # SessionLocal = sessionmaker(bind=engine)

# # def init_db():
# #     Base.metadata.create_all(engine)

# # def save_candidate_run(name, email, company, role, resume_path, jd_path, pdf_path):
# #     session = SessionLocal()
# #     new_record = CandidateRecord(
# #         candidate_name=name,
# #         candidate_email=email,
# #         job_company=company,
# #         job_role=role,
# #         resume_path=resume_path,
# #         jd_path=jd_path,
# #         pdf_output_path=pdf_path
# #     )
# #     session.add(new_record)
# #     session.commit()
# #     session.close()





# import os
# import json
# from pathlib import Path
# from datetime import datetime
# from typing import Any, Optional

# from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, inspect, text
# from sqlalchemy.orm import declarative_base, sessionmaker

# Base = declarative_base()


# class CandidateRecord(Base):
#     __tablename__ = "candidates"

#     id = Column(Integer, primary_key=True, autoincrement=True)

#     candidate_name = Column(String, nullable=True)
#     candidate_email = Column(String, nullable=True)
#     job_company = Column(String, nullable=True)
#     job_role = Column(String, nullable=True)

#     resume_path = Column(String, nullable=False)
#     jd_path = Column(String, nullable=False)
#     pdf_output_path = Column(String, nullable=True)

#     # New columns for storing agent outputs
#     agent_1_output = Column(Text, nullable=True)
#     agent_2_output = Column(Text, nullable=True)
#     agent_3_output = Column(Text, nullable=True)

#     created_at = Column(DateTime, default=datetime.utcnow)


# # Setup SQLite database in the output folder
# DB_DIR = Path("app/database_output")
# DB_DIR.mkdir(parents=True, exist_ok=True)

# DB_FILE = DB_DIR / "interview_system.db"
# DB_PATH = f"sqlite:///{DB_FILE.as_posix()}"

# engine = create_engine(
#     DB_PATH,
#     connect_args={"check_same_thread": False}
# )

# SessionLocal = sessionmaker(bind=engine)


# def _json_to_text(payload: Optional[Any]) -> Optional[str]:
#     """
#     Converts Python dict/list data into JSON string before saving to SQLite.
#     """
#     if payload is None:
#         return None

#     if isinstance(payload, str):
#         return payload

#     return json.dumps(payload, ensure_ascii=False, default=str)


# def _ensure_candidate_columns():
#     """
#     Adds missing columns to existing SQLite candidates table.
#     This is required because SQLAlchemy create_all() does not update existing tables.
#     """
#     inspector = inspect(engine)

#     existing_tables = inspector.get_table_names()
#     if "candidates" not in existing_tables:
#         return

#     existing_columns = {
#         column["name"] for column in inspector.get_columns("candidates")
#     }

#     required_columns = {
#         "agent_1_output": "TEXT",
#         "agent_2_output": "TEXT",
#         "agent_3_output": "TEXT",
#     }

#     with engine.begin() as connection:
#         for column_name, column_type in required_columns.items():
#             if column_name not in existing_columns:
#                 connection.execute(
#                     text(f"ALTER TABLE candidates ADD COLUMN {column_name} {column_type}")
#                 )


# def init_db():
#     Base.metadata.create_all(engine)
#     _ensure_candidate_columns()


# def save_candidate_run(
#     name,
#     email,
#     company,
#     role,
#     resume_path,
#     jd_path,
#     pdf_path,
#     agent_1_output=None,
#     agent_2_output=None,
#     agent_3_output=None,
# ):
#     session = SessionLocal()

#     try:
#         new_record = CandidateRecord(
#             candidate_name=name,
#             candidate_email=email,
#             job_company=company,
#             job_role=role,
#             resume_path=resume_path,
#             jd_path=jd_path,
#             pdf_output_path=pdf_path,

#             # Store agent outputs as JSON text
#             agent_1_output=_json_to_text(agent_1_output),
#             agent_2_output=_json_to_text(agent_2_output),
#             agent_3_output=_json_to_text(agent_3_output),
#         )

#         session.add(new_record)
#         session.commit()
#         session.refresh(new_record)

#         return new_record.id

#     except Exception:
#         session.rollback()
#         raise

#     finally:
#         session.close()






########################################################################

# import os
# from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
# from sqlalchemy.orm import declarative_base, sessionmaker
# from datetime import datetime

# Base = declarative_base()

# class CandidateRecord(Base):
#     __tablename__ = 'candidates'
#     id = Column(Integer, primary_key=True, autoincrement=True)
#     candidate_name = Column(String, nullable=True)
#     candidate_email = Column(String, nullable=True)
#     job_company = Column(String, nullable=True)
#     job_role = Column(String, nullable=True)
#     resume_path = Column(String, nullable=False)
#     jd_path = Column(String, nullable=False)
#     pdf_output_path = Column(String, nullable=True)
#     created_at = Column(DateTime, default=datetime.utcnow)

# # Setup SQLite database in the output folder
# DB_PATH = "sqlite:///app/database_output/interview_system.db"
# engine = create_engine(DB_PATH)
# SessionLocal = sessionmaker(bind=engine)

# def init_db():
#     Base.metadata.create_all(engine)

# def save_candidate_run(name, email, company, role, resume_path, jd_path, pdf_path):
#     session = SessionLocal()
#     new_record = CandidateRecord(
#         candidate_name=name,
#         candidate_email=email,
#         job_company=company,
#         job_role=role,
#         resume_path=resume_path,
#         jd_path=jd_path,
#         pdf_output_path=pdf_path
#     )
#     session.add(new_record)
#     session.commit()
#     session.close()





import os
import json
from pathlib import Path
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()


class CandidateRecord(Base):
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True, autoincrement=True)

    candidate_name = Column(String, nullable=True)
    candidate_email = Column(String, nullable=True)
    job_company = Column(String, nullable=True)
    job_role = Column(String, nullable=True)

    resume_path = Column(String, nullable=False)
    jd_path = Column(String, nullable=False)
    pdf_output_path = Column(String, nullable=True)

    # Unique run identifier — used by the download endpoint to fetch the right record
    run_id = Column(String, nullable=True, index=True)

    # Agent outputs stored as JSON text (no files written to disk)
    agent_1_output = Column(Text, nullable=True)
    agent_2_output = Column(Text, nullable=True)
    agent_3_output = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)


# Setup SQLite database in the output folder
DB_DIR = Path("app/database_output")
DB_DIR.mkdir(parents=True, exist_ok=True)

DB_FILE = DB_DIR / "interview_system.db"
DB_PATH = f"sqlite:///{DB_FILE.as_posix()}"

engine = create_engine(
    DB_PATH,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(bind=engine)


def _json_to_text(payload: Optional[Any]) -> Optional[str]:
    """
    Converts Python dict/list data into JSON string before saving to SQLite.
    """
    if payload is None:
        return None

    if isinstance(payload, str):
        return payload

    return json.dumps(payload, ensure_ascii=False, default=str)


def _ensure_candidate_columns():
    """
    Adds missing columns to existing SQLite candidates table.
    This is required because SQLAlchemy create_all() does not update existing tables.
    """
    inspector = inspect(engine)

    existing_tables = inspector.get_table_names()
    if "candidates" not in existing_tables:
        return

    existing_columns = {
        column["name"] for column in inspector.get_columns("candidates")
    }

    required_columns = {
        "agent_1_output": "TEXT",
        "agent_2_output": "TEXT",
        "agent_3_output": "TEXT",
        "run_id":         "TEXT",
    }

    with engine.begin() as connection:
        for column_name, column_type in required_columns.items():
            if column_name not in existing_columns:
                connection.execute(
                    text(f"ALTER TABLE candidates ADD COLUMN {column_name} {column_type}")
                )


def init_db():
    Base.metadata.create_all(engine)
    _ensure_candidate_columns()


def save_candidate_run(
    name,
    email,
    company,
    role,
    resume_path,
    jd_path,
    pdf_path,
    run_id=None,
    agent_1_output=None,
    agent_2_output=None,
    agent_3_output=None,
):
    session = SessionLocal()

    try:
        new_record = CandidateRecord(
            candidate_name=name,
            candidate_email=email,
            job_company=company,
            job_role=role,
            resume_path=resume_path,
            jd_path=jd_path,
            pdf_output_path=pdf_path,

            run_id=run_id,

            # Store agent outputs as JSON text
            agent_1_output=_json_to_text(agent_1_output),
            agent_2_output=_json_to_text(agent_2_output),
            agent_3_output=_json_to_text(agent_3_output),
        )

        session.add(new_record)
        session.commit()
        session.refresh(new_record)

        return new_record.id

    except Exception:
        session.rollback()
        raise

    finally:
        session.close()


def get_candidate_by_run_id(run_id: str) -> Optional[dict]:
    """
    Fetch the candidate record for a given run_id.
    Returns a plain dict with the fields needed by the download endpoint,
    or None if not found.
    """
    session = SessionLocal()
    try:
        record = (
            session.query(CandidateRecord)
            .filter(CandidateRecord.run_id == run_id)
            .first()
        )
        if record is None:
            return None

        agent3_raw = record.agent_3_output
        agent3_data = json.loads(agent3_raw) if agent3_raw else {}

        return {
            "run_id":         record.run_id,
            "candidate_name": record.candidate_name,
            "candidate_email": record.candidate_email,
            "agent_3_output": agent3_data,
        }
    finally:
        session.close()