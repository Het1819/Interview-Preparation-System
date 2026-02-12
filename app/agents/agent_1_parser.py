from __future__ import annotations

import os
import json
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

# ✅ LangChain v1 agent
from langchain.agents import create_agent

# ✅ Tools decorator (LangChain v1)
from langchain.tools import tool

# ✅ Gemini chat model (LangChain integration)
from langchain_google_genai import ChatGoogleGenerativeAI

# ✅ Structured output strategies (recommended when model-native JSON is not guaranteed)
from langchain.agents.structured_output import ToolStrategy

# ✅ Gemini official SDK (needed for SmartLoader Part -> multimodal extraction)
from google import genai
from google.genai import types as genai_types

# ✅ Import SmartLoader exactly as you asked
from app.shared.utils import SmartLoader


# ----------------------------
# Output schema
# ----------------------------
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


# ----------------------------
# Tool: load file via SmartLoader
# ----------------------------
@tool
def load_file_with_smartloader(file_path: str) -> str:
    """
    Load a file via SmartLoader.
    Returns extracted text if available.
    If scanned/image-heavy, returns a marker "__MULTIMODAL_PART__".
    """
    loader = SmartLoader()
    result = loader.process_file(file_path)

    if isinstance(result, str):
        return result

    if isinstance(result, genai_types.Part):
        return "__MULTIMODAL_PART__"

    return "__UNSUPPORTED_OR_EMPTY__"


# ----------------------------
# Multimodal extractor for scanned PDFs/images
# ----------------------------
def gemini_multimodal_extract_text(part: genai_types.Part, model: str = "gemini-2.5-flash") -> str:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise EnvironmentError("Missing GOOGLE_API_KEY in environment variables.")

    client = genai.Client(api_key=api_key)

    prompt = (
        "Extract all readable text from this document. "
        "Preserve headings, bullet points, and table structure where possible. "
        "Do not add extra commentary."
    )

    resp = client.models.generate_content(
        model=model,
        contents=[prompt, part],
    )

    return (resp.text or "").strip()


# ----------------------------
# Helper: get last assistant message content
# ----------------------------
def _get_last_ai_content(agent_result: Dict[str, Any]) -> str:
    """
    create_agent returns a state dict with 'messages'.
    We'll grab the last AI message content.
    """
    msgs = agent_result.get("messages", [])
    if not msgs:
        return ""

    last = msgs[-1]

    # Messages might be dicts: {"role":"assistant","content":...}
    if isinstance(last, dict):
        content = last.get("content", "")
        return content if isinstance(content, str) else json.dumps(content)

    # Or LangChain message objects
    content = getattr(last, "content", "")
    return content if isinstance(content, str) else json.dumps(content)


# ----------------------------
# Build Agent 1 using create_agent
# ----------------------------
def build_agent1(
    model_name: str = "gemini-2.5-flash",
    temperature: float = 0.2,
):
    llm = ChatGoogleGenerativeAI(
        model=model_name,
        temperature=temperature,
        google_api_key=os.getenv("GOOGLE_API_KEY"),
    )

    tools = [load_file_with_smartloader]

    system_prompt = f"""
You are Agent 1: a document ingestion + parsing agent.

CRITICAL OUTPUT RULE:
- Return ONLY valid JSON.
- Use double quotes for ALL keys and string values.
- Do NOT return python-style output like: key='value'
- Do NOT wrap the JSON in markdown code fences.
- No extra text before or after the JSON.

JSON schema (must match exactly):
{{
  "file_path": "string",
  "doc_type": "resume | job_description | interview_notes | policy | unknown",
  "summary": "string",
  "key_points": ["string", "..."],
  "entities": {{"group": ["item", "..."]}},
  "raw_text_preview": "string"
}}

Process:
1) Call load_file_with_smartloader(file_path).
2) If the tool returns "__MULTIMODAL_PART__", set doc_type="unknown" and summary stating multimodal extraction is needed.
3) If the tool returns text, extract the fields and fill the JSON.

Keep raw_text_preview to first ~1200 characters of the text.
"""

    # You can keep ToolStrategy OR remove it.
    # Keeping it is fine, but it doesn't guarantee JSON. The prompt does.
    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=system_prompt,
        # response_format can be omitted to avoid Pydantic-like output formatting
        # response_format=ToolStrategy(Agent1ParsedDoc),
    )

    return agent



# ----------------------------
# Run Agent 1 end-to-end
# ----------------------------
def run_agent1(file_path: str) -> Dict[str, Any]:
    """
    - If file is text-extractable: agent calls SmartLoader tool and returns structured object.
    - If file is scanned/image-heavy: we do Gemini multimodal OCR -> then call agent WITHOUT tool loop
      (we pass the extracted text directly in the message).
    """
    loader = SmartLoader()
    loaded = loader.process_file(file_path)

    agent = build_agent1()

    # ----------------
    # Case A: text content
    # ----------------
    if isinstance(loaded, str):
        result = agent.invoke(
            {"messages": [{"role": "user", "content": f"Parse this file path: {file_path}"}]}
        )

        # Depending on strategy, final assistant content may already be JSON.
        text = _get_last_ai_content(result).strip()

        # If it's JSON, parse and return
        try:
            return json.loads(text)
        except Exception:
            # As a fallback, return raw
            return {"error": "Failed to parse JSON from agent output.", "raw_output": text}

    # ----------------
    # Case B: scanned/image-heavy -> multimodal extraction
    # ----------------
    if isinstance(loaded, genai_types.Part):
        extracted_text = gemini_multimodal_extract_text(loaded)

        # Now ask agent to convert extracted text into schema.
        # (We don't need the file-loading tool here.)
        result = agent.invoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            f"File path: {file_path}\n\n"
                            "The file was scanned/image-heavy. Here is the extracted text:\n\n"
                            f"{extracted_text[:25000]}"
                        ),
                    }
                ]
            }
        )

        text = _get_last_ai_content(result).strip()
        try:
            return json.loads(text)
        except Exception:
            return {"error": "Failed to parse JSON from agent output.", "raw_output": text}

    # ----------------
    # Fallback
    # ----------------
    empty = Agent1ParsedDoc(
        file_path=file_path,
        doc_type="unknown",
        summary="Unsupported or empty content.",
        key_points=[],
        entities={},
        raw_text_preview="",
    )
    return empty.model_dump()


# ----------------------------
# CLI test
# ----------------------------
if __name__ == "__main__":
    # Put any local path here
    test_path = r"D:\End to end Job Description and Resume Analyser\interview-prep-system\Naval_Dhandha_DA (1).pdf"
    # example_pdf = "INTERVIEW-PREP-SYSTEM/Naval_Dhandha_DA (1).pdf"
    out = run_agent1(test_path)
    print(json.dumps(out, indent=2, ensure_ascii=False))















