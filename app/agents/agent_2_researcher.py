# app/agents/agent_2_researcher.py
from __future__ import annotations

import os
import re
import json
import time
import argparse
from typing import Any, Dict, Optional, List
from dotenv import load_dotenv
load_dotenv()

import requests
from pydantic import BaseModel, Field

from langchain.agents import create_agent
from langchain.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI

# Tavily
from tavily import TavilyClient
# Exa
from exa_py import Exa

# =========================================================
# Output Schema: Agent 2
# =========================================================
from app.shared.schemas import CompanyResearchReport
# class NewsItem(BaseModel):
#     title: str = Field(..., description="News headline")
#     source: str = Field(..., description="Publisher/source name")
#     date: Optional[str] = Field(None, description="Publish date if available")
#     url: str = Field(..., description="Source URL")
#     summary: str = Field(..., description="1-2 line summary")


# class CompanyResearchReport(BaseModel):
#     company_name: str = Field(..., description="Company name")
#     role_title: Optional[str] = Field(None, description="Role title if available")

#     overview: str = Field(..., description="What the company does in 2-4 lines")
#     mission_values: List[str] = Field(default_factory=list, description="Mission/values bullets")
#     products_services: List[str] = Field(default_factory=list, description="Key products/services")
#     business_model: List[str] = Field(default_factory=list, description="How they make money (high-level)")

#     interview_focus: List[str] = Field(default_factory=list, description="Likely interview focus areas")
#     interview_process: List[str] = Field(default_factory=list, description="Stages/rounds if found")

#     recent_news: List[NewsItem] = Field(default_factory=list, description="Recent relevant news")
#     sources: List[str] = Field(default_factory=list, description="URLs used")

#     notes: Optional[str] = Field(None, description="Caveats / missing info")


# =========================================================
# Helpers: Gemini content normalization + safe JSON parse
# =========================================================
def normalize_model_content(content: Any) -> str:
    """
    Gemini via LangChain often returns content as:
      - string
      - list[{"type":"text","text":"..."}]
    Convert into a single plain string.
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


def strip_code_fences(text: str) -> str:
    if not text:
        return ""
    text = text.strip()
    text = re.sub(r"^\s*```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```\s*$", "", text)
    return text.strip()


def extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    """
    Extract JSON even if wrapped in ```json ... ``` or extra text exists.
    """
    if not text:
        return None

    cleaned = strip_code_fences(text)

    # direct
    try:
        return json.loads(cleaned)
    except Exception:
        pass

    # first {...} block
    m = re.search(r"(\{.*\})", cleaned, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            return None
    return None

# =========================================================
# Retry + Provider Fallback Helpers
# =========================================================
# FALLBACK_STATUS_CODES = {400, 429, 500, 503, 504}
FALLBACK_STATUS_CODES = {400, 401, 403, 408, 429, 500, 502, 503, 504}
MAX_SEARCH_RESULTS = 5
MAX_SNIPPET_CHARS = 350
MAX_FETCH_CHARS = 5000


def _extract_status_code(error: Exception) -> Optional[int]:
    """
    Extract HTTP status code from SDK/request exceptions.
    Works for requests errors, SDK errors, and plain string errors.
    """
    # requests-style response
    response = getattr(error, "response", None)
    if response is not None:
        status_code = getattr(response, "status_code", None)
        if isinstance(status_code, int):
            return status_code

    # SDK-style status_code
    status_code = getattr(error, "status_code", None)
    if isinstance(status_code, int):
        return status_code

    # Try to parse from error message
    msg = str(error)
    m = re.search(r"\b(400|401|403|404|408|409|429|500|502|503|504)\b", msg)
    if m:
        return int(m.group(1))

    return None


def _should_fallback(error: Exception) -> bool:
    """
    Switch provider if known fallback status appears.
    Also switch for unknown provider/runtime errors.
    """
    status_code = _extract_status_code(error)

    if status_code in FALLBACK_STATUS_CODES:
        return True

    # If status code is unknown, still fallback because user wants fallback on generated errors too.
    if status_code is None:
        return True

    return False


def _clean_html_to_text(html: str) -> str:
    text = re.sub(r"(?is)<script.*?>.*?</script>", " ", html)
    text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
    text = re.sub(r"(?s)<.*?>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# =========================================================
# Tavily Search Tool
# =========================================================
def _tavily_client() -> TavilyClient:
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        raise EnvironmentError("Missing TAVILY_API_KEY in environment variables.")
    return TavilyClient(api_key=api_key)


def _domain_from_url(url: str) -> str:
    try:
        m = re.search(r"https?://([^/]+)/?", url)
        return m.group(1) if m else ""
    except Exception:
        return ""

def _search_tavily_raw(query: str) -> Dict[str, Any]:
    tavily = _tavily_client()

    resp = tavily.search(
        query=query,
        max_results=MAX_SEARCH_RESULTS,
        search_depth="basic",
        topic="general",
        include_answer=False,
        include_raw_content=False,
        include_images=False,
    )

    results: List[Dict[str, str]] = []

    for r in resp.get("results", []) or []:
        url = r.get("url", "") or ""
        title = r.get("title", "") or ""
        snippet = (r.get("content", "") or "")[:MAX_SNIPPET_CHARS]

        results.append(
            {
                "title": title,
                "snippet": snippet,
                "url": url,
                "source": _domain_from_url(url),
            }
        )

    if not results:
        raise RuntimeError("No results from Tavily.")

    return {
        "provider": "tavily",
        "query": query,
        "results": results,
    }


def _search_exa_raw(query: str) -> Dict[str, Any]:
    exa = _exa_client()

    resp = exa.search_and_contents(
        query=query,
        num_results=MAX_SEARCH_RESULTS,
        text=True,
        highlights=True,
    )

    results: List[Dict[str, str]] = []

    for r in getattr(resp, "results", []) or []:
        url = getattr(r, "url", "") or ""
        title = getattr(r, "title", "") or ""

        highlights = getattr(r, "highlights", None)
        if highlights:
            snippet = " ".join(highlights)[:MAX_SNIPPET_CHARS]
        else:
            snippet = (getattr(r, "text", "") or "")[:MAX_SNIPPET_CHARS]

        results.append(
            {
                "title": title,
                "snippet": snippet,
                "url": url,
                "source": _domain_from_url(url),
            }
        )

    if not results:
        raise RuntimeError("No results from Exa.")

    return {
        "provider": "exa",
        "query": query,
        "results": results,
    }



# @tool
# def web_search_tavily(query: str) -> str:
#     """
#     Web search using Tavily.
#     Returns JSON string:
#     {
#       "query": "...",
#       "results": [
#         {"title": "...", "snippet": "...", "url": "...", "source": "..."},
#         ...
#       ]
#     }
#     """
#     query = (query or "").strip()
#     if not query:
#         return json.dumps({"error": "Empty query"}, ensure_ascii=False)

#     max_attempts = 5
#     initial_delay = 1
#     exp_base = 2
#     for attempt in range(max_attempts):
#         try:
#             tavily = _tavily_client()

#             # Tavily returns structured search results with `results[].content`.
#             # `topic="general"` is a safe default for broad web search.
#             resp = tavily.search(
#                 query=query,
#                 max_results=6,
#                 search_depth="advanced",   # or "basic" if you want cheaper/faster
#                 topic="general",
#                 include_answer=False,
#                 include_raw_content=False,
#                 include_images=False,
#             )

#             results: List[Dict[str, str]] = []
#             for r in resp.get("results", []) or []:
#                 url = r.get("url", "") or ""
#                 title = r.get("title", "") or ""
#                 snippet = (r.get("content", "") or "")[:600]

#                 results.append(
#                     {
#                         "title": title,
#                         "snippet": snippet,
#                         "url": url,
#                         "source": _domain_from_url(url),
#                     }
#                 )

#             if not results:
#                 return json.dumps(
#                     {"error": "No results from Tavily.", "query": query},
#                     ensure_ascii=False
#                 )

#             return json.dumps(
#                 {"query": query, "results": results},
#                 ensure_ascii=False
#             )

#         except Exception as e:
#             if attempt == max_attempts - 1:
#                 return json.dumps({"error": str(e), "query": query}, ensure_ascii=False)
            
#             delay = initial_delay * (exp_base ** attempt)
#             time.sleep(delay)

# @tool
# def fetch_url_tavily(url: str) -> str:
#     """
#     Optional: fetch raw page text for grounding.
#     First tries Tavily Extract, then falls back to requests if needed.

#     Returns JSON:
#     {"url":"...", "text":"..."} or {"url":"...", "error":"..."}
#     """
#     url = (url or "").strip()
#     if not url:
#         return json.dumps({"error": "Empty url"}, ensure_ascii=False)

#     # 1) Try Tavily Extract first
#     max_attempts = 5
#     initial_delay = 1
#     exp_base = 2
#     for attempt in range(max_attempts):
#         try:
#             tavily = _tavily_client()
#             resp = tavily.extract(url)

#             # Tavily extract response shape can vary slightly by SDK version/use,
#             # so we handle the common patterns defensively.
#             text = ""

#             if isinstance(resp, dict):
#                 # Common pattern: {"results": [{"url": "...", "raw_content": "..."}]}
#                 results = resp.get("results", [])
#                 if results and isinstance(results, list):
#                     first = results[0] or {}
#                     text = (
#                         first.get("raw_content")
#                         or first.get("content")
#                         or first.get("text")
#                         or ""
#                     )
#                 else:
#                     # Fallback if content is surfaced directly
#                     text = resp.get("raw_content") or resp.get("content") or resp.get("text") or ""

#             if text:
#                 return json.dumps({"url": url, "text": text[:4000]}, ensure_ascii=False)

#         except Exception:
#             pass

#         # 2) Fallback to plain requests
#         try:
#             r = requests.get(
#                 url,
#                 timeout=30,
#                 headers={
#                     "User-Agent": (
#                         "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
#                         "AppleWebKit/537.36 (KHTML, like Gecko) "
#                         "Chrome/120.0 Safari/537.36"
#                     )
#                 },
#             )
#             r.raise_for_status()
#             html = r.text

#             # basic HTML -> text
#             text = re.sub(r"(?is)<script.*?>.*?</script>", " ", html)
#             text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
#             text = re.sub(r"(?s)<.*?>", " ", text)
#             text = re.sub(r"\s+", " ", text).strip()

#             return json.dumps({"url": url, "text": text[:12000]}, ensure_ascii=False)
#         except Exception as e:
#             if attempt == max_attempts - 1:
#                 return json.dumps({"url": url, "error": str(e)}, ensure_ascii=False)

#             delay = initial_delay * (exp_base ** attempt)
#             import time
#             time.sleep(delay)



# =========================================================
# Exa Search Tool
# =========================================================
def _exa_client() -> Exa:
    api_key = os.getenv("EXA_API_KEY")
    if not api_key:
        raise EnvironmentError("Missing EXA_API_KEY in environment variables.")
    return Exa(api_key=api_key)


# def _domain_from_url(url: str) -> str:
#     try:
#         m = re.search(r"https?://([^/]+)/?", url)
#         return m.group(1) if m else ""
#     except Exception:
#         return ""


# @tool
# def web_search_exa(query: str) -> str:
#     """
#     Web search using Exa.
#     Returns JSON string:
#     {
#       "query": "...",
#       "results": [
#         {"title": "...", "snippet": "...", "url": "...", "source": "..."},
#         ...
#       ]
#     }
#     """
#     query = (query or "").strip()
#     if not query:
#         return json.dumps({"error": "Empty query"}, ensure_ascii=False)
#     max_attempts = 5
#     initial_delay = 1
#     exp_base = 2

#     for attempt in range(max_attempts):
#         try:
#             exa = _exa_client()

#             # Exa can return text/highlights. We'll keep it lightweight.
#             resp = exa.search_and_contents(
#                 query=query,
#                 num_results=6,
#                 text=True,
#                 highlights=True,
#                 # You can optionally bias freshness:
#                 # start_published_date="2024-01-01",
#             )

#             results: List[Dict[str, str]] = []
#             for r in getattr(resp, "results", []) or []:
#                 url = getattr(r, "url", "") or ""
#                 title = getattr(r, "title", "") or ""

#                 snippet = ""
#                 highlights = getattr(r, "highlights", None)
#                 if highlights:
#                     snippet = " ".join(highlights)[:600]
#                 else:
#                     txt = getattr(r, "text", "") or ""
#                     snippet = txt[:600]

#                 results.append(
#                     {
#                         "title": title,
#                         "snippet": snippet,
#                         "url": url,
#                         "source": _domain_from_url(url),
#                     }
#                 )

#             if not results:
#                 return json.dumps({"error": "No results from Exa.", "query": query}, ensure_ascii=False)

#             return json.dumps({"query": query, "results": results}, ensure_ascii=False)

#         except Exception as e:
#             # return json.dumps({"error": str(e), "query": query}, ensure_ascii=False)
#             if attempt == max_attempts - 1:
#                 return json.dumps({"error": str(e), "query": query}, ensure_ascii=False)
#             delay = initial_delay * (exp_base ** attempt)
#             time.sleep(delay)

# @tool
# def fetch_url_exa(url: str) -> str:
#     """
#     Optional: fetch raw page text for grounding.
#     Exa already returns text, but this can help for official pages that Exa summaries miss.
#     Returns JSON:
#     {"url":"...", "text":"..."} or {"url":"...", "error":"..."}
#     """
#     url = (url or "").strip()
#     if not url:
#         return json.dumps({"error": "Empty url"}, ensure_ascii=False)

#     try:
#         r = requests.get(
#             url,
#             timeout=30,
#             headers={
#                 "User-Agent": (
#                     "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
#                     "AppleWebKit/537.36 (KHTML, like Gecko) "
#                     "Chrome/120.0 Safari/537.36"
#                 )
#             },
#         )
#         r.raise_for_status()
#         html = r.text

#         # basic HTML -> text
#         text = re.sub(r"(?is)<script.*?>.*?</script>", " ", html)
#         text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
#         text = re.sub(r"(?s)<.*?>", " ", text)
#         text = re.sub(r"\s+", " ", text).strip()

#         return json.dumps({"url": url, "text": text[:12000]}, ensure_ascii=False)
#     except Exception as e:
#         return json.dumps({"url": url, "error": str(e)}, ensure_ascii=False)

@tool
def web_search_auto(query: str) -> str:
    """
    Smart web search with automatic provider fallback.

    Default flow:
    1. Try Tavily first.
    2. If Tavily fails with 400, 429, 500, 503, 504, or any provider/runtime error, try Exa.
    3. If Exa also fails, return a structured error.
    """
    query = (query or "").strip()
    if not query:
        return json.dumps({"error": "Empty query"}, ensure_ascii=False)

    errors = []

    # Provider order: Tavily first, then Exa
    providers = [
        ("tavily", _search_tavily_raw),
        ("exa", _search_exa_raw),
    ]

    for provider_name, provider_func in providers:
        try:
            data = provider_func(query)
            data["fallback_used"] = provider_name != "tavily"
            return json.dumps(data, ensure_ascii=False)

        except Exception as e:
            errors.append(
                {
                    "provider": provider_name,
                    "status_code": _extract_status_code(e),
                    "error": str(e),
                }
            )

            if not _should_fallback(e):
                break

    return json.dumps(
        {
            "error": "All search providers failed.",
            "query": query,
            "providers_tried": [e["provider"] for e in errors],
            "details": errors,
        },
        ensure_ascii=False,
    )

def _fetch_tavily_raw(url: str) -> Dict[str, Any]:
    tavily = _tavily_client()
    resp = tavily.extract(url)

    text = ""

    if isinstance(resp, dict):
        results = resp.get("results", [])

        if results and isinstance(results, list):
            first = results[0] or {}
            text = (
                first.get("raw_content")
                or first.get("content")
                or first.get("text")
                or ""
            )
        else:
            text = (
                resp.get("raw_content")
                or resp.get("content")
                or resp.get("text")
                or ""
            )

    if not text:
        raise RuntimeError("No extractable text from Tavily.")

    return {
        "provider": "tavily",
        "url": url,
        "text": text[:MAX_FETCH_CHARS],
    }


def _fetch_requests_raw(url: str, provider_name: str = "requests") -> Dict[str, Any]:
    r = requests.get(
        url,
        timeout=30,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0 Safari/537.36"
            )
        },
    )
    r.raise_for_status()

    text = _clean_html_to_text(r.text)

    if not text:
        raise RuntimeError("No extractable page text from requests.")

    return {
        "provider": provider_name,
        "url": url,
        "text": text[:MAX_FETCH_CHARS],
    }


def _fetch_exa_raw(url: str) -> Dict[str, Any]:
    # Exa does not always provide a direct extract method in every SDK setup.
    # For your current code, requests is the safest fallback fetch path.
    return _fetch_requests_raw(url, provider_name="exa_requests")


@tool
def fetch_url_auto(url: str) -> str:
    """
    Smart URL fetch with automatic provider fallback.

    Default flow:
    1. Try Tavily Extract.
    2. If Tavily fails with 400, 429, 500, 503, 504, or any provider/runtime error, try requests/Exa-style fetch.
    3. If both fail, return a structured error.
    """
    url = (url or "").strip()
    if not url:
        return json.dumps({"error": "Empty url"}, ensure_ascii=False)

    errors = []

    providers = [
        ("tavily", _fetch_tavily_raw),
        ("exa_requests", _fetch_exa_raw),
    ]

    for provider_name, provider_func in providers:
        try:
            data = provider_func(url)
            data["fallback_used"] = provider_name != "tavily"
            return json.dumps(data, ensure_ascii=False)

        except Exception as e:
            errors.append(
                {
                    "provider": provider_name,
                    "status_code": _extract_status_code(e),
                    "error": str(e),
                }
            )

            if not _should_fallback(e):
                break

    return json.dumps(
        {
            "error": "All fetch providers failed.",
            "url": url,
            "providers_tried": [e["provider"] for e in errors],
            "details": errors,
        },
        ensure_ascii=False,
    )

# =========================================================
# Company + Role extraction (best effort)
# =========================================================
def guess_company_and_role(agent1: Dict[str, Any]) -> Dict[str, Optional[str]]:
    """
    Agent1 output might be resume or JD.
    - For resume: do NOT assume hiring company from work history.
    - For JD: try to extract company.
    """
    doc_type = (agent1.get("doc_type") or "").lower()
    preview = agent1.get("raw_text_preview") or ""
    entities = agent1.get("entities") or {}

    company = None
    role = None

    # Try common company keys from entities (if your Agent1 extracts these)
    for k in ["Hiring Company", "Company", "Companies", "company", "companies"]:
        if k in entities and isinstance(entities[k], list) and entities[k]:
            company = entities[k][0]
            break

    # Try role from preview: "Role: X", "Title: X"
    # m = re.search(r"(?i)\b(role|position|title)\s*[:\-]\s*([A-Za-z0-9 /&\-\(\)]+)", preview)
    m = re.search(
        r"(?i)\b(role|position|title)\s*[:\-]\s*([^\n\r]+)",
        preview
        )
    if m:
        role = m.group(2).strip()[:120]

    if doc_type == "resume":
        return {"company_name": company, "role_title": role}

    # JD: try "Company: X"
    if not company:
        m2 = re.search(r"(?i)\bcompany\s*[:\-]\s*([A-Za-z0-9 .&\-\(\)]+)", preview)
        if m2:
            company = m2.group(1).strip()

    return {"company_name": company, "role_title": role}


# =========================================================
# Build Agent 2
# =========================================================
def build_agent2(model_name: str = "gemini-2.5-flash-lite", temperature: float = 0.2):
# def build_agent2(model_name: str = "gemini-2.5-flash", temperature: float = 0.2):
    llm = ChatGoogleGenerativeAI(
        model=model_name,
        temperature=temperature,
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        timeout=120,
        max_retries=2
    )

    # tools = [web_search_tavily, fetch_url_tavily,web_search_exa,fetch_url_exa]
    # tools = [web_search_tavily, fetch_url_tavily]
    tools = [web_search_auto, fetch_url_auto]

    system_prompt = """
You are Agent 2: Company Researcher for interview preparation.

CRITICAL OUTPUT RULE:
- Return ONLY valid JSON.
- Use double quotes for all keys and string values.
- Do NOT wrap output in markdown fences.
- No extra text before/after JSON.

Your job:
- Research the company + role using web_search_auto and optionally fetch_url_auto.
- Do not call separate Tavily or Exa tools directly.
- web_search_auto automatically switches between Tavily and Exa if one provider fails.
- fetch_url_auto automatically switches fetch providers if one fails.

# - Research the company + role using web_search and (optionally) fetch_url.
# - Summarize with sources so downstream agents can trust it.

Rules:
- Prefer official sources (company site, docs, investor pages).
- Use reputable publishers for news.
- If something is unknown, write it in notes. Do NOT guess.
- Keep summaries concise and useful for interview prep.

Output JSON schema:
{
  "company_name": "string",
  "role_title": "string or null",
  "overview": "string",
  "mission_values": ["string"],
  "products_services": ["string"],
  "business_model": ["string"],
  "interview_focus": ["string"],
  "interview_process": ["string"],
  "recent_news": [
    {"title":"string","source":"string","date":"string or null","url":"string","summary":"string"}
  ],
  "sources": ["string"],
  "notes": "string or null"
}

Research steps:
1) web_search_auto("<company> official about mission values products services")
2) web_search_auto("<company> business model revenue recent news")
3) If role_title exists: web_search_auto("<company> <role_title> interview process")
   Else: web_search_auto("<company> interview process")
4) Use fetch_url_auto only for 2-3 best official or reputable URLs.
5) Produce final JSON grounded in sources/snippets.

# 1) web_search("<company> about mission values")
# 2) web_search("<company> products services")
# 3) web_search("<company> business model revenue")
# 4) web_search("<company> recent news")
# 5) If role_title exists: web_search("<company> <role_title> interview") else web_search("<company> interview process")
# 6) Choose 3-5 best URLs and optionally fetch_url them (prefer official pages).
# 7) Produce the final JSON grounded in those sources/snippets.

"""

    return create_agent(model=llm, tools=tools, system_prompt=system_prompt)


# =========================================================
# Run Agent 2
# =========================================================
def run_agent2(
    agent1_output: Dict[str, Any],
    company_override: Optional[str] = None,
    role_override: Optional[str] = None,
) -> Dict[str, Any]:
    # agent = build_agent2()
    guessed = guess_company_and_role(agent1_output)

    company = company_override or guessed.get("company_name")
    role_title = role_override or guessed.get("role_title")

    # If company missing, return structured “need input”
    if not company:
        report = CompanyResearchReport(
            company_name="unknown",
            role_title=role_title,
            overview="Company name not found in Agent 1 output. Provide a company name override.",
            mission_values=[],
            products_services=[],
            business_model=[],
            interview_focus=[],
            interview_process=[],
            recent_news=[],
            sources=[],
            notes="Missing company_name. Pass --company or supply a JD with company name.",
        )
        return report.model_dump()

    agent = build_agent2()

    user_payload = {
        "company_name": company,
        "role_title": role_title,
        "agent1_doc_type": agent1_output.get("doc_type"),
        # "hint": "Use web_search + fetch_url. Keep it concise. Always include sources.",
        "hint": "Use web_search_auto and fetch_url_auto. Keep it concise. Always include sources.",
    }

    try:
        result = agent.invoke(
            {
                "messages": [
                    {"role": "user", 
                     "content": json.dumps(user_payload, ensure_ascii=False)
                    }
                ]
            }
        )
    except Exception as e:
        return {
            "error": "Agent 2 invocation failed.",
            "details": str(e),
            "company_name": company,
            "role_title": role_title,
        }

    text = _get_last_ai_content(result).strip()
    # data = extract_json_object(text)
    # if data:
    #     return data
    data = extract_json_object(text)

    if data:
        try:
            return CompanyResearchReport(**data).model_dump()
        except Exception as e:
            return {
                "error": "Model returned JSON but schema validation failed.",
                "validation_error": str(e),
                "raw_output": text,
            }

    return {"error": "Failed to parse JSON from agent output.", "raw_output": text}


# =========================================================
# CLI
# =========================================================
def main():
    parser = argparse.ArgumentParser(description="Agent 2 Company Researcher (Exa + Gemini)")
    parser.add_argument("--agent1_json", type=str, required=True, help="Path to Agent 1 output JSON file")
    parser.add_argument("--company", type=str, required=False, help="Company override (useful if Agent1 was resume)")
    parser.add_argument("--role", type=str, required=False, help="Role override")
    args = parser.parse_args()

    # helpful debugging for paths
    abs_path = os.path.abspath(args.agent1_json)
    if not os.path.exists(abs_path):
        raise FileNotFoundError(f"Agent1 JSON not found: {abs_path}")

    with open(abs_path, "r", encoding="utf-8") as f:
        agent1_data = json.load(f)

    out = run_agent2(agent1_data, company_override=args.company, role_override=args.role)
    print(json.dumps(out, indent=2, ensure_ascii=False))
    os.makedirs("app/output", exist_ok=True)

    with open("app/output/01_Test_Case_agent_2_OP_JD.json","w", encoding="utf-8") as f:
        json.dump(out,f,indent=2,ensure_ascii=False)

if __name__ == "__main__":
    main()

# run the Code
# python -m app.agents.agent_2_researcher --agent1_json "app/output/agent1.json" --company "Stripe" --role "Data Analyst"
# python -m app.agents.agent_2_researcher --agent1_json "app/output/20260408_142740/agent1_combined_out_20260408_142740.json" --company "Micro1" --role "AI/ML Engineer"