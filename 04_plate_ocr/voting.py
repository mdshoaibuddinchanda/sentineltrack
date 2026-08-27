import math
from typing import Optional
from .models import OCRHypothesis, TrackOCRResult
from .normalization import normalize_plate_text
from .grammar import score_indian_grammar, generate_grammar_alternatives, LETTER_TO_DIGIT_MAP, DIGIT_TO_LETTER_MAP

CONFUSION_PAIRS = {
    frozenset({'0', 'O'}), frozenset({'0', 'Q'}), frozenset({'0', 'D'}),
    frozenset({'1', 'I'}), frozenset({'1', 'L'}), frozenset({'2', 'Z'}),
    frozenset({'4', 'A'}), frozenset({'5', 'S'}), frozenset({'6', 'G'}),
    frozenset({'8', 'B'})
}


def weighted_levenshtein(s1: str, s2: str, confusion_cost: float = 0.35) -> float:
    """Computes Levenshtein distance with position-aware character confusion discount."""
    if s1 == s2:
        return 0.0
    if not s1:
        return float(len(s2))
    if not s2:
        return float(len(s1))

    m, n = len(s1), len(s2)
    dp = [[0.0] * (n + 1) for _ in range(m + 1)]

    for i in range(m + 1):
        dp[i][0] = float(i)
    for j in range(n + 1):
        dp[0][j] = float(j)

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            c1, c2 = s1[i - 1], s2[j - 1]
            if c1 == c2:
                cost = 0.0
            elif frozenset({c1, c2}) in CONFUSION_PAIRS:
                # Check slot context if strings are roughly aligned
                pos = i - 1
                if pos < 2 and (c1 in DIGIT_TO_LETTER_MAP or c2 in DIGIT_TO_LETTER_MAP):
                    cost = confusion_cost
                elif pos >= 2 and (c1 in LETTER_TO_DIGIT_MAP or c2 in LETTER_TO_DIGIT_MAP):
                    cost = confusion_cost
                else:
                    cost = confusion_cost * 1.2
            else:
                cost = 1.0

            dp[i][j] = min(
                dp[i - 1][j] + 1.0,
                dp[i][j - 1] + 1.0,
                dp[i - 1][j - 1] + cost
            )

    return dp[m][n]


def normalized_edit_distance(s1: str, s2: str) -> float:
    """Returns normalized edit distance in range [0.0, 1.0]."""
    max_len = max(len(s1), len(s2))
    if max_len == 0:
        return 0.0
    dist = weighted_levenshtein(s1, s2)
    return dist / max_len


def resolve_character_consensus(candidate_strings: list[tuple[str, float]]) -> str:
    """Performs character-level alignment and weighted voting."""
    if not candidate_strings:
        return ''
    if len(candidate_strings) == 1:
        return candidate_strings[0][0]

    length_weights = {}
    for s, w in candidate_strings:
        length_weights[len(s)] = length_weights.get(len(s), 0.0) + w

    target_len = max(length_weights.items(), key=lambda x: x[1])[0]
    matched = [s for s, w in candidate_strings if len(s) == target_len]
    matched_weights = [w for s, w in candidate_strings if len(s) == target_len]

    consensus_chars = []
    for pos in range(target_len):
        char_scores = {}
        for (s, w) in zip(matched, matched_weights):
            ch = s[pos]
            char_scores[ch] = char_scores.get(ch, 0.0) + w

        best_ch = max(char_scores.items(), key=lambda x: x[1])[0]
        consensus_chars.append(best_ch)

    return ''.join(consensus_chars)


class MultiFramePlateVoter:
    """Combines multiple OCR frame hypotheses across a vehicle track."""

    def __init__(
        self,
        min_crop_quality: float = 0.20,
        min_confidence_threshold: float = 0.50,
        min_support_count: int = 2,
        cluster_distance_threshold: float = 0.35,
        w_conf: float = 0.45,
        w_qual: float = 0.25,
        w_gram: float = 0.30,
    ):
        self.min_crop_quality = min_crop_quality
        self.min_confidence_threshold = min_confidence_threshold
        self.min_support_count = min_support_count
        self.cluster_distance_threshold = cluster_distance_threshold
        self.w_conf = w_conf
        self.w_qual = w_qual
        self.w_gram = w_gram

    def vote(self, hypotheses: list[OCRHypothesis]) -> TrackOCRResult:
        if not hypotheses:
            return TrackOCRResult(
                camera_id='unknown',
                track_id=0,
                stream_epoch=0,
                first_pts_ms=0.0,
                last_pts_ms=0.0,
                best_text=None,
                confidence=0.0,
                support_count=0,
                total_hypotheses=0,
                status='INSUFFICIENT_EVIDENCE',
                alternatives=[],
                hypotheses=[]
            )

        cam_id = hypotheses[0].camera_id
        trk_id = hypotheses[0].track_id
        epoch = hypotheses[0].stream_epoch
        pts_list = [h.pts_ms for h in hypotheses]
        first_pts = min(pts_list)
        last_pts = max(pts_list)

        valid_hyps = [h for h in hypotheses if h.crop_quality >= self.min_crop_quality and len(h.normalized_text) >= 5]
        if not valid_hyps:
            valid_hyps = [h for h in hypotheses if len(h.normalized_text) >= 5]

        if not valid_hyps:
            return TrackOCRResult(
                camera_id=cam_id,
                track_id=trk_id,
                stream_epoch=epoch,
                first_pts_ms=first_pts,
                last_pts_ms=last_pts,
                best_text=None,
                confidence=0.0,
                support_count=0,
                total_hypotheses=len(hypotheses),
                status='INSUFFICIENT_EVIDENCE',
                alternatives=[],
                hypotheses=hypotheses
            )

        clusters: list[list[OCRHypothesis]] = []
        for h in valid_hyps:
            assigned = False
            for c in clusters:
                rep_text = c[0].normalized_text
                if normalized_edit_distance(h.normalized_text, rep_text) <= self.cluster_distance_threshold:
                    c.append(h)
                    assigned = True
                    break
            if not assigned:
                clusters.append([h])

        cluster_scores = []
        for c in clusters:
            support = len(c)
            hyp_score = sum(
                (self.w_conf * (h.ocr_confidence or 0.5) + self.w_qual * h.crop_quality + self.w_gram * h.grammar_score)
                for h in c
            )
            total_score = hyp_score * (1.0 + math.log2(1.0 + support))
            cluster_scores.append((c, total_score, support))

        cluster_scores.sort(key=lambda x: x[1], reverse=True)
        winner_cluster, winner_score, winner_support = cluster_scores[0]

        weighted_strings = [
            (h.normalized_text, (self.w_conf * (h.ocr_confidence or 0.5) + self.w_qual * h.crop_quality + self.w_gram * h.grammar_score))
            for h in winner_cluster
        ]
        consensus_text = resolve_character_consensus(weighted_strings)

        grammar_cands = generate_grammar_alternatives(consensus_text)
        final_best_text = grammar_cands[0][0] if grammar_cands else consensus_text
        final_grammar_score = score_indian_grammar(final_best_text)

        total_all_scores = sum(cs[1] for cs in cluster_scores)
        dominance_ratio = winner_score / max(total_all_scores, 1e-6)
        avg_quality = float(sum(h.crop_quality for h in winner_cluster) / len(winner_cluster))
        avg_ocr_conf = float(sum((h.ocr_confidence or 0.5) for h in winner_cluster) / len(winner_cluster))

        final_conf = (
            0.40 * dominance_ratio +
            0.30 * avg_ocr_conf +
            0.20 * final_grammar_score +
            0.10 * avg_quality
        )
        final_conf = round(min(0.99, max(0.01, final_conf)), 4)

        if winner_support < self.min_support_count:
            status = 'CANDIDATE' if final_conf >= 0.40 else 'LOW_CONFIDENCE'
        elif final_conf >= self.min_confidence_threshold:
            status = 'RESOLVED'
        else:
            status = 'LOW_CONFIDENCE'

        alternatives = []
        for c, sc, sup in cluster_scores[1:]:
            rep = c[0].normalized_text
            alt_conf = round(min(0.90, sc / max(total_all_scores, 1e-6)), 4)
            alternatives.append((rep, alt_conf))

        return TrackOCRResult(
            camera_id=cam_id,
            track_id=trk_id,
            stream_epoch=epoch,
            first_pts_ms=first_pts,
            last_pts_ms=last_pts,
            best_text=final_best_text if status in ('RESOLVED', 'CANDIDATE') else (final_best_text if final_conf >= 0.40 else None),
            confidence=final_conf,
            support_count=winner_support,
            total_hypotheses=len(hypotheses),
            status=status,
            alternatives=alternatives[:3],
            hypotheses=hypotheses
        )
