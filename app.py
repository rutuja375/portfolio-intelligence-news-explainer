"""Streamlit interface for synthetic and live portfolio investigation."""

from datetime import date, timedelta

import streamlit as st

from portfolio_intelligence import (
    ContextClassification,
    EvidenceTiming,
    PortfolioPositionInput,
    YFinanceMarketDataProvider,
    analyze_live_portfolio,
    build_live_investigation_detail,
)
from portfolio_intelligence.demo import build_demo_investigation


def percent(value: float) -> str:
    return f"{value:+.2%}"


def currency(value: float) -> str:
    return f"${value:,.2f}"


CLASSIFICATION_LABELS = {
    ContextClassification.MARKET_WIDE: "Market-wide",
    ContextClassification.SECTOR_WIDE: "Sector-wide",
    ContextClassification.COMPANY_SPECIFIC: "Potentially company-specific",
    ContextClassification.MIXED: "Mixed / inconclusive",
}


def render_synthetic_demo() -> None:
    demo = build_demo_investigation()
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

    with movement_tab:
        st.subheader(f"{demo.movement.ticker} movement signal")
        columns = st.columns(4)
        columns[0].metric("Observed return", percent(demo.movement.observed_return))
        columns[1].metric("Historical mean", percent(demo.movement.historical_mean))
        columns[2].metric(
            "Historical volatility", percent(demo.movement.historical_volatility)
        )
        columns[3].metric(
            "Z-score",
            "Unavailable"
            if demo.movement.z_score is None
            else f"{demo.movement.z_score:.2f}",
        )
        st.write("**Detection reasons:**", ", ".join(demo.movement.reasons))
        st.subheader("Market context")
        context_columns = st.columns(4)
        context_columns[0].metric(
            demo.context.security_ticker, percent(demo.context.security_return)
        )
        context_columns[1].metric(
            demo.context.market_ticker, percent(demo.context.market_return)
        )
        context_columns[2].metric(
            demo.context.sector_ticker, percent(demo.context.sector_return)
        )
        context_columns[3].metric(
            "Peer average",
            "Unavailable"
            if demo.context.peer_average_return is None
            else percent(demo.context.peer_average_return),
        )
        st.success(
            f"Context classification: {CLASSIFICATION_LABELS[demo.context.classification]}"
        )
        st.caption("This classification describes relative movement, not proven causality.")

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
        confidence_columns[0].metric(
            "Evidence confidence", demo.explanation.confidence.value
        )
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


def parse_positions(edited_rows) -> tuple[PortfolioPositionInput, ...]:
    records = edited_rows.to_dict("records") if hasattr(edited_rows, "to_dict") else edited_rows
    positions = []
    for row in records:
        ticker = str(row.get("Ticker", "")).strip()
        shares = row.get("Shares")
        if not ticker and (shares is None or shares == ""):
            continue
        positions.append(PortfolioPositionInput(ticker, float(shares)))
    return tuple(positions)


def render_live_portfolio() -> None:
    st.info(
        "Live adjusted prices are retrieved through yfinance for personal research and "
        "demonstration only. Live news and explanations are not yet enabled."
    )
    st.subheader("1. Enter portfolio holdings")
    st.caption(
        "Enter ticker and shares. Position value and portfolio weight are calculated "
        "automatically from adjusted prices."
    )
    initial_rows = [
        {"Ticker": "NVDA", "Shares": 10.0},
        {"Ticker": "MSFT", "Shares": 5.0},
        {"Ticker": "AAPL", "Shares": 8.0},
        {"Ticker": "AMZN", "Shares": 3.0},
        {"Ticker": "JPM", "Shares": 12.0},
    ]
    edited_rows = st.data_editor(
        initial_rows,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key="live_portfolio_editor",
        column_config={
            "Ticker": st.column_config.TextColumn(required=True),
            "Shares": st.column_config.NumberColumn(min_value=0.000001, required=True),
        },
    )
    lookback_days = st.selectbox("Historical lookback", (45, 60, 90, 180), index=2)

    if st.button("Run portfolio analysis", type="primary", use_container_width=True):
        try:
            positions = parse_positions(edited_rows)
            end = date.today()
            start = end - timedelta(days=lookback_days)
            with st.spinner("Retrieving adjusted prices and analyzing the portfolio..."):
                analysis = analyze_live_portfolio(
                    positions,
                    YFinanceMarketDataProvider(),
                    start,
                    end,
                )
            st.session_state["live_analysis"] = analysis
            st.session_state.pop("live_detail", None)
        except Exception as error:
            st.error(str(error))

    analysis = st.session_state.get("live_analysis")
    if analysis is None:
        return

    st.divider()
    st.subheader("2. Portfolio analysis")
    first, second, third, fourth = st.columns(4)
    first.metric("Current portfolio value", currency(analysis.current_total_value))
    second.metric("Latest portfolio return", percent(analysis.portfolio_return))
    third.metric("As of", analysis.as_of_date.isoformat())
    fourth.metric("Flagged holdings", len(analysis.investigation_candidates))
    st.caption(
        "Contribution uses prior-close portfolio weights, which is the appropriate basis "
        "for attributing the latest close-to-close return."
    )
    st.dataframe(
        [
            {
                "Ticker": item.ticker,
                "Shares": item.shares,
                "Latest price": currency(item.latest_adjusted_close),
                "Position value": currency(item.current_market_value),
                "Current weight": percent(item.current_weight),
                "Latest return": percent(item.period_return),
                "Contribution": percent(item.contribution),
                "Abnormal": "Yes" if item.movement and item.movement.is_abnormal else "No",
                "Investigate": "Yes" if item.investigation_candidate else "No",
            }
            for item in analysis.holdings_by_impact
        ],
        use_container_width=True,
        hide_index=True,
    )

    candidates = analysis.investigation_candidates
    st.subheader("3. Holdings requiring attention")
    if not candidates:
        st.success(
            "No holding crossed both the abnormal-movement and material-contribution "
            "thresholds for the latest trading date."
        )
        return

    candidate_ticker = st.selectbox(
        "Select a flagged holding",
        [item.ticker for item in candidates],
    )
    if st.button("Open selected investigation"):
        try:
            with st.spinner("Retrieving market, sector and peer context..."):
                detail = build_live_investigation_detail(
                    analysis,
                    candidate_ticker,
                    YFinanceMarketDataProvider(),
                )
            st.session_state["live_detail"] = detail
        except Exception as error:
            st.error(str(error))

    detail = st.session_state.get("live_detail")
    if detail is None or detail.holding.ticker != candidate_ticker:
        return

    st.subheader(f"4. {detail.holding.ticker} market context")
    columns = st.columns(4)
    columns[0].metric(detail.context.security_ticker, percent(detail.context.security_return))
    columns[1].metric(detail.context.market_ticker, percent(detail.context.market_return))
    columns[2].metric(detail.context.sector_ticker, percent(detail.context.sector_return))
    columns[3].metric(
        "Peer average",
        "Unavailable"
        if detail.context.peer_average_return is None
        else percent(detail.context.peer_average_return),
    )
    st.success(
        f"Context classification: {CLASSIFICATION_LABELS[detail.context.classification]}"
    )
    st.write("**Investigation event:**", detail.event.event_id)
    st.write("**Decision reasons:**", ", ".join(detail.event.decision_reasons))
    st.warning(
        "Live evidence retrieval is not connected yet. The system will not generate a "
        "news explanation until sources can be time-aligned and cited."
    )


st.set_page_config(
    page_title="Portfolio Intelligence",
    page_icon="📈",
    layout="wide",
)
st.title("Portfolio Intelligence / News Explainer")
st.caption("Evidence-first investigation of unusual portfolio movements")

mode = st.sidebar.radio(
    "Analysis mode",
    ("Live portfolio analysis", "Synthetic end-to-end demo"),
)
if mode == "Live portfolio analysis":
    render_live_portfolio()
else:
    render_synthetic_demo()
