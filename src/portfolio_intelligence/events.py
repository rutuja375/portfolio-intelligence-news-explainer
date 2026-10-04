"""Creation of validated, auditable portfolio investigation events."""

from dataclasses import dataclass
from datetime import date
from math import isclose

from .context import MovementContext
from .models import HoldingPerformance
from .movement import MovementSignal


@dataclass(frozen=True, slots=True)
class InvestigationEventConfig:
    """Thresholds controlling whether a detected move merits investigation."""

    minimum_absolute_contribution: float = 0.005
    return_tolerance: float = 1e-9

    def __post_init__(self) -> None:
        if self.minimum_absolute_contribution < 0:
            raise ValueError("Minimum absolute contribution cannot be negative")
        if self.return_tolerance <= 0:
            raise ValueError("Return tolerance must be positive")


@dataclass(frozen=True, slots=True)
class InvestigationEvent:
    """Single source record passed from analytics into the evidence pipeline."""

    event_id: str
    event_date: date
    ticker: str
    holding_performance: HoldingPerformance
    movement: MovementSignal
    context: MovementContext
    investigation_required: bool
    decision_reasons: tuple[str, ...]


def build_investigation_event(
    holding_performance: HoldingPerformance,
    movement: MovementSignal,
    context: MovementContext,
    config: InvestigationEventConfig | None = None,
) -> InvestigationEvent:
    """Combine aligned analytics into a deterministic investigation decision."""

    resolved_config = config or InvestigationEventConfig()
    holding_ticker = holding_performance.ticker.strip().upper()
    movement_ticker = movement.ticker.strip().upper()
    context_ticker = context.security_ticker.strip().upper()
    if len({holding_ticker, movement_ticker, context_ticker}) != 1:
        raise ValueError(
            "Event inputs must reference the same ticker: "
            f"holding={holding_ticker}, movement={movement_ticker}, context={context_ticker}"
        )
    if movement.date != context.date:
        raise ValueError(
            "Movement and context dates must align: "
            f"movement={movement.date.isoformat()}, context={context.date.isoformat()}"
        )

    tolerance = resolved_config.return_tolerance
    if not isclose(
        holding_performance.period_return,
        movement.observed_return,
        abs_tol=tolerance,
    ):
        raise ValueError("Holding and movement returns must align")
    if not isclose(
        movement.observed_return,
        context.security_return,
        abs_tol=tolerance,
    ):
        raise ValueError("Movement and context security returns must align")
    expected_contribution = holding_performance.weight * holding_performance.period_return
    if not isclose(
        holding_performance.contribution,
        expected_contribution,
        abs_tol=tolerance,
    ):
        raise ValueError("Holding contribution must equal weight multiplied by return")

    material_contribution = (
        abs(holding_performance.contribution)
        >= resolved_config.minimum_absolute_contribution
    )
    investigation_required = movement.is_abnormal and material_contribution
    reasons = [
        "ABNORMAL_SECURITY_MOVEMENT"
        if movement.is_abnormal
        else "MOVEMENT_NOT_ABNORMAL",
        "MATERIAL_PORTFOLIO_CONTRIBUTION"
        if material_contribution
        else "CONTRIBUTION_BELOW_THRESHOLD",
        f"CONTEXT_{context.classification.value}",
    ]

    return InvestigationEvent(
        event_id=f"{holding_ticker}-{movement.date:%Y%m%d}",
        event_date=movement.date,
        ticker=holding_ticker,
        holding_performance=holding_performance,
        movement=movement,
        context=context,
        investigation_required=investigation_required,
        decision_reasons=tuple(reasons),
    )
