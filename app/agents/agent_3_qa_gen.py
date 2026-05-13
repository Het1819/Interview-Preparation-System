# from __future__ import annotations

# import os
# import re
# import json
# import argparse
# from typing import Any, Dict, List, Optional

# from dotenv import load_dotenv
# load_dotenv()

# from pydantic import BaseModel, Field

# from langchain.agents import create_agent
# from langchain_google_genai import ChatGoogleGenerativeAI
# from langchain_anthropic import ChatAnthropic
# import time


# # ----------------------------
# # Output schema
# # ----------------------------

# class QAItem(BaseModel):
#     round: str = Field(..., description="Which interview round this Q/A belongs to.")
#     question: str = Field(..., description="Interview question.")
#     answer: str = Field(..., description="Interview answer generated based on selected --answer_length.")
#     focus_area: str = Field(..., description="Skill/area assessed.")
#     difficulty: str = Field(..., description="easy | medium | hard")
    
# # class QAItem(BaseModel):
# #     round: str = Field(..., description="Which interview round this Q/A belongs to.")
# #     question: str = Field(..., description="Interview question.")
# #     answer: str = Field(..., description="Main answer chosen based on --answer_length.")
# #     answer_small: str = Field(..., description="Small answer in point form.")
# #     answer_medium: str = Field(..., description="Medium answer in point form.")
# #     answer_large: str = Field(..., description="Large answer in point form.")
# #     focus_area: str = Field(..., description="Skill/area assessed.")
# #     difficulty: str = Field(..., description="easy | medium | hard")


# class Agent3QAOutput(BaseModel):
#     input: Dict[str, Any] = Field(..., description="Inputs summary.")
#     top_30: List[QAItem] = Field(..., description="Top 30 interview questions and answers.")
#     top_20_questions: List[str] = Field(..., description="Top 20 questions only.")
#     notes: List[str] = Field(default_factory=list, description="Any assumptions/notes.")


# # ----------------------------
# # Helpers
# # ----------------------------

# def normalize_model_content(content: Any) -> str:
#     if content is None:
#         return ""
#     if isinstance(content, str):
#         return content

#     if isinstance(content, list):
#         chunks = []
#         for part in content:
#             if isinstance(part, dict) and isinstance(part.get("text"), str):
#                 chunks.append(part["text"])
#             else:
#                 chunks.append(str(part))
#         return "\n".join(chunks)

#     return str(content)


# def _get_last_ai_content(agent_result: Dict[str, Any]) -> str:
#     msgs = agent_result.get("messages", [])
#     if not msgs:
#         return ""
#     last = msgs[-1]
#     if isinstance(last, dict):
#         return normalize_model_content(last.get("content"))
#     return normalize_model_content(getattr(last, "content", ""))


# def extract_json_object(text: str) -> Optional[Dict[str, Any]]:
#     if not text:
#         return None

#     text = text.strip()

#     fenced = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL | re.IGNORECASE)
#     if fenced:
#         candidate = fenced.group(1).strip()
#         try:
#             return json.loads(candidate)
#         except Exception:
#             pass

#     try:
#         return json.loads(text)
#     except Exception:
#         pass

#     block = re.search(r"(\{.*\})", text, re.DOTALL)
#     if block:
#         candidate = block.group(1).strip()
#         try:
#             return json.loads(candidate)
#         except Exception:
#             return None

#     return None


# def _split_sentences(text: str) -> List[str]:
#     text = re.sub(r"\s+", " ", (text or "").strip())
#     if not text:
#         return []
#     parts = re.split(r"(?<=[.!?])\s+", text)
#     return [p.strip(" -•\t\r\n") for p in parts if p.strip(" -•\t\r\n")]


# def _to_bullets(text: str, max_items: Optional[int] = None) -> str:
#     text = (text or "").strip()
#     if not text:
#         return ""

#     lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
#     bullet_like = []
#     for ln in lines:
#         if re.match(r"^[-•*]\s+", ln) or re.match(r"^\d+[\).\s]", ln):
#             bullet_like.append(ln)

#     if bullet_like:
#         cleaned = []
#         for ln in bullet_like:
#             ln = re.sub(r"^\d+[\).\s]+", "", ln).strip()
#             ln = re.sub(r"^[-•*]\s+", "", ln).strip()
#             if ln:
#                 cleaned.append(f"- {ln}")
#         if max_items:
#             cleaned = cleaned[:max_items]
#         return "\n".join(cleaned)

#     parts = _split_sentences(text)
#     if max_items:
#         parts = parts[:max_items]
#     return "\n".join(f"- {p}" for p in parts if p)


# # def _make_small_answer(source_text: str) -> str:
# #     bullets = _to_bullets(source_text, max_items=3)
# #     return bullets or "- I would answer this briefly based on the experience and tools reflected in my resume."


# # def _make_medium_answer(source_text: str) -> str:
# #     bullets = _to_bullets(source_text, max_items=5)
# #     return bullets or "- I would answer this with balanced depth tied to my experience, approach, and impact."


# # def _make_large_answer(source_text: str) -> str:
# #     bullets = _to_bullets(source_text, max_items=8)
# #     return bullets or "- I would answer this in more depth by covering the problem, approach, technical choices, validation, and outcome."


# # def normalize_qa_item(item: Dict[str, Any], answer_length: str = "answer_medium") -> Dict[str, Any]:
# #     if not isinstance(item, dict):
# #         item = {}

# #     base_answer = str(item.get("answer", "")).strip()
# #     answer_small = str(item.get("answer_small") or "").strip()
# #     answer_medium = str(item.get("answer_medium") or "").strip()
# #     answer_large = str(item.get("answer_large") or "").strip()

# #     seed_text = answer_large or answer_medium or base_answer or answer_small

# #     if not answer_small:
# #         answer_small = _make_small_answer(seed_text)
# #     else:
# #         answer_small = _make_small_answer(answer_small)

# #     if not answer_medium:
# #         answer_medium = _make_medium_answer(seed_text)
# #     else:
# #         answer_medium = _make_medium_answer(answer_medium)

# #     if not answer_large:
# #         answer_large = _make_large_answer(seed_text or answer_medium)
# #     else:
# #         answer_large = _make_large_answer(answer_large)

# #     item["answer_small"] = answer_small
# #     item["answer_medium"] = answer_medium
# #     item["answer_large"] = answer_large

# #     if answer_length == "answer_small":
# #         item["answer"] = answer_small
# #     elif answer_length == "answer_large":
# #         item["answer"] = answer_large
# #     else:
# #         item["answer"] = answer_medium

# #     item["round"] = str(item.get("round", "")).strip()
# #     item["question"] = str(item.get("question", "")).strip()
# #     item["focus_area"] = str(item.get("focus_area", "")).strip()
# #     item["difficulty"] = str(item.get("difficulty", "medium")).strip().lower() or "medium"

# #     if item["difficulty"] not in {"easy", "medium", "hard"}:
# #         item["difficulty"] = "medium"

# #     return item


# # ----------------------------
# # Agent 3 Builder
# # ----------------------------

# def build_agent3(
#     # model_name: str = "gemini-2.5-pro",
#     # model_name: str = "gemini-3-flash",
#     model_name: str = "gemini-2.5-flash",
#     temperature: float = 0.25,
# ):
#     api_key = os.getenv("GOOGLE_API_KEY")
#     anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
#     if not api_key:
#         raise EnvironmentError("Missing GOOGLE_API_KEY in environment variables.")

#     llm = ChatGoogleGenerativeAI(
#         model=model_name,
#         temperature=temperature,
#         google_api_key=api_key,
#         timeout=180,
#         max_retries=2,
#     )

#     llm_anthropic = ChatAnthropic(
#         model='claude-3-5-sonnet-20241022',
#         temperature=temperature,
#         api_key=anthropic_api_key,
#         timeout=180,
#         max_retries=2,
#     )

#     system_prompt = """
# You are Agent 3: Interview Q&A Generator.

# You will receive:
# 1) Agent 1 JSON: parsed document fields.
# 2) Agent 2 JSON: research/context enrichment.
# 3) Interview rounds string provided by the user.

# Your job:
# - Generate interview questions and answers strictly aligned to the provided interview rounds.
# - Output ONLY valid JSON. No markdown. No backticks. No extra text.

# Output requirements:
# A) "top_30": exactly 30 items. Each item must include:
# - round
# - question
# - answer
# - focus_area
# - difficulty
# # - answer_small
# # - answer_medium
# # - answer_large

# Answer style rules:
# - All three answers must be in point form using short bullet lines inside the JSON string.
# Answer style rules based on answer_length:
# - If answer_length = "answer_small":
#   - Give a crisp screening-style answer
#   - Usually 3 to 4 short bullet points
# - If answer_length = "answer_medium":
#   - Give a balanced interview answer
#   - Usually 4 to 7 short bullet points
# - If answer_length = "answer_large":
#   - Give a deeper answer with more technical depth or story detail
#   - Usually 6 to 10 short bullet points

# # - answer_small:
# #   - Crisp screening answer
# #   - Usually 3 to 4 bullets
# # - answer_medium:
# #   - Balanced interview answer
# #   - Usually 4 to 7 bullets
# # - answer_large:
# #   - Deep answer with richer technical depth or story detail
# #   - Usually 6 to 10 bullets


# - If the question is experience-based:
#   - answer using a story shape: problem, action, technical depth, impact
# - If the question is scenario-based:
#   - answer step-by-step with decision reasoning
# - If the question is directly technical:
#   - answer in a structured, confident, technical way
# - Add measurable impact wherever grounded in Agent 1 / Agent 2
# - Align every answer tightly to the resume, JD, and company context available
# - Do not invent experience not present in Agent 1

# B) "top_20_questions": exactly 20 strings.
# C) All Q/A must be based on:
# - Candidate/resume content from Agent 1
# - Research/context from Agent 2
# - Interview rounds specified by user
# - Questions should be different from previously provided 

# Constraints:
# - If Agent 2 lacks company specifics, keep questions role-based and skill-based.
# - Ensure realistic distribution across rounds.
# - Keep focus_area short and specific.
# - Return JSON with double quotes only.

# JSON schema:
# {
#   "input": {
#     "agent1_file": "string",
#     "agent2_file": "string",
#     "doc_type": "string",
#     "rounds": ["string", "..."],
#     "answer_length": "answer_small|answer_medium|answer_large"
#   },
#   "top_30": [
#     {
#       "round": "string",
#       "question": "string",
#       "answer": "string",
#     #   "answer_small": "string",
#     #   "answer_medium": "string",
#     #   "answer_large": "string",
#       "focus_area": "string",
#       "difficulty": "easy|medium|hard"
#     }
#   ],
#   "top_20_questions": ["string", "..."],
#   "notes": ["string", "..."]
# }
# """

#     agent = create_agent(
#         model=[llm, llm_anthropic],
#         tools=[],
#         system_prompt=system_prompt,
#     )
#     return agent


# # ----------------------------
# # Core runner
# # ----------------------------
# # import re
# # import json
# # import asyncio
# # from typing import Dict, Any

# def run_agent3(
#     agent1_data: Dict[str, Any],
#     agent2_data: Dict[str, Any],
#     agent1_path: str,
#     agent2_path: str,
#     interview_rounds: str,
#     answer_length: str = "answer_medium",
# ) -> Dict[str, Any]:
#     rounds = [r.strip() for r in re.split(r"[;\n|,]+", interview_rounds) if r.strip()]
#     if not rounds:
#         rounds = ["Recruiter Screen", "Technical Round", "Hiring Manager", "Behavioral"]

#     if answer_length not in {"answer_small", "answer_medium", "answer_large"}:
#         answer_length = "answer_medium"

#     agent = build_agent3()

#     user_payload = {
#         "agent1_json": agent1_data,
#         "agent2_json": agent2_data,
#         "interview_rounds": rounds,
#         "agent1_file": agent1_path,
#         "agent2_file": agent2_path,
#         "answer_length": answer_length,
#     }
#     max_attempts = 3
#     initial_delay = 1
#     exp_base = 2

#     last_error = None
#     result = None
    
#     for attempt in range(max_attempts):
#         try:
#             result = agent.invoke(
#                 {
#                     "messages": [
#                         {
#                             "role": "user",
#                             "content": (
#                                 "Generate Q&A now using the following JSON inputs.\n"
#                                 "Return ONLY valid JSON.\n\n"
#                                 + json.dumps(user_payload, ensure_ascii=False)
#                             ),
#                         }
#                     ]
#                 }
#             )
#             break
#         except Exception as e:
#                 last_error = str(e)
#                 if attempt == max_attempts - 1:
#                     return {"error": f"Agent invocation failed after retries: {last_error}"}
#                 delay = initial_delay * (exp_base ** attempt)
#                 time.sleep(delay)
#     text = _get_last_ai_content(result).strip()
#     data = extract_json_object(text)

#     if not data:
#         return {"error": "Failed to parse JSON from agent output.", "raw_output": text}

#     try:
#         data.setdefault("input", {})
#         data["input"].setdefault("agent1_file", agent1_path)
#         data["input"].setdefault("agent2_file", agent2_path)
#         data["input"].setdefault("doc_type", str(agent1_data.get("doc_type", "unknown")))
#         data["input"].setdefault("rounds", rounds)
#         data["input"].setdefault("answer_length", answer_length)

#         top_30 = data.get("top_30", [])
#         if isinstance(top_30, list) and len(top_30) > 30:
#             data["top_30"] = top_30[:30]
#         elif isinstance(top_30, list) and len(top_30) < 30:
#             data.setdefault("notes", [])
#             data["notes"].append(
#                 f"Model returned {len(top_30)} items in top_30 (expected 30)."
#             )

#         if isinstance(data.get("top_30"), list):
#             cleaned_items = []
#             for item in data["top_30"]:
#                 if not isinstance(item, dict):
#                     item = {}

#                 cleaned_item = {
#                     "round": str(item.get("round", "")).strip(),
#                     "question": str(item.get("question", "")).strip(),
#                     "answer": str(item.get("answer", "")).strip(),
#                     "focus_area": str(item.get("focus_area", "")).strip(),
#                     "difficulty": str(item.get("difficulty", "medium")).strip().lower() or "medium",
#                 }

#                 if cleaned_item["difficulty"] not in {"easy", "medium", "hard"}:
#                     cleaned_item["difficulty"] = "medium"

#                 if not cleaned_item["answer"]:
#                     cleaned_item["answer"] = "- I would answer this based on my resume-aligned experience and approach."

#                 cleaned_items.append(cleaned_item)

#             data["top_30"] = cleaned_items

#         # top_30 = data.get("top_30", [])
#         # if isinstance(top_30, list) and len(top_30) > 30:
#         #     data["top_30"] = top_30[:30]
#         # elif isinstance(top_30, list) and len(top_30) < 30:
#         #     data.setdefault("notes", [])
#         #     data["notes"].append(
#         #         f"Model returned {len(top_30)} items in top_30 (expected 30)."
#         #     )

#         # if isinstance(data.get("top_30"), list):
#         #     normalized_items = []
#         #     for item in data["top_30"]:
#         #         normalized_items.append(normalize_qa_item(item, answer_length=answer_length))
#         #     data["top_30"] = normalized_items

#         top_20 = data.get("top_20_questions", [])
#         if isinstance(top_20, list) and len(top_20) > 20:
#             data["top_20_questions"] = top_20[:20]
#         elif isinstance(top_20, list) and len(top_20) < 20:
#             if isinstance(data.get("top_30"), list):
#                 derived = []
#                 for item in data["top_30"]:
#                     q = item.get("question") if isinstance(item, dict) else None
#                     if q and q not in derived:
#                         derived.append(q)
#                     if len(derived) == 20:
#                         break
#                 data["top_20_questions"] = derived
#                 data.setdefault("notes", [])
#                 data["notes"].append("top_20_questions was auto-derived from top_30.")

#         data.setdefault("notes", [])
#         data["notes"].append(f"The main `answer` field mirrors `{answer_length}`.")

#     except Exception as e:
#         return {"error": f"Post-processing failed: {e}", "raw_output": data}

#     return data


# # ----------------------------
# # CLI
# # ----------------------------

# def main():
#     parser = argparse.ArgumentParser(description="Agent 3 - Interview Q&A Generator")
#     parser.add_argument("--agent1_json", required=True, help="Path to Agent 1 output JSON file")
#     parser.add_argument("--agent2_json", required=True, help="Path to Agent 2 output JSON file")
#     parser.add_argument("--interview_rounds", required=True, help="Interview rounds separated by ; or , or newline")
#     parser.add_argument(
#         "--answer_length",
#         default="answer_medium",
#         choices=["answer_small", "answer_medium", "answer_large"],
#         help="Choose which answer version should be copied into the main `answer` field"
#     )
#     parser.add_argument("--out_json", default="app/output/03_Test_Case_agent3_qa_02.json", help="Output path for Agent 3 JSON")

#     args = parser.parse_args()

#     if not os.path.exists(args.agent1_json):
#         raise FileNotFoundError(f"Agent1 JSON not found: {args.agent1_json}")
#     if not os.path.exists(args.agent2_json):
#         raise FileNotFoundError(f"Agent2 JSON not found: {args.agent2_json}")

#     with open(args.agent1_json, "r", encoding="utf-8") as f:
#         agent1_data = json.load(f)

#     with open(args.agent2_json, "r", encoding="utf-8") as f:
#         agent2_data = json.load(f)

#     out = run_agent3(
#         agent1_data=agent1_data,
#         agent2_data=agent2_data,
#         agent1_path=args.agent1_json,
#         agent2_path=args.agent2_json,
#         interview_rounds=args.interview_rounds,
#         answer_length=args.answer_length,
#     )

#     os.makedirs(os.path.dirname(args.out_json), exist_ok=True)
#     with open(args.out_json, "w", encoding="utf-8") as f:
#         json.dump(out, f, indent=2, ensure_ascii=False)

#     print(f"[Agent3] Output written to: {args.out_json}")
#     print(json.dumps(out if "error" in out else {"status": "ok"}, indent=2, ensure_ascii=False))

#     legacy_out_path = "app/output/03_Test_case_agent_3_QA.json"
#     os.makedirs(os.path.dirname(legacy_out_path), exist_ok=True)
#     with open(legacy_out_path, "w", encoding="utf-8") as f:
#         json.dump(out, f, indent=2, ensure_ascii=False)


# if __name__ == "__main__":
#     main()



# # Provide the interview rounds by  
# # Round 1 - Recruiter Screen
# # Round 2 - Technical (Core Skills)
# # Round 3 - Technical (Project + Design)
# # Round 4 - Hiring Manager
# # Round 5 - Behavioral

# # python -m app.agents.agente_3_qa_gen ^
# #   --agent1_json app/output/01_agent1.json ^
# #   --agent2_json app/output/02_agent2.json ^
# #   --interview_rounds "Recruiter Screen; Technical Round; Hiring Manager; Behavioral" ^
# #   --answer_length answer_medium ^
# #   --out_json app/output/03_agent3_qa.json


# # Run the 3rd Agent
# # python -m app.agents.agent_3_qa_gen --agent1_json "app/output/agent1.json" --agent2_json "app/output/agent2.json" --interview_rounds "Recruiter Screen; Technical Round 1 (SQL/Python); Technical Round 2 (BI/ETL); Hiring Manager; Behavioral" --out_json "app/output/agent3_qa.json"































from __future__ import annotations

import argparse
import json
import os
import re
import time
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field

from langchain.agents import create_agent
from langchain_google_genai import ChatGoogleGenerativeAI

try:
    from langchain_anthropic import ChatAnthropic
except ImportError:  # Anthropic is optional now.
    ChatAnthropic = None  # type: ignore[assignment]

load_dotenv()


# ----------------------------
# Output schema
# ----------------------------

class QAItem(BaseModel):
    round: str = Field(..., description="Which interview round this Q/A belongs to.")
    question: str = Field(..., description="Interview question.")
    answer: str = Field(..., description="Interview answer generated based on selected --answer_length.")
    focus_area: str = Field(..., description="Skill/area assessed.")
    difficulty: str = Field(..., description="easy | medium | hard")


class Agent3QAOutput(BaseModel):
    input: Dict[str, Any] = Field(..., description="Inputs summary.")
    top_30: List[QAItem] = Field(..., description="Top 30 interview questions and answers.")
    top_20_questions: List[str] = Field(..., description="Top 20 questions only.")
    notes: List[str] = Field(default_factory=list, description="Any assumptions/notes.")


# ----------------------------
# Helpers
# ----------------------------

def normalize_model_content(content: Any) -> str:
    """Convert LangChain/Gemini/Claude response content into plain text."""
    if content is None:
        return ""

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        chunks: List[str] = []
        for part in content:
            if isinstance(part, dict):
                if isinstance(part.get("text"), str):
                    chunks.append(part["text"])
                elif isinstance(part.get("content"), str):
                    chunks.append(part["content"])
                else:
                    chunks.append(str(part))
            else:
                chunks.append(str(part))
        return "\n".join(chunks)

    return str(content)


def _get_last_ai_content(agent_result: Any) -> str:
    """Safely read the last AI message from a LangChain agent result."""
    if not agent_result:
        return ""

    if isinstance(agent_result, dict):
        messages = agent_result.get("messages", [])
    else:
        messages = getattr(agent_result, "messages", [])

    if not messages:
        return ""

    last = messages[-1]
    if isinstance(last, dict):
        return normalize_model_content(last.get("content"))

    return normalize_model_content(getattr(last, "content", ""))


def extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    """
    Extract the first valid JSON object from model output.
    Handles raw JSON, fenced JSON, and JSON mixed with extra text.
    """
    if not text:
        return None

    text = text.strip()

    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL | re.IGNORECASE)
    if fenced:
        text = fenced.group(1).strip()

    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            parsed, _ = decoder.raw_decode(text[index:])
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            continue

    return None


def _split_sentences(text: str) -> List[str]:
    text = re.sub(r"\s+", " ", (text or "").strip())
    if not text:
        return []

    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip(" -•\t\r\n") for p in parts if p.strip(" -•\t\r\n")]


def _to_bullets(text: str, max_items: Optional[int] = None) -> str:
    text = (text or "").strip()
    if not text:
        return ""

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    bullet_like: List[str] = []

    for line in lines:
        if re.match(r"^[-•*]\s+", line) or re.match(r"^\d+[\).\s]", line):
            bullet_like.append(line)

    if bullet_like:
        cleaned: List[str] = []
        for line in bullet_like:
            line = re.sub(r"^\d+[\).\s]+", "", line).strip()
            line = re.sub(r"^[-•*]\s+", "", line).strip()
            if line:
                cleaned.append(f"- {line}")

        if max_items is not None:
            cleaned = cleaned[:max_items]
        return "\n".join(cleaned)

    parts = _split_sentences(text)
    if max_items is not None:
        parts = parts[:max_items]

    return "\n".join(f"- {part}" for part in parts if part)


def _ensure_parent_dir(file_path: str) -> None:
    """Create the parent directory only when a parent directory exists."""
    parent_dir = os.path.dirname(file_path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)


def _normalize_difficulty(value: Any) -> str:
    difficulty = str(value or "medium").strip().lower()
    return difficulty if difficulty in {"easy", "medium", "hard"} else "medium"

# ----------------------------
# LLM fallback helpers
# ----------------------------

LLM_FALLBACK_STATUS_CODES = {400, 429, 500, 503, 504}

LLM_FALLBACK_KEYWORDS = (
    "400",
    "429",
    "500",
    "503",
    "504",
    "rate limit",
    "quota",
    "resource exhausted",
    "service unavailable",
    "timeout",
    "timed out",
    "server error",
    "internal error",
    "bad request",
)


def _extract_http_status_code(exc: Exception) -> Optional[int]:
    """
    Try to extract HTTP status code from different exception formats.
    Works with many provider / SDK exception styles.
    """
    for attr in ("status_code", "status", "code"):
        value = getattr(exc, attr, None)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)

    response = getattr(exc, "response", None)
    if response is not None:
        value = getattr(response, "status_code", None)
        if isinstance(value, int):
            return value

    text = str(exc)
    match = re.search(r"\b(400|429|500|503|504)\b", text)
    if match:
        return int(match.group(1))

    return None


def _is_llm_fallback_error(exc: Exception) -> bool:
    """
    Decide whether this error should trigger fallback to another LLM provider.
    """
    status_code = _extract_http_status_code(exc)
    if status_code in LLM_FALLBACK_STATUS_CODES:
        return True

    error_text = str(exc).lower()
    return any(keyword in error_text for keyword in LLM_FALLBACK_KEYWORDS)


def _provider_fallback_chain(primary_provider: str) -> List[str]:
    """
    Build provider order.
    If primary is google, fallback is anthropic.
    If primary is anthropic, fallback is google.
    """
    primary_provider = (primary_provider or "google").strip().lower()

    supported = ["google", "anthropic"]

    if primary_provider not in supported:
        primary_provider = "google"

    return [primary_provider] + [p for p in supported if p != primary_provider]

# ----------------------------
# Agent 3 Builder
# ----------------------------

def build_agent3(
    model_name: str = "gemini-2.5-flash",
    temperature: float = 0.25,
    provider: str = "google",
):
    """
    Build Agent 3.

    Important fix:
    LangChain create_agent expects ONE model object or model string.
    Passing [llm, llm_anthropic] causes runtime errors, so this function selects one model.
    """
    provider = (provider or "google").strip().lower()

    if provider == "anthropic":
        anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        if ChatAnthropic is None:
            raise ImportError("langchain_anthropic is not installed. Install it or use provider='google'.")
        if not anthropic_api_key:
            raise EnvironmentError("Missing ANTHROPIC_API_KEY in environment variables.")

        llm = ChatAnthropic(
            model="claude-sonnet-4-5",
            temperature=temperature,
            api_key=anthropic_api_key,
            timeout=180,
            max_retries=0,
        )
    else:
        google_api_key = os.getenv("GOOGLE_API_KEY")
        if not google_api_key:
            raise EnvironmentError("Missing GOOGLE_API_KEY in environment variables.")

        llm = ChatGoogleGenerativeAI(
            model=model_name,
            temperature=temperature,
            google_api_key=google_api_key,
            timeout=180,
            max_retries=0,
        )

    system_prompt = """
You are Agent 3: Interview Q&A Generator.

You will receive:
1) Agent 1 JSON: parsed document fields.
2) Agent 2 JSON: research/context enrichment.
3) Interview rounds string provided by the user.
4) answer_length selected by the user.

Your job:
- Generate interview questions and answers strictly aligned to the provided interview rounds.
- Output ONLY valid JSON. No markdown. No backticks. No extra text.

Output requirements:
A) "top_30": exactly 30 items. Each item must include:
- round
- question
- answer
- focus_area
- difficulty

Answer style rules based on answer_length:
- If answer_length = "answer_small":
  - Give a crisp screening-style answer.
  - Usually 3 to 4 short bullet points.

- If answer_length = "answer_medium":
  - Give a balanced interview answer.
  - Usually 4 to 7 short bullet points.

- If answer_length = "answer_large":
  - Give a deeper answer with more technical depth or story detail.
  - Usually 6 to 10 short bullet points.

Every answer must be written as short bullet lines inside the JSON string.

Question type rules:
- If the question is experience-based, answer using problem, action, technical depth, and impact.
- If the question is scenario-based, answer step by step with decision reasoning.
- If the question is directly technical, answer in a structured, confident, technical way.
- Add measurable impact only where grounded in Agent 1 or Agent 2.
- Align every answer tightly to the resume, JD, and company context available.
- Do not invent experience not present in Agent 1.

B) "top_20_questions": exactly 20 strings.
- Generate 20 candidate practice questions that are not similar to the top_30 questions.
- Each question must have distinct wording, scenario, and problem-solving path.
- They should still be relevant to the same role, resume, JD, and interview rounds.

C) All Q/A must be based on:
- Candidate/resume content from Agent 1.
- Research/context from Agent 2.
- Interview rounds specified by user.
- Questions should be different from previously provided if previous questions are present in the input.

Constraints:
- If Agent 2 lacks company specifics, keep questions role-based and skill-based.
- Ensure realistic distribution across rounds.
- Keep focus_area short and specific.
- Return JSON with double quotes only.

JSON schema:
{
  "input": {
    "agent1_file": "string",
    "agent2_file": "string",
    "doc_type": "string",
    "rounds": ["string", "..."],
    "answer_length": "answer_small|answer_medium|answer_large"
  },
  "top_30": [
    {
      "round": "string",
      "question": "string",
      "answer": "string",
      "focus_area": "string",
      "difficulty": "easy|medium|hard"
    }
  ],
  "top_20_questions": ["string", "..."],
  "notes": ["string", "..."]
}
"""

    return create_agent(
        model=llm,
        tools=[],
        system_prompt=system_prompt,
    )


# ----------------------------
# Core runner
# ----------------------------

def run_agent3(
    agent1_data: Dict[str, Any],
    agent2_data: Dict[str, Any],
    agent1_path: str,
    agent2_path: str,
    interview_rounds: str,
    answer_length: str = "answer_medium",
    provider: str = "google",
) -> Dict[str, Any]:
    rounds = [r.strip() for r in re.split(r"[;\n|,]+", interview_rounds or "") if r.strip()]
    if not rounds:
        rounds = ["Recruiter Screen", "Technical Round", "Hiring Manager", "Behavioral"]

    if answer_length not in {"answer_small", "answer_medium", "answer_large"}:
        answer_length = "answer_medium"


########################################################################################################
    # try:
    #     agent = build_agent3(provider=provider)
    # except Exception as exc:
    #     return {"error": f"Agent build failed: {exc}"}

########################################################################################################
    user_payload = {
        "agent1_json": agent1_data,
        "agent2_json": agent2_data,
        "interview_rounds": rounds,
        "agent1_file": agent1_path,
        "agent2_file": agent2_path,
        "answer_length": answer_length,
    }

########################################################################################################
    # max_attempts = 3
    # initial_delay = 1
    # exp_base = 2
    # last_error = ""
    # result: Any = None

    # for attempt in range(max_attempts):
    #     try:
    #         result = agent.invoke(
    #             {
    #                 "messages": [
    #                     {
    #                         "role": "user",
    #                         "content": (
    #                             "Generate Q&A now using the following JSON inputs.\n"
    #                             "Return ONLY valid JSON.\n\n"
    #                             + json.dumps(user_payload, ensure_ascii=False)
    #                         ),
    #                     }
    #                 ]
    #             }
    #         )
    #         break
    #     except Exception as exc:
    #         last_error = str(exc)
    #         if attempt == max_attempts - 1:
    #             return {"error": f"Agent invocation failed after retries: {last_error}"}

    #         delay = initial_delay * (exp_base ** attempt)
    #         time.sleep(delay)

    # if result is None:
    #     return {"error": f"Agent invocation failed: {last_error or 'No result returned.'}"}
    
########################################################################################################

    max_attempts_per_provider = 2
    initial_delay = 1
    exp_base = 2

    # result: Any = None
    selected_provider = ""
    fallback_errors: List[str] = []
    data: Optional[Dict[str, Any]] = None
    last_raw_output = ""

    provider_chain = _provider_fallback_chain(provider)

    for current_provider in provider_chain:
        try:
            agent = build_agent3(provider=current_provider)
        except Exception as exc:
            fallback_errors.append(
                f"{current_provider} build failed: {exc}"
            )
            continue

        for attempt in range(max_attempts_per_provider):
            try:
                result = agent.invoke(
                    {
                        "messages": [
                            {
                                "role": "user",
                                "content": (
                                    "Generate Q&A now using the following JSON inputs.\n"
                                    "Return ONLY valid JSON.\n\n"
                                    + json.dumps(user_payload, ensure_ascii=False)
                                ),
                            }
                        ]
                    }
                )
                # selected_provider = current_provider
                # break
                text = _get_last_ai_content(result).strip()
                last_raw_output = text

                if not text:
                    fallback_errors.append(
                        f"{current_provider} attempt {attempt + 1} returned empty output."
                    )
                    break

                parsed_data = extract_json_object(text)

                if not parsed_data:
                    fallback_errors.append(
                        f"{current_provider} attempt {attempt + 1} returned invalid JSON."
                    )
                    break

                data = parsed_data
                selected_provider = current_provider
                break

            except Exception as exc:
                status_code = _extract_http_status_code(exc)
                error_message = str(exc)

                fallback_errors.append(
                    f"{current_provider} attempt {attempt + 1} failed"
                    + (f" with HTTP {status_code}" if status_code else "")
                    + f": {error_message}"
                )

                should_switch = _is_llm_fallback_error(exc)

                if should_switch:
                    # Do not waste retries on provider-level/API-level failures.
                    # Switch to the next provider immediately.
                    break

                if attempt < max_attempts_per_provider - 1:
                    delay = initial_delay * (exp_base ** attempt)
                    time.sleep(delay)

        if data is not None:
            break
        # if result is not None:
        #     break

    if data is None:
        return {
            "error": "Agent invocation failed for all configured LLM providers.",
            "provider_chain": provider_chain,
            "fallback_errors": fallback_errors,
            "last_raw_output": last_raw_output,
        }
    
    # if result is None:
    #     return {
    #         "error": "Agent invocation failed for all configured LLM providers.",
    #         "provider_chain": provider_chain,
    #         "fallback_errors": fallback_errors,
    #     }

    # text = _get_last_ai_content(result).strip()
    # data = extract_json_object(text)

    # if not data:
    #     return {"error": "Failed to parse JSON from agent output.", "raw_output": text}

    try:
        # data.setdefault("input", {})
        if not isinstance(data.get("input"), dict):
            data["input"] = {}

        data["input"].setdefault("agent1_file", agent1_path)
        data["input"].setdefault("agent2_file", agent2_path)
        data["input"].setdefault("doc_type", str(agent1_data.get("doc_type", "unknown")))
        data["input"].setdefault("rounds", rounds)
        data["input"].setdefault("answer_length", answer_length)

        # notes = data.setdefault("notes", [])
        # if not isinstance(notes, list):
        #     data["notes"] = [str(notes)]

        notes = data.get("notes", [])
        if not isinstance(notes, list):
            notes = [str(notes)]
        data["notes"] = notes


        top_30 = data.get("top_30", [])
        if not isinstance(top_30, list):
            return {
                "error": "Model returned invalid top_30 format. Expected a list.",
                "raw_output": data,
            }
           
            # top_30 = []
            # data["notes"].append("Model returned invalid top_30 format. Expected a list.")

        if len(top_30) > 30:
            data["notes"].append(f"Model returned {len(top_30)} items in top_30. Trimmed to 30.")
            top_30 = top_30[:30]
            
        # elif len(top_30) < 30:
        #     data["notes"].append(f"Model returned {len(top_30)} items in top_30. Expected 30.")
        
        elif len(top_30) < 30:
            return {
                "error": f"Agent 3 returned only {len(top_30)} items in top_30. Expected 30.",
                "raw_output": data,
            }


        cleaned_items: List[Dict[str, str]] = []

        for item in top_30:
            if not isinstance(item, dict):
                item = {}

            # answer = str(item.get("answer", "")).strip()
            # if not answer:
            #     answer = "- I would answer this based on my resume-aligned experience and practical approach."
            item_number = len(cleaned_items) + 1
            question = str(item.get("question", "")).strip()
            answer = str(item.get("answer", "")).strip()
            round_name = str(item.get("round", "")).strip()
            focus_area = str(item.get("focus_area", "")).strip()

            if not round_name:
                return {
                    "error": f"Agent 3 returned an empty round at top_30 item {item_number}.",
                    "raw_output": data,
                }


            if not question:
                return {
                    "error": f"Agent 3 returned an empty question at top_30 item {item_number}.",
                    "raw_output": data,
                }

            if not answer:
                return {
                    "error": f"Agent 3 returned an empty answer at top_30 item {item_number}.",
                    "raw_output": data,
                }
            
            if not focus_area:
                return {
                    "error": f"Agent 3 returned an empty focus_area at top_30 item {item_number}.",
                    "raw_output": data,
                }

            cleaned_items.append(
                {
                    "round": str(item.get("round", "")).strip(),
                    "question": str(item.get("question", "")).strip(),
                    "answer": _to_bullets(answer),
                    "focus_area": str(item.get("focus_area", "")).strip(),
                    "difficulty": _normalize_difficulty(item.get("difficulty")),
                }
            )

        data["top_30"] = cleaned_items

        top_20 = data.get("top_20_questions", [])
        if not isinstance(top_20, list):
            # top_20 = []
            return {
                "error": "Model returned invalid top_20_questions format. Expected a list.",
                "raw_output": data,
            }


        top_20 = [str(q).strip() for q in top_20 if str(q).strip()]

        if len(top_20) > 20:
            data["notes"].append(
                f"Model returned {len(top_20)} items in top_20_questions. Trimmed to 20."
            )
            top_20 = top_20[:20]
    
        elif len(top_20) < 20:
            return {
                "error": f"Agent 3 returned only {len(top_20)} items in top_20_questions. Expected 20.",
                "raw_output": data,
            }
        
        # elif len(top_20) < 20:
        #     derived: List[str] = []
        #     for item in cleaned_items:
        #         question = item.get("question", "").strip()
        #         if question and question not in top_20 and question not in derived:
        #             derived.append(question)
        #         if len(top_20) + len(derived) == 20:
        #             break
        #     top_20.extend(derived)
        #     data["notes"].append("top_20_questions was auto-derived from top_30 where needed.")

        data["top_20_questions"] = top_20

        data["notes"].append(f"The main answer field was generated for {answer_length}.")

        if selected_provider:
            data["notes"].append(f"LLM provider used: {selected_provider}.")
        
        if fallback_errors:
            data["notes"].append("Fallback errors were captured during provider selection.")

    except Exception as exc:
        return {"error": f"Post-processing failed: {exc}", "raw_output": data}

    return data


# ----------------------------
# CLI
# ----------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Agent 3 - Interview Q&A Generator")
    parser.add_argument("--agent1_json", required=True, help="Path to Agent 1 output JSON file")
    parser.add_argument("--agent2_json", required=True, help="Path to Agent 2 output JSON file")
    parser.add_argument("--interview_rounds", required=True, help="Interview rounds separated by ; or , or newline")
    parser.add_argument(
        "--answer_length",
        default="answer_medium",
        choices=["answer_small", "answer_medium", "answer_large"],
        help="Choose which answer version should be copied into the main answer field.",
    )
    parser.add_argument(
        "--provider",
        default="google",
        choices=["google", "anthropic"],
        help="LLM provider to use. Default is google.",
    )
    parser.add_argument(
        "--out_json",
        default="app/output/03_Test_Case_agent3_qa_02.json",
        help="Output path for Agent 3 JSON",
    )
    parser.add_argument(
        "--write_legacy_output",
        action="store_true",
        help="Also write app/output/03_Test_case_agent_3_QA.json for backward compatibility.",
    )

    args = parser.parse_args()

    if not os.path.exists(args.agent1_json):
        raise FileNotFoundError(f"Agent 1 JSON not found: {args.agent1_json}")
    if not os.path.exists(args.agent2_json):
        raise FileNotFoundError(f"Agent 2 JSON not found: {args.agent2_json}")

    with open(args.agent1_json, "r", encoding="utf-8") as file:
        agent1_data = json.load(file)

    with open(args.agent2_json, "r", encoding="utf-8") as file:
        agent2_data = json.load(file)

    output = run_agent3(
        agent1_data=agent1_data,
        agent2_data=agent2_data,
        agent1_path=args.agent1_json,
        agent2_path=args.agent2_json,
        interview_rounds=args.interview_rounds,
        answer_length=args.answer_length,
        provider=args.provider,
    )

    _ensure_parent_dir(args.out_json)
    with open(args.out_json, "w", encoding="utf-8") as file:
        json.dump(output, file, indent=2, ensure_ascii=False)

    print(f"[Agent3] Output written to: {args.out_json}")
    print(json.dumps(output if "error" in output else {"status": "ok"}, indent=2, ensure_ascii=False))

    if "error" in output:
        raise SystemExit(1)

    if args.write_legacy_output:
        legacy_out_path = "app/output/03_Test_case_agent_3_QA.json"
        _ensure_parent_dir(legacy_out_path)
        with open(legacy_out_path, "w", encoding="utf-8") as file:
            json.dump(output, file, indent=2, ensure_ascii=False)
        print(f"[Agent3] Legacy output written to: {legacy_out_path}")


if __name__ == "__main__":
    main()


# Example Windows command:
# python -m app.agents.agent_3_qa_gen ^
#   --agent1_json app/output/01_agent1.json ^
#   --agent2_json app/output/02_agent2.json ^
#   --interview_rounds "Recruiter Screen; Technical Round; Hiring Manager; Behavioral" ^
#   --answer_length answer_medium ^
#   --out_json app/output/03_agent3_qa.json
