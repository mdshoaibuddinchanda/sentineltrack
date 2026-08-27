import importlib
import re
from typing import Optional

# Re-use Priority 4 normalization logic to guarantee 100% semantic parity
norm_mod = importlib.import_module('04_plate_ocr.normalization')
normalize_plate_text = norm_mod.normalize_plate_text
is_valid_candidate_length = norm_mod.is_valid_candidate_length


def normalize_target_registration(raw_input: str) -> tuple[str, bool, Optional[str]]:
    """
    Normalizes a police/operator-entered target registration.
    Returns:
        tuple[normalized_registration: str, is_valid: bool, error_message: Optional[str]]
    """
    if raw_input is None:
        return '', False, 'Target registration cannot be None'

    cleaned = str(raw_input).strip()
    if not cleaned:
        return '', False, 'Target registration cannot be empty'

    normalized = normalize_plate_text(cleaned)
    if not normalized:
        return '', False, f'Target registration "{raw_input}" contains no valid alphanumeric characters'

    if len(normalized) < 4:
        return normalized, False, f'Target registration "{normalized}" is too short (minimum 4 characters required)'

    if len(normalized) > 14:
        return normalized, False, f'Target registration "{normalized}" is too long (maximum 14 characters allowed)'

    return normalized, True, None


def normalize_search_query(query: str) -> tuple[str, bool, bool]:
    """
    Normalizes an operator search query, supporting wildcard queries (e.g. GJ01AB* or GJ01AB????).
    Returns:
        tuple[normalized_query: str, is_wildcard: bool, is_valid: bool]
    """
    if not query or not isinstance(query, str):
        return '', False, False

    q = query.strip().upper()
    is_wildcard = '*' in q or '?' in q or '%' in q

    # Preserve wildcard tokens while normalizing remaining alphanumeric chars
    cleaned = re.sub(r'[^A-Z0-9\*\?\%]', '', q)
    if not cleaned:
        return '', is_wildcard, False

    return cleaned, is_wildcard, True
