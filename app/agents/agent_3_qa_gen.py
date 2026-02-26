# app/agents/agent_3_qa_gen.py
# ------------------------------------------------------------
# Agent 3: Q&A Generator
# - Takes Agent1 parsed JSON + Agent2 research JSON
# - Uses user-provided interview rounds
# - Produces:
#   1) Top 30 detailed questions + detailed answers
#   2) Top 20 questions (shortlist)
#   3) All questions aligned to interview rounds provided by user
#
# Usage:
#   python -m app.agents.agent_3_qa_gen \
#       --agent1_json "app/output/agent1.json" \
#       --agent2_json "app/output/agent2.json" \
#       --interview_rounds "Recruiter Screen; Technical Round 1 (SQL/Python); Technical Round 2 (BI/ETL); Hiring Manager; Behavioral" \
#       --out_json "app/output/agent3_qa.json"
#
# Env:
#   set GOOGLE_API_KEY=xxxx
# ------------------------------------------------------------

from __future__ import annotations

import os
import re
import json
import argparse
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
load_dotenv()

from pydantic import BaseModel, Field

# ✅ LangChain v1 agent
from langchain.agents import create_agent

# ✅ Gemini chat model (LangChain integration)
from langchain_google_genai import ChatGoogleGenerativeAI


# ----------------------------
# Output schema
# ----------------------------

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


# ----------------------------
# Helpers: robust content + JSON extraction
# ----------------------------
def normalize_model_content(content: Any) -> str:
    """
    Gemini via LangChain often returns content as:
      - string
      - list[{"type": "text", "text": "..."}]
    Convert to one plain string.
    """
    if content is None:
        return ""
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        chunks = []
        for part in content:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                chunks.append(part["text"])
            else:
                chunks.append(str(part))
        return "\n".join(chunks)

    return str(content)


def _get_last_ai_content(agent_result: Dict[str, Any]) -> str:
    msgs = agent_result.get("messages", [])
    if not msgs:
        return ""
    last = msgs[-1]
    if isinstance(last, dict):
        return normalize_model_content(last.get("content"))
    return normalize_model_content(getattr(last, "content", ""))


def extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    """
    Extract JSON even if it's wrapped in ```json ... ``` or extra text exists.
    """
    if not text:
        return None

    text = text.strip()

    # Remove markdown fenced JSON if present
    fenced = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL | re.IGNORECASE)
    if fenced:
        candidate = fenced.group(1).strip()
        try:
            return json.loads(candidate)
        except Exception:
            pass

    # Direct parse
    try:
        return json.loads(text)
    except Exception:
        pass

    # Grab first JSON object block
    block = re.search(r"(\{.*\})", text, re.DOTALL)
    if block:
        candidate = block.group(1).strip()
        try:
            return json.loads(candidate)
        except Exception:
            return None

    return None


# ----------------------------
# Agent 3 Builder
# ----------------------------
def build_agent3(
    model_name: str = "gemini-2.5-flash",
    temperature: float = 0.25,
):
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise EnvironmentError("Missing GOOGLE_API_KEY in environment variables.")

    llm = ChatGoogleGenerativeAI(
        model=model_name,
        temperature=temperature,
        google_api_key=api_key,
    )

    system_prompt = """
You are Agent 3: Interview Q&A Generator.

You will receive:
1) Agent 1 JSON: parsed document fields (doc_type, summary, entities, key_points, raw_text_preview).
2) Agent 2 JSON: research/context enrichment about role/company/tech stack/interview style (may contain links/snippets/notes).
3) Interview rounds string provided by the user.

Your job:
- Generate interview questions and answers strictly aligned to the PROVIDED interview rounds.
- Output ONLY valid JSON. No markdown. No backticks. No extra text.

Output requirements:
A) "top_30": exactly 30 items. Each item must include:
   - round (must match one of the provided rounds exactly or be a clean, obvious subset of that round name)
   - question
   - answer (detailed, practical, step-by-step, include examples; avoid fluff)
   - focus_area (one short label)
   - difficulty (easy|medium|hard)
B) "top_20_questions": exactly 20 strings (questions only), selected as the highest-signal subset from top_30.
C) All Q/A must be based on:
   - Candidate/resume content from Agent 1 (skills, projects, experience, tools)
   - Research/context from Agent 2 (role/company/interview expectations if present)
   - Interview rounds specified by user (VERY IMPORTANT)

Constraints:
- Do not invent experience that is not present in Agent 1.
- If Agent 2 lacks company specifics, keep questions role-based and skill-based.
- Ensure coverage across rounds. Distribute questions across rounds in a realistic way.
- Keep answers structured: (Context -> Approach -> Example -> Pitfalls -> How you validate).
- Return JSON with double quotes only.

JSON schema:
{
  "input": {
    "agent1_file": "string",
    "agent2_file": "string",
    "doc_type": "string",
    "rounds": ["string", "..."]
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

    agent = create_agent(
        model=llm,
        tools=[],
        system_prompt=system_prompt,
    )
    return agent


# ----------------------------
# Core runner
# ----------------------------
def run_agent3(
    agent1_data: Dict[str, Any],
    agent2_data: Dict[str, Any],
    agent1_path: str,
    agent2_path: str,
    interview_rounds: str,
) -> Dict[str, Any]:
    # Normalize rounds into a list
    # Accept separators: ; | , \n
    rounds = [r.strip() for r in re.split(r"[;\n|,]+", interview_rounds) if r.strip()]
    if not rounds:
        rounds = ["Recruiter Screen", "Technical Round", "Hiring Manager", "Behavioral"]

    agent = build_agent3()

    user_payload = {
        "agent1_json": agent1_data,
        "agent2_json": agent2_data,
        "interview_rounds": rounds,
        "agent1_file": agent1_path,
        "agent2_file": agent2_path,
    }

    result = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "Generate Q&A now using the following JSON inputs.\n"
                        "Remember: Output ONLY valid JSON.\n\n"
                        + json.dumps(user_payload, ensure_ascii=False)
                    ),
                }
            ]
        }
    )

    text = _get_last_ai_content(result).strip()
    data = extract_json_object(text)

    if not data:
        return {"error": "Failed to parse JSON from agent output.", "raw_output": text}

    # Light validation / guardrails (don’t crash, just patch)
    try:
        # Ensure required keys exist
        data.setdefault("input", {})
        data["input"].setdefault("agent1_file", agent1_path)
        data["input"].setdefault("agent2_file", agent2_path)
        data["input"].setdefault("doc_type", str(agent1_data.get("doc_type", "unknown")))
        data["input"].setdefault("rounds", rounds)

        # Fix counts if model returned wrong sizes (best-effort)
        top_30 = data.get("top_30", [])
        if isinstance(top_30, list) and len(top_30) > 30:
            data["top_30"] = top_30[:30]
        elif isinstance(top_30, list) and len(top_30) < 30:
            data.setdefault("notes", [])
            data["notes"].append(
                f"Model returned {len(top_30)} items in top_30 (expected 30). Consider re-running with lower temperature."
            )

        top_20 = data.get("top_20_questions", [])
        if isinstance(top_20, list) and len(top_20) > 20:
            data["top_20_questions"] = top_20[:20]
        elif isinstance(top_20, list) and len(top_20) < 20:
            # If missing, derive from top_30
            if isinstance(data.get("top_30"), list):
                derived = []
                for item in data["top_30"]:
                    q = item.get("question") if isinstance(item, dict) else None
                    if q and q not in derived:
                        derived.append(q)
                    if len(derived) == 20:
                        break
                data["top_20_questions"] = derived
                data.setdefault("notes", [])
                data["notes"].append("top_20_questions was auto-derived from top_30 due to missing/short output.")

    except Exception as e:
        return {"error": f"Post-processing failed: {e}", "raw_output": data}

    return data


# ----------------------------
# CLI
# ----------------------------
def main():
    parser = argparse.ArgumentParser(description="Agent 3 - Interview Q&A Generator")
    parser.add_argument("--agent1_json", required=True, help="Path to Agent 1 output JSON file")
    parser.add_argument("--agent2_json", required=True, help="Path to Agent 2 output JSON file")
    parser.add_argument("--interview_rounds", required=True, help="Interview rounds (separate by ; or , or newline)")
    parser.add_argument("--out_json", default="app/output/03_Test_Case_agent3_qa_02.json", help="Output path for Agent 3 JSON")

    args = parser.parse_args()

    if not os.path.exists(args.agent1_json):
        raise FileNotFoundError(f"Agent1 JSON not found: {args.agent1_json}")
    if not os.path.exists(args.agent2_json):
        raise FileNotFoundError(f"Agent2 JSON not found: {args.agent2_json}")

    with open(args.agent1_json, "r", encoding="utf-8") as f:
        agent1_data = json.load(f)

    with open(args.agent2_json, "r", encoding="utf-8") as f:
        agent2_data = json.load(f)

    out = run_agent3(
        agent1_data=agent1_data,
        agent2_data=agent2_data,
        agent1_path=args.agent1_json,
        agent2_path=args.agent2_json,
        interview_rounds=args.interview_rounds,
    )

    os.makedirs(os.path.dirname(args.out_json), exist_ok=True)
    with open(args.out_json, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    print(f"[Agent3] Output written to: {args.out_json}")
    print(json.dumps(out if "error" in out else {"status": "ok"}, indent=2, ensure_ascii=False))
    with open("app/output/03_Test_case_agent_3_QA.json", "w",encoding="utf-8") as f:
        json.dump(out,f,indent=2,ensure_ascii=False)

if __name__ == "__main__":
    main()

# Provide the interview rounds by  
# Round 1 - Recruiter Screen
# Round 2 - Technical (Core Skills)
# Round 3 - Technical (Project + Design)
# Round 4 - Hiring Manager
# Round 5 - Behavioral

# Run the 3rd Agent
# python -m app.agents.agent_3_qa_gen --agent1_json "app/output/agent1.json" --agent2_json "app/output/agent2.json" --interview_rounds "Recruiter Screen; Technical Round 1 (SQL/Python); Technical Round 2 (BI/ETL); Hiring Manager; Behavioral" --out_json "app/output/agent3_qa.json"