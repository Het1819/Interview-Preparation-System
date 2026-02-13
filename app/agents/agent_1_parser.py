from __future__ import annotations

import re
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

# ✅ Gemini official SDK (needed for SmartLoader Part -> multimodal extraction)
from google import genai
from google.genai import types as genai_types

# ✅ Import SmartLoader
from app.shared.utils import SmartLoader


# ----------------------------
# Output schema
# ----------------------------
# ✅ Import Schema Agent1ParsedDoc
from app.shared.schemas import Agent1ParsedDoc


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
# Helpers: normalize Gemini content + parse JSON safely
# ----------------------------
def normalize_model_content(content: Any) -> str:
    """
    Gemini via LangChain often returns content as:
      - string
      - list[{"type": "text", "text": "..."}]
    Convert it into a single plain string.
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
    """
    create_agent returns a state dict with 'messages'.
    We'll grab the last assistant content and normalize it to string.
    """
    msgs = agent_result.get("messages", [])
    if not msgs:
        return ""

    last = msgs[-1]

    if isinstance(last, dict):
        return normalize_model_content(last.get("content"))

    return normalize_model_content(getattr(last, "content", ""))


def strip_code_fences(text: str) -> str:
    """
    Removes ```json ... ``` or ``` ... ``` fences if present.
    """
    if not text:
        return ""
    text = text.strip()

    # Remove opening fence
    text = re.sub(r"^\s*```(?:json)?\s*", "", text, flags=re.IGNORECASE)

    # Remove closing fence
    text = re.sub(r"\s*```\s*$", "", text)

    return text.strip()


def extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    """
    Robust JSON extractor for:
    - plain JSON
    - JSON wrapped in ```json fences
    - extra text around a JSON block
    """
    if not text:
        return None

    cleaned = strip_code_fences(text)

    # 1) direct parse
    try:
        return json.loads(cleaned)
    except Exception:
        pass

    # 2) extract first {...} block
    m = re.search(r"(\{.*\})", cleaned, re.DOTALL)
    if m:
        candidate = m.group(1).strip()
        try:
            return json.loads(candidate)
        except Exception:
            return None

    return None


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

    system_prompt = """
    You are Agent 1: a document ingestion + parsing agent.

    CRITICAL OUTPUT RULE:
    - Return ONLY valid JSON.
    - Use double quotes for ALL keys and string values.
    - Do NOT return python-style output like: key='value'
    - Do NOT wrap the JSON in markdown code fences.
    - No extra text before or after the JSON.

    JSON schema (must match exactly):
    {
    "file_path": "string",
    "doc_type": "resume | job_description | interview_notes | policy | unknown",
    "summary": "string",
    "key_points": ["string", "..."],
    "entities": {"group": ["item", "..."]},
    "raw_text_preview": "string"
    }

    Process:
    1) Call load_file_with_smartloader(file_path).
    2) If the tool returns "__MULTIMODAL_PART__", set doc_type="unknown" and summary stating multimodal extraction is needed.
    3) If the tool returns text, extract the fields and fill the JSON.

    Keep raw_text_preview to first ~1200 characters of the text.
    """

    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=system_prompt,
    )

    return agent


# ----------------------------
# Run Agent 1 end-to-end
# ----------------------------
def run_agent1(file_path: str) -> Dict[str, Any]:
    """
    - If file is text-extractable: agent calls SmartLoader tool and returns JSON.
    - If file is scanned/image-heavy: do Gemini multimodal OCR -> then agent converts extracted text to JSON.
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

        text = _get_last_ai_content(result).strip()
        data = extract_json_object(text)
        if data:
            return data

        return {"error": "Failed to parse JSON from agent output.", "raw_output": text}

    # ----------------
    # Case B: scanned/image-heavy -> multimodal extraction
    # ----------------
    if isinstance(loaded, genai_types.Part):
        extracted_text = gemini_multimodal_extract_text(loaded)

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
        data = extract_json_object(text)
        if data:
            return data

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
    test_path_01 = r"D:\End to end Job Description and Resume Analyser\interview-prep-system\documents\Naval_Dhandha_DA (1).pdf"
    test_path_02 = r"D:\End to end Job Description and Resume Analyser\interview-prep-system\documents\JD FOR KNOWN.docx"
    out1 = run_agent1(test_path_01)
    out2 = run_agent1(test_path_02)
    print(json.dumps(out1, indent=2, ensure_ascii=False))
    print(json.dumps(out2, indent=2, ensure_ascii=False))






