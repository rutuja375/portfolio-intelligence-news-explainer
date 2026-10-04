"""Streamlit analyst interface for the synthetic end-to-end investigation."""

import streamlit as st

from portfolio_intelligence import ContextClassification, EvidenceTiming
from portfolio_intelligence.demo import build_demo_investigation


def percent(value: float) -> str:
    return f"{value:+.2%}"


st.set_page_config(
    page_title="Portfolio Intelligence",
    page_icon="📈",
    layout="wide",
)

demo = build_demo_investigation()

st.title("Portfolio Intelligence / News Explainer")
st.caption("Evidence-first investigation of unusual portfolio movements")
st.info(
    "Synthetic demonstration data — not investment advice. The interface explains "
    "associations supported by evidence; it does not establish causality."
)

overview, movement_tab, evidence_tab, explanation_tab = st.tabs(
    ["Portfolio", "Movement & context", "Evidence", "Explanation"]
)

with overview:
    st.subheader("Portfolio overview")
    first, second, third = st.columns(3)
    first.metric("Portfolio return", percent(demo.attribution.portfolio_return))
    second.metric("Largest contributor", demo.attribution.contributors_by_impact[0].ticker)
    second.caption(
        percent(demo.attribution.contributors_by_impact[0].contribution)
        + " portfolio contribution"
    )
    third.metric(
        "Investigation required",
        "Yes" if demo.event.investigation_required else "No",
    )

    st.subheader("Holding attribution")
    st.dataframe(
        [
            {
                "Holding": item.ticker,
                "Weight": percent(item.weight),
                "Return": percent(item.period_return),
                "Contribution": percent(item.contribution),
            }
            for item in demo.attribution.contributors_by_impact
        ],
        use_container_width=True,
        hide_index=True,
    )
    st.caption("Holdings are ordered by absolute contribution to the portfolio movement.")

with movement_tab:
    st.subheader(f"{demo.movement.ticker} movement signal")
    first, second, third, fourth = st.columns(4)
    first.metric("Observed return", percent(demo.movement.observed_return))
    second.metric("Historical mean", percent(demo.movement.historical_mean))
    third.metric("Historical volatility", percent(demo.movement.historical_volatility))
    fourth.metric(
        "Z-score",
        "Unavailable" if demo.movement.z_score is None else f"{demo.movement.z_score:.2f}",
    )
    st.write("**Detection reasons:**", ", ".join(demo.movement.reasons))

    st.subheader("Market context")
    context_columns = st.columns(4)
    context_columns[0].metric(demo.context.security_ticker, percent(demo.context.security_return))
    context_columns[1].metric(demo.context.market_ticker, percent(demo.context.market_return))
    context_columns[2].metric(demo.context.sector_ticker, percent(demo.context.sector_return))
    context_columns[3].metric(
        "Peer average",
        "Unavailable"
        if demo.context.peer_average_return is None
        else percent(demo.context.peer_average_return),
    )
    classification_label = {
        ContextClassification.MARKET_WIDE: "Market-wide",
        ContextClassification.SECTOR_WIDE: "Sector-wide",
        ContextClassification.COMPANY_SPECIFIC: "Potentially company-specific",
        ContextClassification.MIXED: "Mixed / inconclusive",
    }[demo.context.classification]
    st.success(f"Context classification: {classification_label}")
    st.caption("This classification describes relative movement, not proven causality.")

    st.subheader("Investigation event")
    st.code(demo.event.event_id)
    for reason in demo.event.decision_reasons:
        st.write(f"- {reason}")

with evidence_tab:
    st.subheader("Ranked evidence")
    st.caption(
        "Post-movement reporting is retained for context but receives a temporal penalty."
    )
    timing_labels = {
        EvidenceTiming.PRE_MOVEMENT: "Pre-movement",
        EvidenceTiming.DURING_MOVEMENT: "During movement",
        EvidenceTiming.POST_MOVEMENT: "Post-movement",
    }
    for position, ranked in enumerate(demo.ranked_evidence, start=1):
        with st.container(border=True):
            left, right = st.columns([4, 1])
            left.markdown(f"**{position}. {ranked.item.title}**")
            left.write(ranked.item.summary)
            left.caption(
                f"{ranked.item.source} · {ranked.item.published_at.isoformat()} · "
                f"{timing_labels[ranked.timing]}"
            )
            right.metric("Evidence score", f"{ranked.combined_score:.3f}")
            st.write("Signals:", ", ".join(ranked.ranking_reasons))

with explanation_tab:
    st.subheader("Grounded explanation")
    confidence_columns = st.columns(3)
    confidence_columns[0].metric("Evidence confidence", demo.explanation.confidence.value)
    confidence_columns[1].metric(
        "Selected evidence", len(demo.readiness.selected_evidence)
    )
    confidence_columns[2].metric(
        "Conflicting signals", "Yes" if demo.readiness.conflict_detected else "No"
    )
    st.write(demo.explanation.summary)
    for claim in demo.explanation.claims:
        st.markdown(f"- {claim.text}  ")
        st.caption("Citations: " + ", ".join(claim.citation_ids))
    st.warning(
        "Human judgment remains final. This explanation does not recommend buying, "
        "selling or holding any security."
    )
