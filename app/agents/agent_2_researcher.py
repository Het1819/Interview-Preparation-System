# app/agents/agent_2_researcher.py
from __future__ import annotations

import os
import re
import json
import argparse
from typing import Any, Dict, Optional, List
from dotenv import load_dotenv
load_dotenv()

import requests
from pydantic import BaseModel, Field

from langchain.agents import create_agent
from langchain.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI

# Exa
from exa_py import Exa

# =========================================================
# Output Schema: Agent 2
# =========================================================
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
# Exa Search Tool
# =========================================================
def _exa_client() -> Exa:
    api_key = os.getenv("EXA_API_KEY")
    if not api_key:
        raise EnvironmentError("Missing EXA_API_KEY in environment variables.")
    return Exa(api_key=api_key)


def _domain_from_url(url: str) -> str:
    try:
        m = re.search(r"https?://([^/]+)/?", url)
        return m.group(1) if m else ""
    except Exception:
        return ""


@tool
def web_search(query: str) -> str:
    """
    Web search using Exa.
    Returns JSON string:
    {
      "query": "...",
      "results": [
        {"title": "...", "snippet": "...", "url": "...", "source": "..."},
        ...
      ]
    }
    """
    query = (query or "").strip()
    if not query:
        return json.dumps({"error": "Empty query"}, ensure_ascii=False)

    try:
        exa = _exa_client()

        # Exa can return text/highlights. We'll keep it lightweight.
        resp = exa.search_and_contents(
            query=query,
            num_results=6,
            text=True,
            highlights=True,
            # You can optionally bias freshness:
            # start_published_date="2024-01-01",
        )

        results: List[Dict[str, str]] = []
        for r in getattr(resp, "results", []) or []:
            url = getattr(r, "url", "") or ""
            title = getattr(r, "title", "") or ""

            snippet = ""
            highlights = getattr(r, "highlights", None)
            if highlights:
                snippet = " ".join(highlights)[:600]
            else:
                txt = getattr(r, "text", "") or ""
                snippet = txt[:600]

            results.append(
                {
                    "title": title,
                    "snippet": snippet,
                    "url": url,
                    "source": _domain_from_url(url),
                }
            )

        if not results:
            return json.dumps({"error": "No results from Exa.", "query": query}, ensure_ascii=False)

        return json.dumps({"query": query, "results": results}, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"error": str(e), "query": query}, ensure_ascii=False)


@tool
def fetch_url(url: str) -> str:
    """
    Optional: fetch raw page text for grounding.
    Exa already returns text, but this can help for official pages that Exa summaries miss.
    Returns JSON:
    {"url":"...", "text":"..."} or {"url":"...", "error":"..."}
    """
    url = (url or "").strip()
    if not url:
        return json.dumps({"error": "Empty url"}, ensure_ascii=False)

    try:
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
        html = r.text

        # basic HTML -> text
        text = re.sub(r"(?is)<script.*?>.*?</script>", " ", html)
        text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
        text = re.sub(r"(?s)<.*?>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()

        return json.dumps({"url": url, "text": text[:12000]}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"url": url, "error": str(e)}, ensure_ascii=False)


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
    m = re.search(r"(?i)\b(role|position|title)\s*[:\-]\s*([A-Za-z0-9 /&\-\(\)]+)", preview)
    if m:
        role = m.group(2).strip()

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
def build_agent2(model_name: str = "gemini-2.5-flash", temperature: float = 0.2):
    llm = ChatGoogleGenerativeAI(
        model=model_name,
        temperature=temperature,
        google_api_key=os.getenv("GOOGLE_API_KEY"),
    )

    tools = [web_search, fetch_url]

    system_prompt = """
You are Agent 2: Company Researcher for interview preparation.

CRITICAL OUTPUT RULE:
- Return ONLY valid JSON.
- Use double quotes for all keys and string values.
- Do NOT wrap output in markdown fences.
- No extra text before/after JSON.

Your job:
- Research the company + role using web_search and (optionally) fetch_url.
- Summarize with sources so downstream agents can trust it.

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

Research steps (do them):
1) web_search("<company> about mission values")
2) web_search("<company> products services")
3) web_search("<company> business model revenue")
4) web_search("<company> recent news")
5) If role_title exists: web_search("<company> <role_title> interview") else web_search("<company> interview process")
6) Choose 3-5 best URLs and optionally fetch_url them (prefer official pages).
7) Produce the final JSON grounded in those sources/snippets.
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
    agent = build_agent2()

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

    user_payload = {
        "company_name": company,
        "role_title": role_title,
        "agent1_doc_type": agent1_output.get("doc_type"),
        "hint": "Use web_search + fetch_url. Keep it concise. Always include sources.",
    }

    result = agent.invoke(
        {"messages": [{"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)}]}
    )

    text = _get_last_ai_content(result).strip()
    data = extract_json_object(text)
    if data:
        return data

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
    with open("app/output/03_Test_Case_agent_2_OP_JD.json","w", encoding="utf-8") as f:
        json.dump(out,f,indent=2,ensure_ascii=False)

if __name__ == "__main__":
    main()

# run the Code
# python -m app.agents.agent_2_researcher --agent1_json "app/output/agent1.json" --company "Stripe" --role "Data Analyst"