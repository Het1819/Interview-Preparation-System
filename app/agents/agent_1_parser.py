from __future__ import annotations

import re
import os
import json
import base64
import mimetypes
from typing import Any, Dict, Optional

import anthropic
from pydantic import ValidationError
from dotenv import load_dotenv

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_anthropic import ChatAnthropic

from google import genai
from google.genai import types as genai_types

from app.shared.utils import SmartLoader
from app.shared.schemas import Agent1ParsedDoc


# ----------------------------
# Load environment variables
# ----------------------------
load_dotenv()


# ----------------------------
# Hardcoded model configuration
# ----------------------------
GEMINI_MODEL = "gemini-2.5-flash-lite"

ANTHROPIC_MODEL = "claude-3-5-haiku-latest"
ANTHROPIC_MULTIMODAL_MODEL = "claude-3-5-haiku-latest"
ANTHROPIC_MAX_FILE_BYTES = 23068672  # 22 MB


# ----------------------------
# Fallback configuration
# ----------------------------
FALLBACK_STATUS_CODES = {400, 401, 403, 408, 429, 500, 502, 503, 504}


# ----------------------------
# Multimodal extractor: Gemini
# ----------------------------
def gemini_multimodal_extract_text(
    part: genai_types.Part,
    model: str = GEMINI_MODEL,
) -> str:
    """
    Extract readable text from scanned PDFs/images using Gemini multimodal.
    """

    api_key = os.getenv("GOOGLE_API_KEY")

    if not api_key:
        raise EnvironmentError("Missing GOOGLE_API_KEY in environment variables.")

    retry_config = genai_types.HttpRetryOptions(
        attempts=5,
        exp_base=7,
        initial_delay=1,
        http_status_codes=[429, 500, 503, 504],
    )

    client = genai.Client(
        api_key=api_key,
        http_options=genai_types.HttpOptions(
            retry_options=retry_config,
        ),
    )

    prompt = (
        "Extract all readable text from this document. "
        "Preserve headings, bullet points, dates, names, tables, and section structure where possible. "
        "Do not add commentary. Return only the extracted text."
    )

    response = client.models.generate_content(
        model=model,
        contents=[prompt, part],
    )

    return (response.text or "").strip()


# ----------------------------
# Multimodal extractor: Anthropic fallback
# ----------------------------
def get_file_media_type(file_path: str) -> str:
    """
    Detect media type for Anthropic multimodal input.
    Supports PDFs and common image formats.
    """

    ext = os.path.splitext(file_path.lower())[1]

    explicit_types = {
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }

    if ext in explicit_types:
        return explicit_types[ext]

    guessed_type, _ = mimetypes.guess_type(file_path)

    if guessed_type:
        return guessed_type

    return "application/octet-stream"


def normalize_anthropic_message_text(message: Any) -> str:
    """
    Extract text from Anthropic SDK message response.
    """

    chunks = []

    for block in getattr(message, "content", []):
        text = getattr(block, "text", None)

        if isinstance(text, str):
            chunks.append(text)
            continue

        if isinstance(block, dict) and isinstance(block.get("text"), str):
            chunks.append(block["text"])

    return "\n".join(chunks).strip()


def anthropic_multimodal_extract_text(
    file_path: str,
    model: str = ANTHROPIC_MULTIMODAL_MODEL,
    max_tokens: int = 4000,
) -> str:
    """
    Fallback OCR/document extraction using Anthropic.
    Uses the original file path instead of Google's genai_types.Part.

    Supports:
    - PDF files
    - PNG/JPEG/WEBP/GIF images
    """

    api_key = os.getenv("ANTHROPIC_API_KEY")

    if not api_key:
        raise EnvironmentError("Missing ANTHROPIC_API_KEY in environment variables.")

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found for Anthropic extraction: {file_path}")

    media_type = get_file_media_type(file_path)

    supported_media_types = {
        "application/pdf",
        "image/png",
        "image/jpeg",
        "image/webp",
        "image/gif",
    }

    if media_type not in supported_media_types:
        raise ValueError(
            f"Unsupported file type for Anthropic multimodal extraction: {media_type}"
        )

    file_size = os.path.getsize(file_path)

    if file_size > ANTHROPIC_MAX_FILE_BYTES:
        raise ValueError(
            f"File too large for Anthropic base64 fallback. "
            f"Size={file_size} bytes, limit={ANTHROPIC_MAX_FILE_BYTES} bytes."
        )

    with open(file_path, "rb") as file:
        file_data = base64.standard_b64encode(file.read()).decode("utf-8")

    if media_type == "application/pdf":
        file_block = {
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": file_data,
            },
        }
    else:
        file_block = {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": file_data,
            },
        }

    extraction_prompt = (
        "Extract all readable text from this document or image. "
        "Preserve headings, bullet points, dates, names, tables, and section structure where possible. "
        "Do not add commentary. Return only the extracted text."
    )

    client = anthropic.Anthropic(api_key=api_key)

    message = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[
            {
                "role": "user",
                "content": [
                    file_block,
                    {
                        "type": "text",
                        "text": extraction_prompt,
                    },
                ],
            }
        ],
    )

    return normalize_anthropic_message_text(message)


# ----------------------------
# Helpers: normalize model content
# ----------------------------
def normalize_model_content(content: Any) -> str:
    """
    Normalize model response content into plain text.

    Handles:
    - string
    - list of text blocks
    - dict-like content blocks
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


def strip_code_fences(text: str) -> str:
    """
    Remove ```json ... ``` or ``` ... ``` fences if present.
    """

    if not text:
        return ""

    text = text.strip()

    text = re.sub(
        r"^\s*```(?:json)?\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"\s*```\s*$",
        "",
        text,
    )

    return text.strip()


def extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    """
    Safely extract a JSON object from model output.

    Handles:
    - plain JSON
    - JSON inside code fences
    - extra text before/after JSON
    """

    if not text:
        return None

    cleaned = strip_code_fences(text)

    try:
        parsed = json.loads(cleaned)

        if isinstance(parsed, dict):
            return parsed

    except Exception:
        pass

    decoder = json.JSONDecoder()

    for index, char in enumerate(cleaned):
        if char == "{":
            try:
                parsed, _ = decoder.raw_decode(cleaned[index:])

                if isinstance(parsed, dict):
                    return parsed

            except Exception:
                continue

    return None


# ----------------------------
# Error helpers
# ----------------------------
def extract_status_code_from_error(error: Exception) -> Optional[int]:
    """
    Try to extract HTTP status code from different exception formats.
    Works for Google, Anthropic, requests/httpx-style errors, and plain text errors.
    """

    status_code = getattr(error, "status_code", None)

    if isinstance(status_code, int):
        return status_code

    code = getattr(error, "code", None)

    if isinstance(code, int):
        return code

    response = getattr(error, "response", None)

    if response is not None:
        response_status = getattr(response, "status_code", None)

        if isinstance(response_status, int):
            return response_status

    error_text = str(error)

    match = re.search(
        r"\b(400|401|403|404|408|409|429|500|502|503|504)\b",
        error_text,
    )

    if match:
        return int(match.group(1))

    return None


def should_switch_provider(error: Exception) -> bool:
    """
    Decide whether to switch from Gemini to Anthropic.
    """

    status_code = extract_status_code_from_error(error)

    if status_code in FALLBACK_STATUS_CODES:
        return True

    if status_code is None:
        return True

    return False


# ----------------------------
# LLM builders
# ----------------------------
def build_gemini_llm(
    model_name: str = GEMINI_MODEL,
    temperature: float = 0.2,
) -> ChatGoogleGenerativeAI:
    """
    Build Gemini chat model.
    """

    api_key = os.getenv("GOOGLE_API_KEY")

    if not api_key:
        raise EnvironmentError("Missing GOOGLE_API_KEY in environment variables.")

    return ChatGoogleGenerativeAI(
        model=model_name,
        temperature=temperature,
        google_api_key=api_key,
        timeout=120,
        max_retries=2,
    )


def build_anthropic_llm(
    model_name: str = ANTHROPIC_MODEL,
    temperature: float = 0.2,
) -> ChatAnthropic:
    """
    Build Anthropic chat model.
    """

    api_key = os.getenv("ANTHROPIC_API_KEY")

    if not api_key:
        raise EnvironmentError("Missing ANTHROPIC_API_KEY in environment variables.")

    return ChatAnthropic(
        model=model_name,
        temperature=temperature,
        anthropic_api_key=api_key,
        timeout=120,
        max_retries=2,
    )


# ----------------------------
# Parser system prompt
# ----------------------------
PARSER_SYSTEM_PROMPT = """
You are Agent 1: a document ingestion and parsing agent.

CRITICAL OUTPUT RULE:
- Return ONLY valid JSON.
- Use double quotes for all keys and string values.
- Do NOT return python-style output like: key='value'
- Do NOT wrap the JSON in markdown code fences.
- No extra text before or after the JSON.

JSON schema must match exactly:
{
  "file_path": "string",
  "doc_type": "resume | job_description | interview_notes | policy | unknown",
  "summary": "string",
  "key_points": ["string", "..."],
  "entities": {"group": ["item", "..."]},
  "raw_text_preview": "string"
}

Rules:
- Identify doc_type based on the document content.
- Keep summary concise but useful.
- Extract key points from the actual document.
- Extract important entities such as names, skills, tools, companies, roles, locations, education, certifications, dates, and technologies where available.
- Set raw_text_preview as an empty string. The system will fill it later.
"""


# ----------------------------
# Output validation
# ----------------------------
def validate_agent1_output(
    data: Dict[str, Any],
    raw_output: str = "",
) -> Dict[str, Any]:
    """
    Validate parsed JSON against Agent1ParsedDoc schema.
    This prevents downstream blank PDFs or broken workflow outputs.
    """

    try:
        parsed = Agent1ParsedDoc.model_validate(data)
        return parsed.model_dump()

    except ValidationError as error:
        return {
            "error": "JSON parsed but schema validation failed.",
            "details": error.errors(),
            "raw_output": raw_output,
        }


def parse_llm_response_to_agent1_json(
    response: Any,
    raw_text_preview: str,
) -> tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Convert LLM response into validated Agent1ParsedDoc JSON.

    Returns:
    - parsed output if successful
    - error object if failed
    """

    raw_output = normalize_model_content(
        getattr(response, "content", "")
    ).strip()

    data = extract_json_object(raw_output)

    if not data:
        return None, {
            "error": "Failed to parse JSON from model output.",
            "raw_output": raw_output,
        }

    data["raw_text_preview"] = raw_text_preview[:1200]

    validated = validate_agent1_output(data, raw_output)

    if isinstance(validated, dict) and validated.get("error"):
        return None, validated

    return validated, None


# ----------------------------
# Text to structured JSON parser
# ----------------------------
def parse_text_to_agent1_json(
    file_path: str,
    text: str,
    model_name: str = GEMINI_MODEL,
    temperature: float = 0.2,
) -> Dict[str, Any]:
    """
    Parse extracted document text into Agent1ParsedDoc JSON.

    Flow:
    1. Try Gemini first.
    2. If Gemini fails or returns invalid JSON, switch to Anthropic.
    3. Return safe error objects instead of crashing.
    """

    if not text or not text.strip():
        empty = Agent1ParsedDoc(
            file_path=file_path,
            doc_type="unknown",
            summary="The file was loaded but no readable text was extracted.",
            key_points=[],
            entities={},
            raw_text_preview="",
        )
        return empty.model_dump()

    trimmed_text = text[:15000]
    raw_text_preview = text[:1200]

    user_prompt = f"""
File path:
{file_path}

Document text:
{trimmed_text}
"""

    messages = [
        SystemMessage(content=PARSER_SYSTEM_PROMPT),
        HumanMessage(content=user_prompt),
    ]

    provider_errors = []

    # ----------------------------
    # Provider 1: Gemini
    # ----------------------------
    try:
        gemini_llm = build_gemini_llm(
            model_name=model_name,
            temperature=temperature,
        )

        response = gemini_llm.invoke(messages)

        parsed_output, parse_error = parse_llm_response_to_agent1_json(
            response=response,
            raw_text_preview=raw_text_preview,
        )

        if parsed_output:
            return parsed_output

        provider_errors.append(
            {
                "provider": "gemini",
                "error": "Gemini returned invalid or schema-incompatible JSON.",
                "details": parse_error,
            }
        )

    except Exception as error:
        provider_errors.append(
            {
                "provider": "gemini",
                "error": "Gemini LLM parsing failed.",
                "status_code": extract_status_code_from_error(error),
                "details": str(error),
            }
        )

        if not should_switch_provider(error):
            return {
                "error": "Gemini failed with a non-fallback error.",
                "provider_errors": provider_errors,
            }

    # ----------------------------
    # Provider 2: Anthropic fallback
    # ----------------------------
    try:
        anthropic_llm = build_anthropic_llm(
            model_name=ANTHROPIC_MODEL,
            temperature=temperature,
        )

        response = anthropic_llm.invoke(messages)

        parsed_output, parse_error = parse_llm_response_to_agent1_json(
            response=response,
            raw_text_preview=raw_text_preview,
        )

        if parsed_output:
            return parsed_output

        provider_errors.append(
            {
                "provider": "anthropic",
                "error": "Anthropic returned invalid or schema-incompatible JSON.",
                "details": parse_error,
            }
        )

    except Exception as error:
        provider_errors.append(
            {
                "provider": "anthropic",
                "error": "Anthropic fallback failed.",
                "status_code": extract_status_code_from_error(error),
                "details": str(error),
            }
        )

    return {
        "error": "All LLM providers failed.",
        "provider_errors": provider_errors,
    }


# ----------------------------
# Run Agent 1 end-to-end
# ----------------------------
def run_agent1(file_path: str) -> Dict[str, Any]:
    """
    Agent 1 end-to-end flow:

    1. Load file once using SmartLoader.
    2. If text is available, parse directly into validated JSON.
    3. If scanned/image-heavy, try Gemini multimodal extraction.
    4. If Gemini multimodal fails, try Anthropic multimodal extraction.
    5. Parse extracted text into validated JSON using Gemini with Anthropic fallback.
    6. Return safe error objects instead of crashing.
    """

    if not file_path or not str(file_path).strip():
        return {
            "error": "Missing file_path.",
            "details": "run_agent1() received an empty file path.",
        }

    if not os.path.exists(file_path):
        return {
            "error": "File not found.",
            "file_path": file_path,
        }

    loader = SmartLoader()

    try:
        loaded = loader.process_file(file_path)

    except Exception as error:
        return {
            "error": "SmartLoader failed to process the file.",
            "file_path": file_path,
            "details": str(error),
        }

    # ----------------------------
    # Case A: normal text content
    # ----------------------------
    if isinstance(loaded, str):
        return parse_text_to_agent1_json(
            file_path=file_path,
            text=loaded,
        )

    # ----------------------------
    # Case B: scanned/image-heavy content
    # ----------------------------
    if isinstance(loaded, genai_types.Part):
        extraction_errors = []
        extracted_text = ""
        extraction_provider = ""

        # Try Gemini multimodal first
        try:
            extracted_text = gemini_multimodal_extract_text(loaded)
            extraction_provider = "gemini_multimodal"

        except Exception as error:
            extraction_errors.append(
                {
                    "provider": "gemini_multimodal",
                    "error": "Gemini multimodal extraction failed.",
                    "status_code": extract_status_code_from_error(error),
                    "details": str(error),
                }
            )

        # Fallback to Anthropic multimodal
        if not extracted_text.strip():
            try:
                extracted_text = anthropic_multimodal_extract_text(
                    file_path=file_path,
                    model=ANTHROPIC_MULTIMODAL_MODEL,
                )
                extraction_provider = "anthropic_multimodal"

            except Exception as error:
                extraction_errors.append(
                    {
                        "provider": "anthropic_multimodal",
                        "error": "Anthropic multimodal extraction failed.",
                        "status_code": extract_status_code_from_error(error),
                        "details": str(error),
                    }
                )

                return {
                    "error": "All multimodal text extraction providers failed.",
                    "file_path": file_path,
                    "extraction_errors": extraction_errors,
                }

        if not extracted_text.strip():
            empty = Agent1ParsedDoc(
                file_path=file_path,
                doc_type="unknown",
                summary="The file appears to be scanned/image-heavy, but no readable text was extracted by any provider.",
                key_points=[],
                entities={},
                raw_text_preview="",
            )
            return empty.model_dump()

        parsed_output = parse_text_to_agent1_json(
            file_path=file_path,
            text=extracted_text,
        )

        if isinstance(parsed_output, dict):
            parsed_output["extraction_provider"] = extraction_provider

            if extraction_errors:
                parsed_output["extraction_errors"] = extraction_errors

        return parsed_output

    # ----------------------------
    # Case C: unsupported or empty content
    # ----------------------------
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
    test_path_01 = r"D:\End to end Job Description and Resume Analyser\interview-prep-system\documents\01_Resume.pdf"
    test_path_02 = r"D:\End to end Job Description and Resume Analyser\interview-prep-system\documents\01_JD.pdf"

    out1 = run_agent1(test_path_01)
    out2 = run_agent1(test_path_02)

    print(json.dumps(out1, indent=2, ensure_ascii=False))
    print(json.dumps(out2, indent=2, ensure_ascii=False))

    os.makedirs("app/output", exist_ok=True)

    with open("app/output/01_Agent_1_OP_Resume.json", "w", encoding="utf-8") as file:
        json.dump(out1, file, indent=2, ensure_ascii=False)

    with open("app/output/02_Agent_1_OP_JD.json", "w", encoding="utf-8") as file:
        json.dump(out2, file, indent=2, ensure_ascii=False)
















###### ================================================================================================




# from __future__ import annotations

# import re
# import os
# import json
# import base64
# import mimetypes
# from typing import Any, Dict, Optional
# from pydantic import ValidationError
# import anthropic
# from dotenv import load_dotenv
# load_dotenv()

# # ✅ LangChain v1 agent
# # from langchain.agents import create_agent

# # # ✅ Tools decorator (LangChain v1)
# # from langchain.tools import tool

# # ✅ Gemini chat model (LangChain integration)
# from langchain_google_genai import ChatGoogleGenerativeAI
# from langchain_core.messages import SystemMessage, HumanMessage
# from langchain_anthropic import ChatAnthropic

# # ✅ Gemini official SDK (needed for SmartLoader Part -> multimodal extraction)
# from google import genai
# from google.genai import types as genai_types

# # ✅ Import SmartLoader
# from app.shared.utils import SmartLoader


# # ----------------------------
# # Output schema
# # ----------------------------
# # ✅ Import Schema Agent1ParsedDoc
# from app.shared.schemas import Agent1ParsedDoc


# # ----------------------------
# # Tool: load file via SmartLoader
# # ----------------------------
# # @tool
# # def load_file_with_smartloader(file_path: str) -> str:
# #     """
# #     Load a file via SmartLoader.
# #     Returns extracted text if available.
# #     If scanned/image-heavy, returns a marker "__MULTIMODAL_PART__".
# #     """
# #     loader = SmartLoader()
# #     result = loader.process_file(file_path)

# #     if isinstance(result, str):
# #         return result

# #     if isinstance(result, genai_types.Part):
# #         return "__MULTIMODAL_PART__"

# #     return "__UNSUPPORTED_OR_EMPTY__"


# # ----------------------------
# # Multimodal extractor for scanned PDFs/images
# # ----------------------------
# def gemini_multimodal_extract_text(part: genai_types.Part, model: str = "gemini-2.5-flash-lite") -> str:
#     api_key = os.getenv("GOOGLE_API_KEY")
#     if not api_key:
#         raise EnvironmentError("Missing GOOGLE_API_KEY in environment variables.")

#     retry_config = genai_types.HttpRetryOptions(
#         attempts=5,
#         exp_base=7,
#         initial_delay=1,
#         http_status_codes=[429, 500, 503, 504],
#     )

#     client = genai.Client(
#                 api_key=api_key,
#                 http_options=genai_types.HttpOptions(
#                     retry_options=retry_config
#                 )
#             )

#     prompt = (
#         "Extract all readable text from this document. "
#         "Preserve headings, bullet points, and table structure where possible. "
#         "Do not add extra commentary."
#     )

#     resp = client.models.generate_content(
#         model=model,
#         contents=[prompt, part],
#     )

#     return (resp.text or "").strip()

# def get_file_media_type(file_path: str) -> str:
#     """
#     Detect media type for Anthropic multimodal input.
#     Supports PDFs and common image formats.
#     """

#     ext = os.path.splitext(file_path.lower())[1]

#     explicit_types = {
#         ".pdf": "application/pdf",
#         ".png": "image/png",
#         ".jpg": "image/jpeg",
#         ".jpeg": "image/jpeg",
#         ".webp": "image/webp",
#         ".gif": "image/gif",
#     }

#     if ext in explicit_types:
#         return explicit_types[ext]

#     guessed_type, _ = mimetypes.guess_type(file_path)

#     if guessed_type:
#         return guessed_type

#     return "application/octet-stream"


# def normalize_anthropic_message_text(message: Any) -> str:
#     """
#     Extract text from Anthropic SDK message response.
#     """

#     chunks = []

#     for block in getattr(message, "content", []):
#         text = getattr(block, "text", None)

#         if isinstance(text, str):
#             chunks.append(text)
#             continue

#         if isinstance(block, dict) and isinstance(block.get("text"), str):
#             chunks.append(block["text"])

#     return "\n".join(chunks).strip()


# def anthropic_multimodal_extract_text(
#     file_path: str,
#     model: Optional[str] = None,
#     max_tokens: int = 4000,
# ) -> str:
#     """
#     Fallback OCR/document extraction using Anthropic.
#     Uses the original file path, not Google's genai_types.Part.

#     Supports:
#     - PDF files through Anthropic document blocks
#     - PNG/JPEG/WEBP/GIF files through Anthropic image blocks
#     """

#     api_key = os.getenv("ANTHROPIC_API_KEY")
#     if not api_key:
#         raise EnvironmentError("Missing ANTHROPIC_API_KEY in environment variables.")

#     if not os.path.exists(file_path):
#         raise FileNotFoundError(f"File not found for Anthropic extraction: {file_path}")

#     media_type = get_file_media_type(file_path)

#     supported_media_types = {
#         "application/pdf",
#         "image/png",
#         "image/jpeg",
#         "image/webp",
#         "image/gif",
#     }

#     if media_type not in supported_media_types:
#         raise ValueError(
#             f"Unsupported file type for Anthropic multimodal extraction: {media_type}"
#         )

#     # Keep payload safer. Anthropic standard request size is commonly limited around 32 MB,
#     # and base64 increases payload size, so keep a lower file-size guard.
#     max_file_bytes = int(os.getenv("ANTHROPIC_MAX_FILE_BYTES", str(22 * 1024 * 1024)))
#     file_size = os.path.getsize(file_path)

#     if file_size > max_file_bytes:
#         raise ValueError(
#             f"File too large for base64 Anthropic fallback. "
#             f"Size={file_size} bytes, limit={max_file_bytes} bytes. "
#             f"Use file splitting or Anthropic Files API for larger PDFs."
#         )

#     with open(file_path, "rb") as f:
#         file_data = base64.standard_b64encode(f.read()).decode("utf-8")

#     if media_type == "application/pdf":
#         file_block = {
#             "type": "document",
#             "source": {
#                 "type": "base64",
#                 "media_type": media_type,
#                 "data": file_data,
#             },
#         }
#     else:
#         file_block = {
#             "type": "image",
#             "source": {
#                 "type": "base64",
#                 "media_type": media_type,
#                 "data": file_data,
#             },
#         }

#     extraction_prompt = (
#         "Extract all readable text from this document or image. "
#         "Preserve headings, bullet points, dates, names, tables, and section structure where possible. "
#         "Do not add commentary. Return only the extracted text."
#     )

#     client = anthropic.Anthropic(api_key=api_key)

#     selected_model = (
#         model
#         or os.getenv("ANTHROPIC_MULTIMODAL_MODEL")
#         or os.getenv("ANTHROPIC_MODEL")
#         or "claude-3-5-haiku-latest"
#     )

#     message = client.messages.create(
#         model=selected_model,
#         max_tokens=max_tokens,
#         messages=[
#             {
#                 "role": "user",
#                 "content": [
#                     file_block,
#                     {
#                         "type": "text",
#                         "text": extraction_prompt,
#                     },
#                 ],
#             }
#         ],
#     )

#     return normalize_anthropic_message_text(message)

# # ----------------------------
# # Helpers: normalize Gemini content + parse JSON safely
# # ----------------------------
# def normalize_model_content(content: Any) -> str:
#     """
#     Gemini via LangChain often returns content as:
#       - string
#       - list[{"type": "text", "text": "..."}]
#     Convert it into a single plain string.
#     """
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


# # def _get_last_ai_content(agent_result: Dict[str, Any]) -> str:
# #     """
# #     create_agent returns a state dict with 'messages'.
# #     We'll grab the last assistant content and normalize it to string.
# #     """
# #     msgs = agent_result.get("messages", [])
# #     if not msgs:
# #         return ""

# #     last = msgs[-1]

# #     if isinstance(last, dict):
# #         return normalize_model_content(last.get("content"))

# #     return normalize_model_content(getattr(last, "content", ""))


# def strip_code_fences(text: str) -> str:
#     """
#     Removes ```json ... ``` or ``` ... ``` fences if present.
#     """
#     if not text:
#         return ""
#     text = text.strip()

#     # Remove opening fence
#     text = re.sub(r"^\s*```(?:json)?\s*", "", text, flags=re.IGNORECASE)

#     # Remove closing fence
#     text = re.sub(r"\s*```\s*$", "", text)

#     return text.strip()


# def extract_json_object(text: str) -> Optional[Dict[str, Any]]:
#     """
#     Robust JSON extractor for:
#     - plain JSON
#     - JSON wrapped in ```json fences
#     - extra text around a JSON block
#     """
#     if not text:
#         return None

#     cleaned = strip_code_fences(text)

#     # 1) direct parse
#     try:
#         return json.loads(cleaned)
#     except Exception:
#         pass

#     # 2) extract first {...} block
#     m = re.search(r"(\{.*\})", cleaned, re.DOTALL)
#     if m:
#         candidate = m.group(1).strip()
#         try:
#             return json.loads(candidate)
#         except Exception:
#             return None

#     return None

# # FALLBACK_STATUS_CODES = {400, 429, 500, 503, 504}
# FALLBACK_STATUS_CODES = {400, 401, 403, 408, 429, 500, 502, 503, 504}


# def extract_status_code_from_error(error: Exception) -> Optional[int]:
#     """
#     Try to extract HTTP status code from different exception formats.
#     Works for Google, Anthropic, requests/httpx-style errors, and plain text errors.
#     """

#     # Direct status_code attribute
#     status_code = getattr(error, "status_code", None)
#     if isinstance(status_code, int):
#         return status_code

#     # Some SDKs use code instead of status_code
#     code = getattr(error, "code", None)
#     if isinstance(code, int):
#         return code

#     # Response object pattern
#     response = getattr(error, "response", None)
#     if response is not None:
#         response_status = getattr(response, "status_code", None)
#         if isinstance(response_status, int):
#             return response_status

#     # Fallback: search inside error message
#     error_text = str(error)
#     match = re.search(r"\b(400|401|403|404|408|409|429|500|502|503|504)\b", error_text)
#     if match:
#         return int(match.group(1))

#     return None


# def should_switch_provider(error: Exception) -> bool:
#     """
#     Decide whether to switch from Gemini to Anthropic.
#     Switch on known API/search/fetch/rate-limit/server errors.
#     Also switch if status code cannot be detected, because production should try fallback.
#     """

#     status_code = extract_status_code_from_error(error)

#     if status_code in FALLBACK_STATUS_CODES:
#         return True

#     # If SDK throws a generic error without a status code, still try fallback
#     if status_code is None:
#         return True

#     return False


# def build_gemini_llm(
#     model_name: str,
#     temperature: float,
# ) -> ChatGoogleGenerativeAI:
#     api_key = os.getenv("GOOGLE_API_KEY")
#     if not api_key:
#         raise EnvironmentError("Missing GOOGLE_API_KEY in environment variables.")

#     return ChatGoogleGenerativeAI(
#         model=model_name,
#         temperature=temperature,
#         google_api_key=api_key,
#         timeout=120,
#         max_retries=2,
#     )


# def build_anthropic_llm(
#     model_name: str = "claude-3-5-haiku-latest",
#     temperature: float = 0.2,
# ) -> ChatAnthropic:
#     api_key = os.getenv("ANTHROPIC_API_KEY")
#     if not api_key:
#         raise EnvironmentError("Missing ANTHROPIC_API_KEY in environment variables.")

#     return ChatAnthropic(
#         model=model_name,
#         temperature=temperature,
#         anthropic_api_key=api_key,
#         timeout=120,
#         max_retries=2,
#     )


# def parse_llm_response_to_agent1_json(
#     response: Any,
#     raw_text_preview: str,
# ) -> tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
#     """
#     Convert LLM response into validated Agent1ParsedDoc JSON.
#     Returns:
#       - parsed output if successful
#       - error object if failed
#     """

#     raw_output = normalize_model_content(getattr(response, "content", "")).strip()
#     data = extract_json_object(raw_output)

#     if not data:
#         return None, {
#             "error": "Failed to parse JSON from model output.",
#             "raw_output": raw_output,
#         }

#     # Force raw_text_preview from Python instead of trusting the LLM
#     data["raw_text_preview"] = raw_text_preview[:1200]

#     validated = validate_agent1_output(data, raw_output)

#     if isinstance(validated, dict) and validated.get("error"):
#         return None, validated

#     return validated, None



# PARSER_SYSTEM_PROMPT = """
# You are Agent 1: a document ingestion and parsing agent.

# CRITICAL OUTPUT RULE:
# - Return ONLY valid JSON.
# - Use double quotes for all keys and string values.
# - Do NOT return python-style output like: key='value'
# - Do NOT wrap the JSON in markdown code fences.
# - No extra text before or after the JSON.

# JSON schema must match exactly:
# {
#   "file_path": "string",
#   "doc_type": "resume | job_description | interview_notes | policy | unknown",
#   "summary": "string",
#   "key_points": ["string", "..."],
#   "entities": {"group": ["item", "..."]},
#   "raw_text_preview": "string"
# }

# Rules:
# - Identify doc_type based on the document content.
# - Keep summary concise but useful.
# - Extract key points from the actual document.
# - Extract important entities such as names, skills, tools, companies, roles, locations, education, certifications, dates, and technologies where available.
# - Keep raw_text_preview to the first 1200 characters of the provided text.
# """

# def validate_agent1_output(data: Dict[str, Any], raw_output: str = "") -> Dict[str, Any]:
#     """
#     Validate parsed JSON against Agent1ParsedDoc schema.
#     This prevents downstream blank PDFs or broken workflow outputs.
#     """
#     try:
#         parsed = Agent1ParsedDoc.model_validate(data)
#         return parsed.model_dump()
#     except ValidationError as e:
#         return {
#             "error": "JSON parsed but schema validation failed.",
#             "details": e.errors(),
#             "raw_output": raw_output,
#         }

# # def parse_text_to_agent1_json(
# #     file_path: str,
# #     text: str,
# #     model_name: str = "gemini-2.5-flash-lite",
# #     temperature: float = 0.2,
# # ) -> Dict[str, Any]:
# #     """
# #     Directly parse extracted document text into Agent1ParsedDoc JSON.
# #     Avoids LangChain agent/tool overhead and prevents duplicate SmartLoader calls.
# #     """
# #     if not text or not text.strip():
# #         empty = Agent1ParsedDoc(
# #             file_path=file_path,
# #             doc_type="unknown",
# #             summary="The file was loaded but no readable text was extracted.",
# #             key_points=[],
# #             entities={},
# #             raw_text_preview="",
# #         )
# #         return empty.model_dump()

# #     llm = ChatGoogleGenerativeAI(
# #         model=model_name,
# #         temperature=temperature,
# #         google_api_key=os.getenv("GOOGLE_API_KEY"),
# #         timeout=120,
# #         max_retries=2,
# #     )

# #     trimmed_text = text[:25000]

# #     user_prompt = f"""
# # File path:
# # {file_path}

# # Document text:
# # {trimmed_text}
# # """

# #     try:
# #         response = llm.invoke(
# #             [
# #                 {"role": "system", "content": PARSER_SYSTEM_PROMPT},
# #                 {"role": "user", "content": user_prompt},
# #             ]
# #         )

# #         raw_output = normalize_model_content(getattr(response, "content", "")).strip()
# #         data = extract_json_object(raw_output)

# #         if not data:
# #             return {
# #                 "error": "Failed to parse JSON from model output.",
# #                 "raw_output": raw_output,
# #             }

# #         return validate_agent1_output(data, raw_output)

# #     except Exception as e:
# #         return {
# #             "error": "LLM parsing failed.",
# #             "details": str(e),
# #         }
# def parse_text_to_agent1_json(
#     file_path: str,
#     text: str,
#     model_name: str = "gemini-2.5-flash-lite",
#     temperature: float = 0.2,
# ) -> Dict[str, Any]:
#     """
#     Parse extracted document text into Agent1ParsedDoc JSON.

#     Improved production behavior:
#     1. Try Gemini first.
#     2. If Gemini fails due to 400, 429, 500, 503, 504, or generic SDK/API error,
#        automatically switch to Anthropic.
#     3. If Gemini returns invalid JSON, try Anthropic before failing.
#     4. Return safe error objects instead of crashing.
#     """

#     if not text or not text.strip():
#         empty = Agent1ParsedDoc(
#             file_path=file_path,
#             doc_type="unknown",
#             summary="The file was loaded but no readable text was extracted.",
#             key_points=[],
#             entities={},
#             raw_text_preview="",
#         )
#         return empty.model_dump()

#     # Reduce token usage from 25000 to 15000 characters
#     trimmed_text = text[:15000]
#     raw_text_preview = text[:1200]

#     user_prompt = f"""
# File path:
# {file_path}

# Document text:
# {trimmed_text}
# """

#     messages = [
#         SystemMessage(content=PARSER_SYSTEM_PROMPT),
#         HumanMessage(content=user_prompt),
#     ]

#     provider_errors = []

#     # ----------------------------
#     # Provider 1: Gemini
#     # ----------------------------
#     try:
#         gemini_llm = build_gemini_llm(
#             model_name=model_name,
#             temperature=temperature,
#         )

#         response = gemini_llm.invoke(messages)

#         parsed_output, parse_error = parse_llm_response_to_agent1_json(
#             response=response,
#             raw_text_preview=raw_text_preview,
#         )

#         if parsed_output:
#             return parsed_output

#         provider_errors.append({
#             "provider": "gemini",
#             "error": "Gemini returned invalid or schema-incompatible JSON.",
#             "details": parse_error,
#         })

#     except Exception as e:
#         provider_errors.append({
#             "provider": "gemini",
#             "error": "Gemini LLM parsing failed.",
#             "status_code": extract_status_code_from_error(e),
#             "details": str(e),
#         })

#         if not should_switch_provider(e):
#             return {
#                 "error": "Gemini failed with a non-fallback error.",
#                 "provider_errors": provider_errors,
#             }

#     # ----------------------------
#     # Provider 2: Anthropic fallback
#     # ----------------------------
#     try:
#         anthropic_llm = build_anthropic_llm(
#             model_name="claude-3-5-haiku-latest",
#             temperature=temperature,
#         )

#         response = anthropic_llm.invoke(messages)

#         parsed_output, parse_error = parse_llm_response_to_agent1_json(
#             response=response,
#             raw_text_preview=raw_text_preview,
#         )

#         if parsed_output:
#             return parsed_output

#         provider_errors.append({
#             "provider": "anthropic",
#             "error": "Anthropic returned invalid or schema-incompatible JSON.",
#             "details": parse_error,
#         })

#     except Exception as e:
#         provider_errors.append({
#             "provider": "anthropic",
#             "error": "Anthropic fallback failed.",
#             "status_code": extract_status_code_from_error(e),
#             "details": str(e),
#         })

#     return {
#         "error": "All LLM providers failed.",
#         "provider_errors": provider_errors,
#     }

# # ----------------------------
# # Build Agent 1 using create_agent
# # ----------------------------
# # def build_agent1(
# #     model_name: str = "gemini-2.5-flash-lite",
# #     # model_name: str = "gemini-2.5-flash",
# #     temperature: float = 0.2,
# # ):
# #     llm = ChatGoogleGenerativeAI(
# #         model=model_name,
# #         temperature=temperature,
# #         google_api_key=os.getenv("GOOGLE_API_KEY"),
# #         timeout=120,
# #         max_retries=2
# #     )

# #     tools = [load_file_with_smartloader]

# #     system_prompt = """
# #     You are Agent 1: a document ingestion + parsing agent.

# #     CRITICAL OUTPUT RULE:
# #     - Return ONLY valid JSON.
# #     - Use double quotes for ALL keys and string values.
# #     - Do NOT return python-style output like: key='value'
# #     - Do NOT wrap the JSON in markdown code fences.
# #     - No extra text before or after the JSON.

# #     JSON schema (must match exactly):
# #     {
# #     "file_path": "string",
# #     "doc_type": "resume | job_description | interview_notes | policy | unknown",
# #     "summary": "string",
# #     "key_points": ["string", "..."],
# #     "entities": {"group": ["item", "..."]},
# #     "raw_text_preview": "string"
# #     }

# #     Process:
# #     1) Call load_file_with_smartloader(file_path).
# #     2) If the tool returns "__MULTIMODAL_PART__", set doc_type="unknown" and summary stating multimodal extraction is needed.
# #     3) If the tool returns text, extract the fields and fill the JSON.

# #     Keep raw_text_preview to first ~1200 characters of the text.
# #     """

# #     agent = create_agent(
# #         model=llm,
# #         tools=tools,
# #         system_prompt=system_prompt,
# #     )

# #     return agent


# # ----------------------------
# # Run Agent 1 end-to-end
# # ----------------------------
# def run_agent1(file_path: str) -> Dict[str, Any]:
#     """
#     Agent 1 end-to-end flow:
#     1. Load file once using SmartLoader.
#     2. If text is available, parse directly into validated JSON.
#     3. If scanned/image-heavy, extract text using Gemini multimodal extraction.
#     4. Validate final output against Agent1ParsedDoc.
#     5. Return safe error objects instead of crashing or generating blank outputs.
#     """

#     if not file_path or not str(file_path).strip():
#         return {
#             "error": "Missing file_path.",
#             "details": "run_agent1() received an empty file path.",
#         }

#     if not os.path.exists(file_path):
#         return {
#             "error": "File not found.",
#             "file_path": file_path,
#         }

#     loader = SmartLoader()

#     try:
#         loaded = loader.process_file(file_path)
#     except Exception as e:
#         return {
#             "error": "SmartLoader failed to process the file.",
#             "file_path": file_path,
#             "details": str(e),
#         }

#     # ----------------
#     # Case A: text content
#     # ----------------
#     # if isinstance(loaded, str):
#     #     return parse_text_to_agent1_json(
#     #         file_path=file_path,
#     #         text=loaded,
#     #     )

#     # # ----------------
#     # # Case B: scanned/image-heavy content
#     # # ----------------
#     # if isinstance(loaded, genai_types.Part):
#     #     try:
#     #         extracted_text = gemini_multimodal_extract_text(loaded)
#     #     except Exception as e:
#     #         return {
#     #             "error": "Multimodal text extraction failed.",
#     #             "file_path": file_path,
#     #             "details": str(e),
#     #         }

#     #     if not extracted_text.strip():
#     #         empty = Agent1ParsedDoc(
#     #             file_path=file_path,
#     #             doc_type="unknown",
#     #             summary="The file appears to be scanned/image-heavy, but no readable text was extracted.",
#     #             key_points=[],
#     #             entities={},
#     #             raw_text_preview="",
#     #         )
#     #         return empty.model_dump()

#     #     return parse_text_to_agent1_json(
#     #         file_path=file_path,
#     #         text=extracted_text,
#     #     )

#     if isinstance(loaded, genai_types.Part):
#         extraction_errors = []
#         extracted_text = ""
#         extraction_provider = ""

#         # ----------------------------
#         # Try Gemini multimodal first
#         # ----------------------------
#         try:
#             extracted_text = gemini_multimodal_extract_text(loaded)
#             extraction_provider = "gemini_multimodal"
#         except Exception as e:
#             extraction_errors.append({
#                 "provider": "gemini_multimodal",
#                 "error": "Gemini multimodal extraction failed.",
#                 "status_code": extract_status_code_from_error(e),
#                 "details": str(e),
#             })

#         # ----------------------------
#         # Fallback: Anthropic multimodal using original file_path
#         # ----------------------------
#         if not extracted_text.strip():
#             try:
#                 extracted_text = anthropic_multimodal_extract_text(file_path)
#                 extraction_provider = "anthropic_multimodal"
#             except Exception as e:
#                 extraction_errors.append({
#                     "provider": "anthropic_multimodal",
#                     "error": "Anthropic multimodal extraction failed.",
#                     "status_code": extract_status_code_from_error(e),
#                     "details": str(e),
#                 })

#                 return {
#                     "error": "All multimodal text extraction providers failed.",
#                     "file_path": file_path,
#                     "extraction_errors": extraction_errors,
#                 }

#         if not extracted_text.strip():
#             empty = Agent1ParsedDoc(
#                 file_path=file_path,
#                 doc_type="unknown",
#                 summary="The file appears to be scanned/image-heavy, but no readable text was extracted by any provider.",
#                 key_points=[],
#                 entities={},
#                 raw_text_preview="",
#             )
#             return empty.model_dump()

#         parsed_output = parse_text_to_agent1_json(
#             file_path=file_path,
#             text=extracted_text,
#         )

#         if isinstance(parsed_output, dict) and parsed_output.get("error"):
#             parsed_output["extraction_provider"] = extraction_provider
#             parsed_output["extraction_errors"] = extraction_errors

#         return parsed_output
    
    


#     # ----------------
#     # Case C: unsupported or empty content
#     # ----------------
#     empty = Agent1ParsedDoc(
#         file_path=file_path,
#         doc_type="unknown",
#         summary="Unsupported or empty content.",
#         key_points=[],
#         entities={},
#         raw_text_preview="",
#     )
#     return empty.model_dump()


# # def run_agent1(file_path: str) -> Dict[str, Any]:
# #     """
# #     - If file is text-extractable: agent calls SmartLoader tool and returns JSON.
# #     - If file is scanned/image-heavy: do Gemini multimodal OCR -> then agent converts extracted text to JSON.
# #     """
# #     loader = SmartLoader()
# #     loaded = loader.process_file(file_path)

# #     agent = build_agent1()

# #     # ----------------
# #     # Case A: text content
# #     # ----------------
# #     if isinstance(loaded, str):
# #         result = agent.invoke(
# #             {"messages": [{"role": "user", "content": f"Parse this file path: {file_path}"}]}
# #         )

# #         text = _get_last_ai_content(result).strip()
# #         data = extract_json_object(text)
# #         if data:
# #             return data

# #         return {"error": "Failed to parse JSON from agent output.", "raw_output": text}

# #     # ----------------
# #     # Case B: scanned/image-heavy -> multimodal extraction
# #     # ----------------
# #     if isinstance(loaded, genai_types.Part):
# #         extracted_text = gemini_multimodal_extract_text(loaded)

# #         result = agent.invoke(
# #             {
# #                 "messages": [
# #                     {
# #                         "role": "user",
# #                         "content": (
# #                             f"File path: {file_path}\n\n"
# #                             "The file was scanned/image-heavy. Here is the extracted text:\n\n"
# #                             f"{extracted_text[:25000]}"
# #                         ),
# #                     }
# #                 ]
# #             }
# #         )

# #         text = _get_last_ai_content(result).strip()
# #         data = extract_json_object(text)
# #         if data:
# #             return data

# #         return {"error": "Failed to parse JSON from agent output.", "raw_output": text}

# #     # ----------------
# #     # Fallback
# #     # ----------------
# #     empty = Agent1ParsedDoc(
# #         file_path=file_path,
# #         doc_type="unknown",
# #         summary="Unsupported or empty content.",
# #         key_points=[],
# #         entities={},
# #         raw_text_preview="",
# #     )
# #     return empty.model_dump()


# # ----------------------------
# # CLI test
# # ----------------------------
# if __name__ == "__main__":
#     test_path_01 = r"D:\End to end Job Description and Resume Analyser\interview-prep-system\documents\01_Resume.pdf"
#     test_path_02 = r"D:\End to end Job Description and Resume Analyser\interview-prep-system\documents\01_JD.pdf"
#     out1 = run_agent1(test_path_01)
#     out2 = run_agent1(test_path_02)
#     print(json.dumps(out1, indent=2, ensure_ascii=False))
#     print(json.dumps(out2, indent=2, ensure_ascii=False))
#     os.makedirs("app/output", exist_ok=True)
#     with open("app/output/01_Agent_1_OP_Resume.json", "w", encoding="utf-8") as f:
#         json.dump(out1, f, indent=2, ensure_ascii=False)
#     with open("app/output/02_Agent_1_OP_JD.json", "w", encoding="utf-8") as f:
#         json.dump(out2, f, indent=2, ensure_ascii=False)






