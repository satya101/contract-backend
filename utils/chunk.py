from typing import List, Dict, Any

def chunk_pages(pages: List[Dict[str, Any]], max_chars: int = 8000) -> List[Dict[str, Any]]:
    chunks = []
    buff, buff_pages = "", []
    for p in pages:
        header = f"[[PAGE {p['page']}]]\n"
        candidate = header + (p.get("text") or "") + "\n\n"
        if len(buff) + len(candidate) > max_chars and buff:
            chunks.append({"text": buff, "pages": buff_pages[:]})
            buff, buff_pages = "", []
        buff += candidate
        buff_pages.append(p["page"])
    if buff:
        chunks.append({"text": buff, "pages": buff_pages})
    return chunks
