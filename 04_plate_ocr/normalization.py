import re
import unicodedata


def normalize_plate_text(raw_text: str) -> str:
    """
    Applies deterministic string normalization to raw OCR output:
    - Unicode NFKD decomposition
    - Strips whitespace, hyphens, dots, underscores, slashes, and noise
    - Converts to uppercase alphanumeric characters [A-Z0-9]
    - Does NOT apply global confusion replacement (e.g. does NOT blindly map O->0 or B->8)
    """
    if not raw_text or not isinstance(raw_text, str):
        return ''

    # 1. Unicode decomposition
    normalized = unicodedata.normalize('NFKD', raw_text)

    # 2. Uppercase
    normalized = normalized.upper()

    # 3. Strip non-alphanumeric characters (keeps only A-Z and 0-9)
    cleaned = re.sub(r'[^A-Z0-9]', '', normalized)

    return cleaned


def is_valid_candidate_length(text: str) -> bool:
    """Checks if normalized plate string length is within plausible Indian registration length."""
    return 6 <= len(text) <= 12
