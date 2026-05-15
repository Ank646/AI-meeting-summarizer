"""
Evaluation metrics for the AI pipeline.

Metrics tracked:
  WER  — Word Error Rate        (ASR quality)
  DER  — Diarization Error Rate (speaker assignment quality)
  Precision/Recall              (extraction quality)
  FPR  — False Positive Rate    (extraction noise)
"""

from typing import List, Optional
from dataclasses import dataclass


@dataclass
class EvaluationMetrics:
    wer: float = 0.0               # Word Error Rate
    der: float = 0.0               # Diarization Error Rate
    task_precision: float = 0.0    # TP / (TP + FP)
    task_recall: float = 0.0       # TP / (TP + FN)
    decision_precision: float = 0.0
    decision_recall: float = 0.0
    fpr: float = 0.0               # FP / (FP + TN)


def compute_wer(reference: List[str], hypothesis: List[str]) -> float:
    """
    Standard Word Error Rate using dynamic programming (edit distance).
    reference:  list of reference words
    hypothesis: list of ASR-produced words
    Returns WER in range [0.0, ∞).  Perfect = 0.0.
    """
    r = [w.lower().strip(".,!?;:") for w in reference]
    h = [w.lower().strip(".,!?;:") for w in hypothesis]

    n = len(r)
    if n == 0:
        return 0.0 if not h else float(len(h))

    # Build distance matrix
    d = [[0] * (len(h) + 1) for _ in range(len(r) + 1)]
    for i in range(len(r) + 1):
        d[i][0] = i
    for j in range(len(h) + 1):
        d[0][j] = j

    for i in range(1, len(r) + 1):
        for j in range(1, len(h) + 1):
            if r[i - 1] == h[j - 1]:
                d[i][j] = d[i - 1][j - 1]
            else:
                d[i][j] = 1 + min(d[i - 1][j], d[i][j - 1], d[i - 1][j - 1])

    return d[len(r)][len(h)] / n


def compute_der(
    reference_segments: List[dict],  # [{"start": float, "end": float, "speaker": str}]
    hypothesis_segments: List[dict],
    total_duration: float,
) -> float:
    """
    Simplified DER: fraction of time with wrong speaker assignment.
    DER = (FA + MISS + SE) / total_speech_time
    where:
      FA   = false alarm (speech detected where there is none)
      MISS = missed speech
      SE   = speaker error (wrong speaker)
    """
    if total_duration <= 0:
        return 0.0

    error_time = 0.0
    step = 0.02  # 20ms evaluation resolution

    t = 0.0
    while t < total_duration:
        ref_speaker = _speaker_at(reference_segments, t)
        hyp_speaker = _speaker_at(hypothesis_segments, t)

        if ref_speaker != hyp_speaker:
            error_time += step
        t += step

    return error_time / total_duration


def compute_precision_recall(
    ground_truth: List[str],
    predicted: List[str],
    similarity_threshold: float = 0.5,
) -> tuple:
    """
    Compute precision and recall for extraction tasks/decisions.
    Uses Jaccard similarity for matching (not exact string match).
    Returns (precision, recall).
    """
    if not predicted:
        return 0.0, 0.0 if ground_truth else 1.0
    if not ground_truth:
        return 0.0, 1.0

    def jaccard(a: str, b: str) -> float:
        wa = set(a.lower().split())
        wb = set(b.lower().split())
        if not wa or not wb:
            return 0.0
        return len(wa & wb) / len(wa | wb)

    tp = 0
    matched_gt = set()

    for pred in predicted:
        for gt_idx, gt in enumerate(ground_truth):
            if gt_idx not in matched_gt and jaccard(pred, gt) >= similarity_threshold:
                tp += 1
                matched_gt.add(gt_idx)
                break

    precision = tp / len(predicted)
    recall = tp / len(ground_truth)
    return precision, recall


def _speaker_at(segments: List[dict], t: float) -> Optional[str]:
    for seg in segments:
        if seg["start"] <= t <= seg["end"]:
            return seg["speaker"]
    return None
