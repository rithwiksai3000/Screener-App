# src/regime_engine.py
# Hidden Markov Model - Market Regime Detection.
# Classifies each trading day into Bull / Bear / Sideways regime
# based on return + volatility patterns learned from the full price history.

import numpy as np
import pandas as pd
from hmmlearn.hmm import GaussianHMM
import warnings
warnings.filterwarnings("ignore")


# ── Constants ─────────────────────────────────────────────────────────────────
N_STATES        = 3          # Bull / Sideways / Bear
MIN_DAYS        = 120        # minimum history needed
VOL_WINDOW      = 10         # rolling vol window for features
RANDOM_STATE    = 42


# ── Core fitting function ──────────────────────────────────────────────────────
def _fit_hmm(returns: np.ndarray, vols: np.ndarray) -> GaussianHMM:
    """Fits a 3-state Gaussian HMM on [return, vol] feature pairs."""
    X = np.column_stack([returns, vols])
    model = GaussianHMM(
        n_components=N_STATES,
        covariance_type="full",
        n_iter=200,
        random_state=RANDOM_STATE,
        tol=1e-4,
    )
    model.fit(X)
    return model


def _label_states(model: GaussianHMM) -> dict:
    """
    Maps HMM state indices to regime names by ranking the mean daily return
    of each state: highest = Bull, lowest = Bear, middle = Sideways.
    """
    means = model.means_[:, 0]          # mean return of each state
    order = np.argsort(means)           # [bear_idx, sideways_idx, bull_idx]
    return {
        order[2]: "Bull",
        order[1]: "Sideways",
        order[0]: "Bear",
    }


# ── Public API ─────────────────────────────────────────────────────────────────
def get_regime_analysis(df_stock: pd.DataFrame) -> dict:
    """
    Runs the HMM on `df_stock` (must have a 'Close' column).

    Returns
    -------
    {
        'current_regime':   str,           # 'Bull' | 'Bear' | 'Sideways'
        'regime_color':     str,           # hex colour for UI
        'regime_since':     str,           # date the current streak started
        'streak_days':      int,           # trading days in current regime
        'confidence':       float,         # HMM posterior prob of current state (0-1)
        'regime_series':    pd.Series,     # full history of labelled regimes (DatetimeIndex)
        'state_stats':      list[dict],    # per-regime summary stats
        'plain_english':    str,
        'error':            str | None,
    }
    """
    base = {
        'current_regime': 'Unknown',
        'regime_color':   '#8b949e',
        'regime_since':   'N/A',
        'streak_days':    0,
        'confidence':     0.0,
        'regime_series':  pd.Series(dtype=str),
        'state_stats':    [],
        'plain_english':  'Not enough data to detect regime.',
        'error':          None,
    }

    try:
        if df_stock is None or len(df_stock) < MIN_DAYS:
            base['error'] = f"Need at least {MIN_DAYS} days of price history."
            return base

        # Use Date column as index so downstream .strftime() and chart x-axes work
        tmp   = df_stock[['Date', 'Close']].dropna(subset=['Close']).copy()
        tmp.index = pd.to_datetime(tmp['Date']).dt.tz_localize(None)
        close   = tmp['Close']
        returns = close.pct_change().dropna()
        vols    = returns.rolling(VOL_WINDOW).std().dropna()

        # Align - both series must start at the same point after dropna
        returns = returns.loc[vols.index]

        model      = _fit_hmm(returns.values, vols.values)
        state_seq  = model.predict(np.column_stack([returns.values, vols.values]))
        posteriors = model.predict_proba(np.column_stack([returns.values, vols.values]))
        label_map  = _label_states(model)

        # Build labelled series
        regime_series = pd.Series(
            [label_map[s] for s in state_seq],
            index=returns.index,
        )

        # Current regime
        current_state     = state_seq[-1]
        current_regime    = label_map[current_state]
        current_confidence = float(posteriors[-1, current_state])

        # Streak - how long have we been in the current regime?
        reversed_states = regime_series.iloc[::-1]
        streak = int((reversed_states == current_regime).cumprod().sum())
        regime_since = regime_series.index[-streak].strftime("%b %d, %Y") if streak > 0 else "N/A"

        # Colour map
        color_map = {"Bull": "#00FFC8", "Bear": "#FF4B4B", "Sideways": "#FFD700"}
        regime_color = color_map.get(current_regime, "#8b949e")

        # Per-state stats (for the UI table)
        state_stats = []
        for state_idx, name in label_map.items():
            mask   = regime_series == name
            r_vals = returns.loc[mask]
            v_vals = vols.loc[mask]
            state_stats.append({
                'regime':       name,
                'color':        color_map[name],
                'days':         int(mask.sum()),
                'avg_return':   round(float(r_vals.mean()) * 100, 3),   # % per day
                'avg_vol':      round(float(v_vals.mean()) * 100, 3),   # % per day
                'pct_of_time':  round(float(mask.mean()) * 100, 1),
            })
        state_stats.sort(key=lambda x: ["Bull","Sideways","Bear"].index(x['regime']))

        plain = _build_plain_english(
            current_regime, streak, regime_since, current_confidence, state_stats
        )

        return {
            'current_regime':  current_regime,
            'regime_color':    regime_color,
            'regime_since':    regime_since,
            'streak_days':     streak,
            'confidence':      round(current_confidence, 3),
            'regime_series':   regime_series,
            'state_stats':     state_stats,
            'plain_english':   plain,
            'error':           None,
        }

    except Exception as e:
        base['error'] = str(e)
        return base


def _build_plain_english(regime, streak, since, confidence, state_stats) -> str:
    """Converts regime data into a plain-English 2-sentence summary."""
    conf_word = "high" if confidence >= 0.75 else "moderate" if confidence >= 0.50 else "low"

    if regime == "Bull":
        sent1 = (
            f"The AI has identified a Bull Regime - the stock is in a period of "
            f"above-average returns and controlled volatility, a historically favourable "
            f"environment for buyers."
        )
        implication = (
            "The XGBoost confidence scores and price forecasts above carry more weight "
            "in a Bull Regime. Momentum strategies tend to work better here."
        )
    elif regime == "Bear":
        sent1 = (
            f"The AI has identified a Bear Regime - the stock is in a period of "
            f"below-average or negative returns with elevated volatility. "
            f"This is a higher-risk environment."
        )
        implication = (
            "The AI's positive forecasts should be treated with more caution in a Bear Regime. "
            "Consider waiting for a regime shift before entering a new position."
        )
    else:
        sent1 = (
            f"The AI has identified a Sideways Regime - the stock is drifting without a "
            f"clear directional trend, with moderate volatility. Neither bulls nor bears "
            f"have clear control."
        )
        implication = (
            "Price forecasts in a Sideways Regime are less reliable. "
            "Wait for a regime break into Bull before acting on buy signals."
        )

    streak_str = f"{streak} trading day{'s' if streak != 1 else ''}"
    return (
        f"{sent1} "
        f"This regime has persisted for {streak_str} (since {since}), "
        f"with {conf_word} model confidence ({confidence*100:.0f}%). "
        f"{implication}"
    )


def build_regime_chart(df_stock: pd.DataFrame, regime_series: pd.Series) -> object:
    """
    Returns a Plotly figure: candlestick price chart with coloured regime
    background bands (Bull=green, Bear=red, Sideways=yellow).
    """
    import plotly.graph_objects as go

    # Use Date column as x-axis so charts show real dates
    tmp_chart = df_stock.tail(252).copy()
    tmp_chart.index = pd.to_datetime(tmp_chart['Date']).dt.tz_localize(None)
    chart_data = tmp_chart
    fig = go.Figure()

    # ── Regime background bands ──────────────────────────────────────────────
    color_map   = {"Bull": "rgba(0,255,200,0.08)", "Bear": "rgba(255,75,75,0.08)", "Sideways": "rgba(255,215,0,0.06)"}
    reg_aligned = regime_series.reindex(chart_data.index, method='ffill').dropna()

    if not reg_aligned.empty:
        changes = reg_aligned[reg_aligned != reg_aligned.shift()]
        block_starts  = list(changes.index)
        block_regimes = list(changes.values)
        block_ends    = block_starts[1:] + [reg_aligned.index[-1]]

        for start, end, reg in zip(block_starts, block_ends, block_regimes):
            fig.add_vrect(
                x0=start.strftime('%Y-%m-%d'), x1=end.strftime('%Y-%m-%d'),
                fillcolor=color_map.get(reg, "rgba(0,0,0,0)"),
                layer="below", line_width=0,
            )

    # ── Candlestick ───────────────────────────────────────────────────────────
    fig.add_trace(go.Candlestick(
        x=chart_data.index,
        open=chart_data['Open'], high=chart_data['High'],
        low=chart_data['Low'],  close=chart_data['Close'],
        name="Price",
        increasing_line_color='#00FFC8',
        decreasing_line_color='#FF4B4B',
    ))

    # SMAs if available
    if 'SMA_50' in chart_data.columns:
        fig.add_trace(go.Scatter(
            x=chart_data.index, y=chart_data['SMA_50'],
            line=dict(color='#FFA500', width=1.5), name="50-Day Avg"
        ))
    if 'SMA_200' in chart_data.columns:
        fig.add_trace(go.Scatter(
            x=chart_data.index, y=chart_data['SMA_200'],
            line=dict(color='#FF00FF', width=1.5, dash='dot'), name="200-Day Avg"
        ))

    fig.update_layout(
        template="plotly_dark",
        xaxis_rangeslider_visible=False,
        hovermode="x unified",
        height=420,
        margin=dict(t=10, b=10, l=0, r=0),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        legend=dict(orientation="h", y=1.05),
    )
    return fig
