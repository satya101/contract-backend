import json
from typing import Any, Dict, List
from openai import OpenAI

def _extract_json(text: str) -> Dict[str, Any]:
    text = (text or "").strip()
    start = text.find("{")
    end = text.rfind("}")
    snippet = text[start:end+1] if start != -1 and end != -1 and end > start else text
    return json.loads(snippet)

def call_model(client: OpenAI, model: str, schema: Dict[str, Any], instructions: str, chunk_text: str) -> Dict[str, Any]:
    prompt = f"""{instructions}

SOURCE:
{chunk_text}

Return JSON ONLY, matching this JSON schema loosely (names/types):
{json.dumps(schema, indent=2)}
"""
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    txt = resp.choices[0].message.content or "{}"
    return _extract_json(txt)

def merge_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    def union_list(a, b):
        if isinstance(a, list) and isinstance(b, list):
            return sorted(list({x for x in (a + b) if x not in (None, "")}))
        if isinstance(a, list): return a
        if isinstance(b, list): return b
        return []

    wanted = ["title","mortgages","planning_zoning","rates_outgoings","insurance","building_permits","notices","special_conditions"]

    for r in results:
        for key, val in r.items():
            if key in wanted and isinstance(val, dict):
                out.setdefault(key, {})
                cur = out[key]
                for k, v in val.items():
                    if k == "page_refs" and isinstance(v, list):
                        cur.setdefault("page_refs", [])
                        cur["page_refs"] = sorted(list(set(cur["page_refs"] + v)))
                    elif k == "supporting_doc_present":
                        cur["supporting_doc_present"] = bool(v) or cur.get("supporting_doc_present", False)
                    elif isinstance(v, list):
                        cur[k] = union_list(cur.get(k, []), v)
                    else:
                        cur[k] = v or cur.get(k)
            elif key == "missing_or_unclear" and isinstance(val, list):
                out.setdefault("missing_or_unclear", [])
                out["missing_or_unclear"] = union_list(out["missing_or_unclear"], val)

    for req in wanted:
        out.setdefault(req, {})
        out[req].setdefault("supporting_doc_present", False)
        out[req].setdefault("page_refs", [])

    out.setdefault("missing_or_unclear", [])
    return out
