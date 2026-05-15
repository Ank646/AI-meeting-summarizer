"""
Layer 2 + 3 — LLM-based extraction with self-consistency.

Layer 2: LLM classification at temperature=0.0 → deterministic first pass
Layer 3: Second run at temperature=0.4 → stochastic confirmation pass
         Keep intersection of both runs (items confirmed by both)

Uses LangChain + Ollama.  Output is validated via Pydantic.
"""

import asyncio
import json
from typing import List, Optional
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from langchain_ollama import ChatOllama
from langchain.prompts import ChatPromptTemplate
from models.schemas import ExtractionResult, ExtractedTask, ExtractedDecision, ExtractedRisk
from services.extraction.heuristics import HeuristicFilter, HeuristicCandidate
from core.config import settings

logger = structlog.get_logger()


EXTRACTION_PROMPT = """\
You are a senior business analyst extracting execution intelligence from meeting transcripts.

TRANSCRIPT:
{transcript}

SPEAKER CONTEXT:
{speaker_context}

EXTRACT ONLY concrete, specific items. Do NOT extract speculative or conversational remarks.

Rules:
- TASKS: concrete actions with a clear doer (not "someone should")
- DECISIONS: final choices already made (not options being discussed)
- RISKS: active blockers, missing dependencies, timeline concerns
- TOPICS: 3-5 keywords for main subjects discussed
- Mark is_vague=true for: maybe / should / try / might / soon / at some point / someone

Return ONLY this JSON structure with no commentary:
{{
  "tasks": [
    {{"description": "...", "assignee": "...", "deadline_raw": "...", "is_vague": false, "confidence": 0.85}}
  ],
  "decisions": [
    {{"description": "...", "made_by": "...", "rationale": "...", "confidence": 0.9}}
  ],
  "risks": [
    {{"description": "...", "severity": "high", "category": "blocker", "is_blocker": true, "confidence": 0.8}}
  ],
  "topics": ["topic1", "topic2"]
}}
"""

CONSISTENCY_PROMPT = """\
You are a strict meeting analyst validating extraction results.

ORIGINAL TRANSCRIPT:
{transcript}

FIRST EXTRACTION:
{first_result}

Re-extract independently. Include only items you are confident about (confidence >= 0.65).
Reject vague commitments unless clearly assigned.

Return ONLY the same JSON structure, no commentary.
"""


class LLMExtractor:
    """
    4-layer extraction pipeline:
      L1 — heuristic pre-filter
      L2 — LLM extraction (t=0.0)
      L3 — self-consistency (t=0.4)
      L4 — confidence scoring + vague marking
    """

    def __init__(self):
        self.heuristics = HeuristicFilter()
        self._llm_det = ChatOllama(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            temperature=0.0,
            num_predict=2048,
            format="json",
        )
        self._llm_stoch = ChatOllama(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            temperature=0.4,
            num_predict=2048,
            format="json",
        )
        self._extract_prompt = ChatPromptTemplate.from_template(EXTRACTION_PROMPT)
        self._consistency_prompt = ChatPromptTemplate.from_template(CONSISTENCY_PROMPT)

    async def extract(
        self,
        transcript: str,
        speaker_context: Optional[str] = None,
    ) -> ExtractionResult:
        """Full 4-layer extraction. Returns empty result if no candidates found."""

        # L1: heuristic pre-filter
        candidates = self.heuristics.filter_candidates(transcript)
        if not candidates:
            return ExtractionResult()

        speaker_ctx = speaker_context or "Multiple speakers"

        # L2: deterministic LLM pass
        result1 = await self._llm_extract(transcript, speaker_ctx, use_stochastic=False)
        if not result1:
            return ExtractionResult()

        # L3: stochastic consistency pass
        result2 = await self._llm_extract_consistency(transcript, result1)

        # Merge results
        merged = self._intersect_results(result1, result2, candidates)

        # L4: apply confidence scoring
        merged = self._apply_confidence_scoring(merged, candidates)

        return merged

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=5),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    async def _llm_extract(
        self,
        transcript: str,
        speaker_context: str,
        use_stochastic: bool = False,
    ) -> Optional[ExtractionResult]:
        llm = self._llm_stoch if use_stochastic else self._llm_det
        chain = self._extract_prompt | llm
        loop = asyncio.get_event_loop()

        try:
            response = await loop.run_in_executor(
                None,
                lambda: chain.invoke({
                    "transcript": transcript[:4000],
                    "speaker_context": speaker_context[:500],
                })
            )
            content = response.content if hasattr(response, "content") else str(response)
            data = json.loads(content)
            return ExtractionResult(**data)
        except json.JSONDecodeError as e:
            logger.warning("LLM returned invalid JSON", error=str(e))
            raise
        except Exception as e:
            logger.warning("LLM extraction error", error=str(e))
            raise

    async def _llm_extract_consistency(
        self,
        transcript: str,
        first_result: ExtractionResult,
    ) -> Optional[ExtractionResult]:
        chain = self._consistency_prompt | self._llm_stoch
        loop = asyncio.get_event_loop()
        try:
            response = await loop.run_in_executor(
                None,
                lambda: chain.invoke({
                    "transcript": transcript[:4000],
                    "first_result": first_result.model_dump_json(),
                })
            )
            content = response.content if hasattr(response, "content") else str(response)
            data = json.loads(content)
            return ExtractionResult(**data)
        except Exception as e:
            logger.warning("Self-consistency pass failed, using first result", error=str(e))
            return first_result

    def _intersect_results(
        self,
        r1: ExtractionResult,
        r2: Optional[ExtractionResult],
        candidates: List[HeuristicCandidate],
    ) -> ExtractionResult:
        """
        Keep items confirmed by both extraction runs using Jaccard similarity.
        High-confidence items from r1 alone are kept if similarity > 0.5 is not found.
        """
        if not r2:
            return r1

        def jaccard(a: str, b: str) -> float:
            wa = set(a.lower().split())
            wb = set(b.lower().split())
            if not wa or not wb:
                return 0.0
            return len(wa & wb) / len(wa | wb)

        # Tasks
        confirmed_tasks = []
        for t1 in r1.tasks:
            matched = next(
                (t2 for t2 in r2.tasks if jaccard(t1.description, t2.description) > 0.5),
                None,
            )
            if matched:
                t1.confidence = min(1.0, (t1.confidence + matched.confidence) / 2 + 0.15)
                confirmed_tasks.append(t1)
            elif t1.confidence >= 0.65:
                confirmed_tasks.append(t1)

        # Decisions (stricter — false positives are costly)
        confirmed_decisions = []
        for d1 in r1.decisions:
            matched = next(
                (d2 for d2 in r2.decisions if jaccard(d1.description, d2.description) > 0.5),
                None,
            )
            if matched:
                d1.confidence = min(1.0, (d1.confidence + matched.confidence) / 2 + 0.15)
                confirmed_decisions.append(d1)
            elif d1.confidence >= 0.75:
                confirmed_decisions.append(d1)

        # Risks (permissive — false negatives cost more)
        confirmed_risks = [r for r in r1.risks if r.confidence >= 0.40]

        return ExtractionResult(
            tasks=confirmed_tasks,
            decisions=confirmed_decisions,
            risks=confirmed_risks,
            topics=r1.topics or r2.topics,
        )

    def _apply_confidence_scoring(
        self,
        result: ExtractionResult,
        candidates: List[HeuristicCandidate],
    ) -> ExtractionResult:
        """
        Layer 4: Weighted sigmoid confidence scoring.
        P(item|s) = sigmoid(confidence_raw * weight_factor + vague_penalty)
        """
        import math

        def sigmoid(x: float) -> float:
            return 1.0 / (1.0 + math.exp(-x))

        # Build vague sentence lookup
        vague_map = {c.sentence: c.vague_score for c in candidates}

        def vague_penalty(description: str) -> float:
            for sentence, vscore in vague_map.items():
                if description.lower()[:60] in sentence.lower():
                    return -vscore * 0.3
            return 0.0

        for task in result.tasks:
            penalty = vague_penalty(task.description)
            task.confidence = sigmoid(task.confidence * 3.0 + penalty)
            if vague_penalty(task.description) < -0.15:
                task.is_vague = True

        for decision in result.decisions:
            decision.confidence = sigmoid(decision.confidence * 3.2)

        for risk in result.risks:
            risk.confidence = sigmoid(risk.confidence * 3.0)

        return result


# Module-level singleton
llm_extractor = LLMExtractor()
