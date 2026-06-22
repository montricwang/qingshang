"""Evidence Reviewer 的正式 workflow 入口，不增加任何检索能力。"""

from app.services.allusion_evidence_reviewer import (
    build_evidence_review_prompt,
    normalize_evidence_review,
    review_allusion_candidate,
)


review_evidence = review_allusion_candidate

__all__ = [
    "build_evidence_review_prompt",
    "normalize_evidence_review",
    "review_evidence",
]
