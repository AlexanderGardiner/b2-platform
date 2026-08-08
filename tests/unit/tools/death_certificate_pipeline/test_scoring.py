from tools.death_certificate_pipeline.models import (
    AuthenticitySignal,
    Band,
    ConsistencySignal,
    DocumentSignal,
)
from tools.death_certificate_pipeline.pipeline import _stage_score
from tools.fake_image_detector.models import Escalation, ToolResult, Verdict


def _auth(risk_score: float, escalation: Escalation = Escalation.AUTO_ACCEPT) -> AuthenticitySignal:
    verdict = Verdict.PASS
    if escalation == Escalation.HUMAN_REVIEW:
        verdict = Verdict.FLAG
    elif escalation == Escalation.AUTO_REJECT:
        verdict = Verdict.REJECT

    return AuthenticitySignal(
        result=ToolResult(
            verdict=verdict,
            risk_score=risk_score,
            escalation=escalation,
            checks=[],
        )
    )


async def test_score_high_band_from_strong_stage_scores():
    result = await _stage_score(
        DocumentSignal(legible=True, document_type="death_certificate"),
        _auth(0.05),
        ConsistencySignal(consistency_score=0.9, consistency_label="high"),
    )

    assert result.score == 94
    assert result.band == Band.HIGH
    assert result.sub_scores == {"document": 1.0, "authenticity": 0.95, "consistency": 0.9}


async def test_score_medium_and_low_bands_from_weighted_scores():
    medium = await _stage_score(
        DocumentSignal(legible=True, document_type="death_certificate"),
        _auth(0.35),
        ConsistencySignal(consistency_score=0.2, consistency_label="low"),
    )
    low = await _stage_score(
        DocumentSignal(legible=False),
        _auth(0.6),
        ConsistencySignal(consistency_score=0.1, consistency_label="low"),
    )

    assert medium.score == 54
    assert medium.band == Band.MEDIUM
    assert low.score == 26
    assert low.band == Band.LOW


async def test_hard_authenticity_escalation_overrides_numeric_high_score():
    result = await _stage_score(
        DocumentSignal(legible=True, document_type="death_certificate"),
        _auth(0.05, Escalation.HUMAN_REVIEW),
        ConsistencySignal(consistency_score=0.9, consistency_label="high"),
    )

    assert result.score == 94
    assert result.band == Band.ESCALATE
    assert result.flags == ["HARD_ESCALATION"]
