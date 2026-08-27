import re

INDIAN_STATE_CODES = {
    'AN', 'AP', 'AR', 'AS', 'BR', 'CG', 'CH', 'DD', 'DL', 'DN', 'GA', 'GJ',
    'HP', 'HR', 'JH', 'JK', 'KA', 'KL', 'LA', 'LD', 'MH', 'ML', 'MN', 'MP',
    'MZ', 'NL', 'OD', 'OR', 'PB', 'PY', 'RJ', 'SK', 'TN', 'TR', 'TS', 'UK',
    'UA', 'UP', 'WB'
}

PATTERN_STANDARD = re.compile(r'^[A-Z]{2}[0-9]{1,2}[A-Z]{0,3}[0-9]{4}$')
PATTERN_BH_SERIES = re.compile(r'^[0-9]{2}BH[0-9]{4}[A-Z]{1,2}$')
PATTERN_DEFENSE = re.compile(r'^[0-9]{2}[A-Z][0-9]{6}[A-Z]?$')
PATTERN_DIPLOMATIC = re.compile(r'^[0-9]{2,3}(CD|CC|UN)[0-9]+$')

# Positional substitution maps
LETTER_TO_DIGIT_MAP = {'O': '0', 'Q': '0', 'D': '0', 'I': '1', 'L': '1', 'Z': '2', 'A': '4', 'S': '5', 'G': '6', 'B': '8'}
DIGIT_TO_LETTER_MAP = {'0': 'O', '1': 'I', '2': 'Z', '4': 'A', '5': 'S', '6': 'G', '8': 'B'}


def score_indian_grammar(plate_text: str) -> float:
    """
    Computes a soft grammar plausibility score [0.0, 1.0] for a normalized plate string.
    """
    if not plate_text or not isinstance(plate_text, str):
        return 0.0

    length = len(plate_text)
    if length < 6 or length > 12:
        return max(0.1, 1.0 - abs(length - 9) * 0.15)

    score = 0.35  # Baseline length adequacy

    # 1. BH-Series Check
    if PATTERN_BH_SERIES.match(plate_text):
        return 0.98

    # 2. State Prefix Validation
    prefix = plate_text[:2]
    if prefix in INDIAN_STATE_CODES:
        score += 0.40
        if PATTERN_STANDARD.match(plate_text):
            score += 0.25
        elif len(plate_text) >= 8 and plate_text[-4:].isdigit():
            score += 0.15
    elif prefix.isalpha():
        score += 0.10
        if PATTERN_STANDARD.match(plate_text):
            score += 0.20
        elif len(plate_text) >= 8 and plate_text[-4:].isdigit():
            score += 0.10
    elif PATTERN_DEFENSE.match(plate_text) or PATTERN_DIPLOMATIC.match(plate_text):
        score += 0.40

    return round(min(1.0, score), 4)


def generate_grammar_alternatives(plate_text: str, max_candidates: int = 5) -> list[tuple[str, float]]:
    """
    Generates position-aware alternatives using soft Indian registration grammar.
    Only swaps letters/digits where slot position context supports it.
    """
    candidates = [(plate_text, score_indian_grammar(plate_text))]

    if len(plate_text) < 7:
        return candidates

    chars = list(plate_text)
    n = len(chars)

    # Position 0, 1: State Code expects LETTERS
    for i in [0, 1]:
        if chars[i] in DIGIT_TO_LETTER_MAP:
            fixed = list(chars)
            fixed[i] = DIGIT_TO_LETTER_MAP[chars[i]]
            fixed_str = ''.join(fixed)
            candidates.append((fixed_str, score_indian_grammar(fixed_str)))

    # Position 2, 3: RTO Code expects DIGITS
    for i in [2, 3]:
        if i < n and chars[i] in LETTER_TO_DIGIT_MAP:
            fixed = list(chars)
            fixed[i] = LETTER_TO_DIGIT_MAP[chars[i]]
            fixed_str = ''.join(fixed)
            candidates.append((fixed_str, score_indian_grammar(fixed_str)))

    # Suffix: Last 4 characters expect DIGITS
    for i in range(max(4, n - 4), n):
        if chars[i] in LETTER_TO_DIGIT_MAP:
            fixed = list(chars)
            fixed[i] = LETTER_TO_DIGIT_MAP[chars[i]]
            fixed_str = ''.join(fixed)
            candidates.append((fixed_str, score_indian_grammar(fixed_str)))

    seen = set()
    unique_candidates = []
    for cand, sc in sorted(candidates, key=lambda x: x[1], reverse=True):
        if cand not in seen:
            seen.add(cand)
            unique_candidates.append((cand, sc))

    return unique_candidates[:max_candidates]
