SECTION32_SCHEMA = {
  "type": "object",
  "properties": {
    "title": {
      "type": "object",
      "properties": {
        "owner_names": {"type": "array", "items": {"type": "string"}},
        "volume_folio": {"type": "string"},
        "plan_lot": {"type": "string"},
        "encumbrances": {"type": "array", "items": {"type": "string"}},
        "supporting_doc_present": {"type": "boolean"},
        "page_refs": {"type": "array", "items": {"type": "integer"}}
      },
      "required": ["supporting_doc_present", "page_refs"]
    },
    "mortgages": {
      "type": "object",
      "properties": {
        "mortgagees": {"type": "array", "items": {"type": "string"}},
        "discharge_required": {"type": "boolean"},
        "supporting_doc_present": {"type": "boolean"},
        "page_refs": {"type": "array", "items": {"type": "integer"}}
      },
      "required": ["supporting_doc_present", "page_refs"]
    },
    "planning_zoning": {
      "type": "object",
      "properties": {
        "zone": {"type": "string"},
        "overlays": {"type": "array", "items": {"type": "string"}},
        "certificate_date": {"type": "string"},
        "supporting_doc_present": {"type": "boolean"},
        "page_refs": {"type": "array", "items": {"type": "integer"}}
      },
      "required": ["supporting_doc_present", "page_refs"]
    },
    "rates_outgoings": {
      "type": "object",
      "properties": {
        "council": {"type": "string"},
        "annual_amount": {"type": "string"},
        "owners_corp": {"type": "string"},
        "supporting_doc_present": {"type": "boolean"},
        "page_refs": {"type": "array", "items": {"type": "integer"}}
      },
      "required": ["supporting_doc_present", "page_refs"]
    },
    "insurance": {
      "type": "object",
      "properties": {
        "policy_number": {"type": "string"},
        "insurer": {"type": "string"},
        "valid_to": {"type": "string"},
        "supporting_doc_present": {"type": "boolean"},
        "page_refs": {"type": "array", "items": {"type": "integer"}}
      },
      "required": ["supporting_doc_present", "page_refs"]
    },
    "building_permits": {
      "type": "object",
      "properties": {
        "permits": {"type": "array", "items": {"type": "string"}},
        "owner_builder": {"type": "boolean"},
        "warranty_insurance": {"type": "string"},
        "supporting_doc_present": {"type": "boolean"},
        "page_refs": {"type": "array", "items": {"type": "integer"}}
      },
      "required": ["supporting_doc_present", "page_refs"]
    },
    "notices": {
      "type": "object",
      "properties": {
        "adverse_notices": {"type": "array", "items": {"type": "string"}},
        "supporting_doc_present": {"type": "boolean"},
        "page_refs": {"type": "array", "items": {"type": "integer"}}
      },
      "required": ["supporting_doc_present", "page_refs"]
    },
    "special_conditions": {
      "type": "object",
      "properties": {
        "items": {"type": "array", "items": {"type": "string"}},
        "caveats": {"type": "array", "items": {"type": "string"}},
        "supporting_doc_present": {"type": "boolean"},
        "page_refs": {"type": "array", "items": {"type": "integer"}}
      },
      "required": ["supporting_doc_present", "page_refs"]
    },
    "missing_or_unclear": {
      "type": "array",
      "items": {"type": "string"}
    }
  },
  "required": ["title","mortgages","planning_zoning","rates_outgoings","insurance","building_permits","notices","special_conditions","missing_or_unclear"]
}

EXTRACTION_INSTRUCTIONS = """
You are extracting a Victorian Section 32 (Vendor Statement) summary.

RULES:
- Only return valid JSON matching the provided schema.
- Use the exact field names.
- For each section, set supporting_doc_present true/false based on evidence.
- Always include page_refs (list of integers).
- If a field isn't present, leave it empty but still include the key; also add a human-readable note to `missing_or_unclear`.
- Never invent data; if uncertain, state so in `missing_or_unclear`.

Checklist to look for:
- Title (volume/folio, plan/lot, encumbrances/easements, caveats)
- Mortgages/charges & discharge
- Planning/Zoning certificate (zone/overlays, date, authority)
- Rates & outgoings (council, owners corp/strata)
- Insurance (building policy; owner-builder warranty if applicable)
- Building permits (numbers/dates, owner-builder status)
- Notices/adverse matters (from council or authorities)
- Special conditions & caveats (contract specials, restrictions)
"""
