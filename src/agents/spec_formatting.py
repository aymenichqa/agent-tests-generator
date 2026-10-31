"""
Shared spec formatting helpers for agents.

Provides a single source of truth for formatting ParsedSpecification items
with their unique_codes, used by TestDesignAgent and EdgeCasesAgent.
"""
from src.analysis.models import ParsedSpecification, ExceptionSpec


def format_spec_items(spec: ParsedSpecification) -> list[tuple[str, str, str]]:
    """
    Formate les items d'une spec avec leurs unique_codes stables.

    Args:
        spec: Spécification parsée.

    Returns:
        list[tuple[str, str, str]] — Liste de (kind, code, text) où kind est
            'REQ', 'RG' ou 'EX', code est le unique_code stable, et text est
            la description lisible.

    Raises:
        ValueError: Si un item n'a pas de unique_code (fail loudly, pas silencieux).
    """
    items: list[tuple[str, str, str]] = []

    for req in spec.requirements or []:
        if isinstance(req, dict):
            codes = req.get("unique_codes", []) or []
            text = req.get("id", str(req))
        else:
            codes = []
            text = str(req)
        if not codes:
            raise ValueError(
                f"Requirement sans unique_code : {text!r}. "
                "Tous les items doivent avoir un unique_code assigné à la naissance."
            )
        items.append(("REQ", codes[0], text))

    for rule in spec.business_rules or []:
        if isinstance(rule, dict):
            codes = rule.get("unique_codes", []) or []
            text = rule.get("id", str(rule))
        else:
            codes = []
            text = str(rule)
        if not codes:
            raise ValueError(
                f"Business rule sans unique_code : {text!r}. "
                "Tous les items doivent avoir un unique_code assigné à la naissance."
            )
        items.append(("RG", codes[0], text))

    for exc in spec.exceptions or []:
        if isinstance(exc, ExceptionSpec):
            codes = exc.unique_codes
            label = exc.name
            desc = exc.description or ""
            text = f"{label}{f' — {desc}' if desc else ''}"
        elif isinstance(exc, dict):
            codes = exc.get("unique_codes", []) or []
            label = exc.get("name", "")
            desc = exc.get("description", "")
            text = f"{label}{f' — {desc}' if desc else ''}"
        else:
            codes = []
            text = str(exc)
        if not codes:
            raise ValueError(
                f"Exception sans unique_code : {text!r}. "
                "Tous les items doivent avoir un unique_code assigné à la naissance."
            )
        items.append(("EX", codes[0], text))

    return items


def build_traceability_prompt(spec: ParsedSpecification) -> str:
    """
    Construit le bloc de traçabilité à inclure dans les prompts.

    Liste tous les items avec leurs codes stables pour que le LLM
    puisse les référencer dans les cas de test.
    """
    items = format_spec_items(spec)
    lines: list[str] = []

    for kind, code, text in items:
        lines.append(f"- {code}: {text}")

    return "\n".join(lines)
