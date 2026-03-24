def normalize_query(q: str) -> str:
    """Collapse whitespace and strip so queries are consistent regardless of input formatting."""
    return " ".join((q or "").strip().split())
