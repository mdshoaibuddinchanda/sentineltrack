import numpy as np
from typing import Optional

# Standard Indian visual OCR confusion pairs
CONFUSION_PAIRS = {
    ('O', '0'), ('0', 'O'),
    ('Q', '0'), ('0', 'Q'),
    ('D', '0'), ('0', 'D'),
    ('D', 'O'), ('O', 'D'),
    ('I', '1'), ('1', 'I'),
    ('L', '1'), ('1', 'L'),
    ('Z', '2'), ('2', 'Z'),
    ('A', '4'), ('4', 'A'),
    ('S', '5'), ('5', 'S'),
    ('G', '6'), ('6', 'G'),
    ('B', '8'), ('8', 'B'),
}

LETTER_TO_DIGIT = {'O': '0', 'Q': '0', 'D': '0', 'I': '1', 'L': '1', 'Z': '2', 'A': '4', 'S': '5', 'G': '6', 'B': '8'}
DIGIT_TO_LETTER = {'0': 'O', '1': 'I', '2': 'Z', '4': 'A', '5': 'S', '6': 'G', '8': 'B'}


def is_exact_match(target: str, observed: str) -> bool:
    """High-speed exact string equality."""
    return target == observed and len(target) > 0


def standard_levenshtein(s1: str, s2: str) -> int:
    """Calculates standard unit-cost Levenshtein distance."""
    if s1 == s2:
        return 0
    len1, len2 = len(s1), len(s2)
    if len1 == 0:
        return len2
    if len2 == 0:
        return len1

    dp = np.zeros((len1 + 1, len2 + 1), dtype=np.int32)
    for i in range(len1 + 1):
        dp[i][0] = i
    for j in range(len2 + 1):
        dp[0][j] = j

    for i in range(1, len1 + 1):
        c1 = s1[i - 1]
        for j in range(1, len2 + 1):
            c2 = s2[j - 1]
            cost = 0 if c1 == c2 else 1
            dp[i][j] = min(
                dp[i - 1][j] + 1,      # Deletion
                dp[i][j - 1] + 1,      # Insertion
                dp[i - 1][j - 1] + cost # Substitution
            )

    return int(dp[len1][len2])


def damerau_levenshtein(s1: str, s2: str) -> int:
    """Calculates Damerau-Levenshtein distance supporting adjacent character transpositions."""
    if s1 == s2:
        return 0
    len1, len2 = len(s1), len(s2)
    if len1 == 0:
        return len2
    if len2 == 0:
        return len1

    dp = np.zeros((len1 + 1, len2 + 1), dtype=np.int32)
    for i in range(len1 + 1):
        dp[i][0] = i
    for j in range(len2 + 1):
        dp[0][j] = j

    for i in range(1, len1 + 1):
        c1 = s1[i - 1]
        for j in range(1, len2 + 1):
            c2 = s2[j - 1]
            cost = 0 if c1 == c2 else 1
            dp[i][j] = min(
                dp[i - 1][j] + 1,
                dp[i][j - 1] + 1,
                dp[i - 1][j - 1] + cost
            )
            # Transposition check
            if i > 1 and j > 1 and s1[i - 1] == s2[j - 2] and s1[i - 2] == s2[j - 1]:
                dp[i][j] = min(dp[i][j], dp[i - 2][j - 2] + 1)

    return int(dp[len1][len2])


def get_position_substitution_cost(
    target_char: str,
    obs_char: str,
    pos: int,
    total_len: int,
    base_confusion_cost: float = 0.20
) -> float:
    """
    Computes position-aware character substitution cost between target and observed characters.
    Discounts plausible confusions ONLY when slot grammar context supports it.
    """
    if target_char == obs_char:
        return 0.0

    pair = (target_char, obs_char)

    # 1. Check if characters form a recognized visual confusion pair
    if pair in CONFUSION_PAIRS or (obs_char, target_char) in CONFUSION_PAIRS:
        # State slot (positions 0, 1) expects LETTERS
        if pos in (0, 1):
            if target_char.isalpha() and obs_char.isdigit():
                return base_confusion_cost
            elif target_char.isalpha() and obs_char.isalpha():
                return base_confusion_cost * 1.25

        # RTO slot (positions 2, 3) expects DIGITS
        elif pos in (2, 3):
            if target_char.isdigit() and obs_char.isalpha():
                return base_confusion_cost
            elif target_char.isdigit() and obs_char.isdigit():
                return base_confusion_cost * 1.25

        # Numeric Suffix (last 4 positions) expects DIGITS
        elif pos >= max(4, total_len - 4):
            if target_char.isdigit() and obs_char.isalpha():
                return base_confusion_cost
            elif target_char.isdigit() and obs_char.isdigit():
                return base_confusion_cost * 1.25

        # General unpositioned plausible confusion
        return base_confusion_cost * 1.75

    # Standard incompatible substitution
    return 1.0


def position_weighted_edit_distance(
    target: str,
    observed: str,
    base_confusion_cost: float = 0.20,
    insertion_cost: float = 1.0,
    deletion_cost: float = 1.0
) -> tuple[float, list[str]]:
    """
    Calculates position-aware weighted edit distance and records explicit substitution reasons.
    """
    if target == observed:
        return 0.0, ['Exact identical character match']

    len_t, len_o = len(target), len(observed)
    if len_t == 0:
        return float(len_o) * insertion_cost, [f'Observed has {len_o} extra characters on empty target']
    if len_o == 0:
        return float(len_t) * deletion_cost, [f'Observed is missing all {len_t} characters']

    dp = np.zeros((len_t + 1, len_o + 1), dtype=np.float64)
    for i in range(len_t + 1):
        dp[i][0] = i * deletion_cost
    for j in range(len_o + 1):
        dp[0][j] = j * insertion_cost

    for i in range(1, len_t + 1):
        c_t = target[i - 1]
        for j in range(1, len_o + 1):
            c_o = observed[j - 1]
            sub_cost = get_position_substitution_cost(c_t, c_o, i - 1, len_t, base_confusion_cost)

            dp[i][j] = min(
                dp[i - 1][j] + deletion_cost,
                dp[i][j - 1] + insertion_cost,
                dp[i - 1][j - 1] + sub_cost
            )

    dist = float(dp[len_t][len_o])

    # Generate reasons
    reasons = []
    if abs(len_t - len_o) > 0:
        reasons.append(f'Length difference of {abs(len_t - len_o)} char(s) (target: {len_t}, observed: {len_o})')

    # Trace aligned characters if lengths are similar
    if len_t == len_o:
        diff_count = 0
        conf_count = 0
        for idx, (ct, co) in enumerate(zip(target, observed)):
            if ct != co:
                diff_count += 1
                if (ct, co) in CONFUSION_PAIRS or (co, ct) in CONFUSION_PAIRS:
                    conf_count += 1
                    reasons.append(f"Position {idx + 1}: '{co}' observed vs '{ct}' target (plausible OCR confusion)")
                else:
                    reasons.append(f"Position {idx + 1}: '{co}' observed vs '{ct}' target (character mismatch)")
        if diff_count == 0:
            reasons.append('All characters matched')
    else:
        reasons.append(f'Weighted edit distance: {dist:.2f}')

    return round(dist, 4), reasons


def calculate_normalized_similarity(target: str, observed: str, confusion_dist: float) -> float:
    """Converts distance into normalized similarity score [0.0, 1.0]."""
    max_len = max(len(target), len(observed), 1)
    norm_dist = min(confusion_dist / max_len, 1.0)
    return round(max(0.0, 1.0 - norm_dist), 4)
