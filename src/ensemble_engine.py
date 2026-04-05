# src/ensemble_engine.py
# Ensemble Consensus Score — combines every ML signal into a single
# 0-100 conviction score with a weighted breakdown.
#
# Weights (sum to 1.0):
#   KPI Score        30%  — fundamental + technical quality
#   XGBoost Conf     25%  — AI return-probability at 12% target
#   HMM Regime       20%  — current market environment
#   Prophet Trend    10%  — structural trend direction
#   Sentiment        10%  — news flow
#   Risk Penalty      5%  — Isolation Forest anomaly flag (downward only)

from __future__ import annotations
import math

# ── Weight table ──────────────────────────────────────────────────────────────
WEIGHTS = {
    'kpi_score':   0.30,
    'xgb_conf':    0.25,
    'regime':      0.20,
    'prophet':     0.10,
    'sentiment':   0.10,
    'risk':        0.05,
}

# Labels for the conviction score
def _conviction_label(score: float) -> tuple[str, str]:
    """Returns (label, hex_colour)."""
    if score >= 75:
        return "High Conviction Buy",  "#00FFC8"
    elif score >= 58:
        return "Moderate Buy Signal",  "#7EE8A2"
    elif score >= 42:
        return "Neutral — Watch",      "#FFD700"
    elif score >= 25:
        return "Weak Signal — Wait",   "#FFA500"
    else:
        return "Avoid",                "#FF4B4B"


# ── Signal normalisers (each returns 0-100) ───────────────────────────────────
def _normalise_kpi(total_score: float, max_score: float = 12.0) -> float:
    return min(max(total_score / max_score * 100, 0), 100)

def _normalise_xgb(conf: float) -> float:
    """XGBoost already returns 0-100."""
    return min(max(float(conf), 0), 100)

def _normalise_regime(regime_label: str) -> float:
    return {"Bull": 100.0, "Sideways": 50.0, "Bear": 10.0}.get(regime_label, 50.0)

def _normalise_prophet(trend_direction: str) -> float:
    return {"Upward": 85.0, "Flat": 50.0, "Downward": 20.0}.get(trend_direction, 50.0)

def _normalise_sentiment(sentiment_pct: float) -> float:
    """sentiment_pct is already 0-100 from FinBERT engine."""
    return min(max(float(sentiment_pct), 0), 100)

def _normalise_risk(is_anomaly: bool) -> float:
    """Anomaly = penalty (low score), normal = neutral (100)."""
    return 20.0 if is_anomaly else 100.0


# ── Public API ─────────────────────────────────────────────────────────────────
def compute_ensemble_score(
    total_kpi_score:    float,
    xgb_confidence:     float | None,
    regime_label:       str,
    prophet_trend:      str,
    sentiment_pct:      float | None,
    is_anomaly:         bool,
    xgb_available:      bool = True,
    sentiment_available: bool = True,
    prophet_available:  bool = True,
) -> dict:
    """
    Computes the weighted ensemble conviction score.

    Parameters
    ----------
    total_kpi_score     : 0-12 KPI score
    xgb_confidence      : 0-100 from run_ai_signal_analysis (None if unavailable)
    regime_label        : 'Bull' | 'Sideways' | 'Bear'
    prophet_trend       : 'Upward' | 'Flat' | 'Downward'
    sentiment_pct       : 0-100 from get_sentiment_analysis (None if unavailable)
    is_anomaly          : bool from detect_anomalies
    xgb_available       : whether XGBoost ran successfully
    sentiment_available : whether FinBERT ran successfully
    prophet_available   : whether Prophet ran successfully

    Returns
    -------
    {
        'score'        : float,   # 0-100 final weighted score
        'label'        : str,
        'color'        : str,     # hex
        'components'   : list[dict],  # per-signal breakdown for waterfall UI
        'plain_english': str,
    }
    """
    weights = WEIGHTS.copy()

    # Redistribute weights of unavailable signals to KPI (most reliable)
    if not xgb_available:
        weights['kpi_score'] += weights.pop('xgb_conf', 0)
    if not sentiment_available:
        weights['kpi_score'] += weights.pop('sentiment', 0)
    if not prophet_available:
        weights['kpi_score'] += weights.pop('prophet', 0)

    # Normalise each signal to 0-100
    signals = {
        'kpi_score': _normalise_kpi(total_kpi_score),
        'regime':    _normalise_regime(regime_label),
        'risk':      _normalise_risk(is_anomaly),
    }
    if xgb_available and xgb_confidence is not None:
        signals['xgb_conf']  = _normalise_xgb(xgb_confidence)
    if sentiment_available and sentiment_pct is not None:
        signals['sentiment'] = _normalise_sentiment(sentiment_pct)
    if prophet_available:
        signals['prophet']   = _normalise_prophet(prophet_trend)

    # Weighted sum
    total_weight = sum(weights[k] for k in signals)
    raw_score    = sum(signals[k] * weights[k] for k in signals) / total_weight
    final_score  = round(raw_score, 1)

    label, color = _conviction_label(final_score)

    # Build component list for the waterfall UI
    SIGNAL_LABELS = {
        'kpi_score':  'KPI Quality Score',
        'xgb_conf':   'AI Return Probability',
        'regime':     'Market Regime (HMM)',
        'prophet':    'Trend Direction (Prophet)',
        'sentiment':  'News Sentiment',
        'risk':       'Risk / Anomaly Check',
    }
    SIGNAL_ICONS = {
        'kpi_score':  'Fundamental + Technical',
        'xgb_conf':   'XGBoost classifier',
        'regime':     'Hidden Markov Model',
        'prophet':    'Facebook Prophet',
        'sentiment':  'FinBERT NLP',
        'risk':       'Isolation Forest',
    }

    components = []
    for key, raw_val in signals.items():
        w          = weights.get(key, 0)
        contribution = raw_val * w / total_weight
        if raw_val >= 65:
            sig_color = "#00FFC8"
        elif raw_val >= 40:
            sig_color = "#FFD700"
        else:
            sig_color = "#FF4B4B"

        components.append({
            'key':          key,
            'label':        SIGNAL_LABELS.get(key, key),
            'model':        SIGNAL_ICONS.get(key, ''),
            'raw_score':    round(raw_val, 1),
            'weight_pct':   round(w / total_weight * 100, 1),
            'contribution': round(contribution, 2),
            'color':        sig_color,
        })

    # Sort strongest contribution first
    components.sort(key=lambda x: x['contribution'], reverse=True)

    plain = _build_plain_english(final_score, label, components, regime_label,
                                  is_anomaly, prophet_trend)

    return {
        'score':      final_score,
        'label':      label,
        'color':      color,
        'components': components,
        'plain_english': plain,
    }


def _build_plain_english(score, label, components, regime, is_anomaly, trend) -> str:
    top2    = [c['label'] for c in components[:2]]
    bottom1 = components[-1]

    if score >= 75:
        opening = (
            f"The Ensemble AI gives this stock a conviction score of {score:.0f}/100 ({label}). "
            f"All major signals are aligned: strong fundamentals, a favourable market regime, "
            f"and positive AI forecasts."
        )
    elif score >= 58:
        opening = (
            f"The Ensemble AI gives this a score of {score:.0f}/100 ({label}). "
            f"The strongest signals come from {top2[0]} and {top2[1]}, "
            f"though not every indicator is fully positive."
        )
    elif score >= 42:
        opening = (
            f"The Ensemble AI scores this at {score:.0f}/100 ({label}). "
            f"The signals are mixed - some positive, some cautionary. "
            f"No strong catalyst in either direction right now."
        )
    else:
        opening = (
            f"The Ensemble AI gives this a low score of {score:.0f}/100 ({label}). "
            f"Multiple signals are pointing negatively. "
            f"The weakest area is {bottom1['label']}."
        )

    caveats = []
    if is_anomaly:
        caveats.append("unusual trading activity has been flagged")
    if regime == "Bear":
        caveats.append("the stock is in a Bear Regime which reduces confidence in upside forecasts")
    if trend == "Downward":
        caveats.append("the structural trend is pointing downward")

    caveat_str = ""
    if caveats:
        caveat_str = " Note: " + "; ".join(caveats) + "."

    return opening + caveat_str + (
        " This score is a starting point for your research, not a buy/sell recommendation."
    )
