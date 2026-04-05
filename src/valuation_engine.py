# src/valuation_engine.py
# Revenue-based intrinsic value calculator (P/S projection method).
# Inspired by the Buffett principle: "approximately right > precisely wrong."
#
# Method:
#   1. Start with TTM (trailing 12-month) revenue
#   2. Project it forward N years at a user-chosen growth rate
#   3. Apply a terminal P/S multiple to get a future market cap
#   4. Divide by shares outstanding → future price per share
#   5. Discount back to today using a required annual return
#   6. Apply a margin of safety → the price you should actually pay

import warnings
warnings.filterwarnings("ignore")

import yfinance as yf
import pandas as pd
import numpy as np


# ── Sector defaults ─────────────────────────────────────────────────────────
# (suggested_growth_rate, conservative_terminal_ps)
# Terminal P/S is intentionally lower than today's typical multiple —
# mature companies tend to be re-rated downward as growth slows.
SECTOR_DEFAULTS = {
    'Technology':            (0.09, 5.0),
    'Communication Services':(0.07, 4.0),
    'Healthcare':            (0.07, 3.5),
    'Consumer Discretionary':(0.06, 2.5),
    'Consumer Staples':      (0.04, 2.0),
    'Financials':            (0.05, 2.0),
    'Industrials':           (0.05, 2.0),
    'Energy':                (0.04, 1.5),
    'Materials':             (0.04, 1.5),
    'Real Estate':           (0.04, 3.0),
    'Utilities':             (0.03, 1.5),
}


# ── Data fetcher ─────────────────────────────────────────────────────────────
def get_revenue_valuation_inputs(ticker: str, df_isq: pd.DataFrame = None) -> dict:
    """
    Fetches live inputs needed for the model.

    Returns
    -------
    {
        'ttm_revenue_bn'  : float  — trailing 12M revenue in $B
        'shares_bn'       : float  — shares outstanding in billions
        'current_price'   : float
        'current_ps'      : float | None
        'sector'          : str
        'suggested_growth': float  — sector-appropriate default (e.g. 0.09)
        'suggested_ps'    : float  — conservative terminal P/S default
        'error'           : str | None
    }
    """
    try:
        t    = yf.Ticker(ticker)
        info = t.info

        # TTM Revenue — prefer summing last 4 quarters from df_isq
        # (already in $B from Migration.py safe_extract); fallback to yfinance info
        if df_isq is not None and not df_isq.empty and 'Total Revenue' in df_isq.columns:
            q_rev = df_isq['Total Revenue'].dropna().head(4)
            ttm_rev = float(q_rev.sum())                        # $B
        else:
            ttm_rev = info.get('totalRevenue', 0) / 1e9        # convert to $B

        shares_bn     = info.get('sharesOutstanding', 0) / 1e9
        current_price = float(info.get('currentPrice') or info.get('regularMarketPrice', 0))
        current_ps    = info.get('priceToSalesTrailing12Months')
        sector        = info.get('sector', 'Unknown')

        suggested_growth, suggested_ps = SECTOR_DEFAULTS.get(sector, (0.06, 3.0))

        # Conservative terminal P/S: min of sector default and 65% of current P/S
        if current_ps:
            suggested_ps = min(suggested_ps, round(current_ps * 0.65, 1))
        suggested_ps = max(1.0, round(suggested_ps, 1))

        return {
            'ttm_revenue_bn':   round(ttm_rev, 3),
            'shares_bn':        round(shares_bn, 4),
            'current_price':    round(current_price, 2),
            'current_ps':       round(current_ps, 2) if current_ps else None,
            'sector':           sector,
            'suggested_growth': suggested_growth,
            'suggested_ps':     suggested_ps,
            'error':            None,
        }

    except Exception as e:
        return {
            'ttm_revenue_bn': 0, 'shares_bn': 0, 'current_price': 0,
            'current_ps': None, 'sector': 'Unknown',
            'suggested_growth': 0.06, 'suggested_ps': 3.0,
            'error': str(e),
        }


# ── Core calculation ──────────────────────────────────────────────────────────
def calculate_revenue_intrinsic_value(
    ttm_revenue_bn:  float,
    shares_bn:       float,
    current_price:   float,
    growth_rate:     float,
    terminal_ps:     float,
    discount_rate:   float,
    margin_of_safety:float,
    years:           int = 5,
) -> dict:
    """
    Revenue-based intrinsic value model.

    Returns
    -------
    {
        'year_projections'    : list[dict]  — [{'year': 'Year 1', 'revenue_bn': x}, ...]
        'year5_revenue_bn'    : float
        'future_market_cap_bn': float
        'future_price'        : float       — per share at year N
        'present_value'       : float       — discounted to today
        'fair_buy_price'      : float       — present_value × (1 – margin_of_safety)
        'implied_return_pct'  : float       — CAGR if you buy today and sell at future_price
        'upside_to_pv_pct'    : float       — % gap: present_value vs current_price
        'upside_to_fbp_pct'   : float       — % gap: fair_buy_price vs current_price
        'verdict'             : str
        'verdict_color'       : str
        'verdict_desc'        : str
    }
    """
    year_projections = []
    for y in range(1, years + 1):
        rev = ttm_revenue_bn * ((1 + growth_rate) ** y)
        year_projections.append({'year': f'Year {y}', 'revenue_bn': round(rev, 3)})

    year5_revenue       = year_projections[-1]['revenue_bn']
    future_market_cap   = year5_revenue * terminal_ps          # $B
    future_price        = (future_market_cap / shares_bn) if shares_bn > 0 else 0
    present_value       = future_price / ((1 + discount_rate) ** years)
    fair_buy_price      = present_value * (1 - margin_of_safety)

    implied_return = (
        ((future_price / current_price) ** (1 / years) - 1)
        if current_price > 0 and future_price > 0 else 0.0
    )

    upside_to_pv  = ((present_value  - current_price) / current_price * 100) if current_price > 0 else 0
    upside_to_fbp = ((fair_buy_price - current_price) / current_price * 100) if current_price > 0 else 0

    if current_price <= fair_buy_price:
        verdict       = "In Buy Zone"
        verdict_color = "#00FFC8"
        verdict_desc  = (
            f"At ${current_price:.2f}, this stock is trading **below** the fair buy price "
            f"of ${fair_buy_price:.2f}. Based on your assumptions, this looks like an "
            f"attractive entry with a {margin_of_safety*100:.0f}% margin of safety built in."
        )
    elif current_price <= present_value:
        verdict       = "Fairly Priced"
        verdict_color = "#FFD700"
        verdict_desc  = (
            f"At ${current_price:.2f}, this stock sits between the fair buy price "
            f"(${fair_buy_price:.2f}) and the raw intrinsic value (${present_value:.2f}). "
            f"Reasonable — but there is limited margin of safety if your assumptions are wrong."
        )
    else:
        verdict       = "Overvalued"
        verdict_color = "#FF4B4B"
        verdict_desc  = (
            f"At ${current_price:.2f}, the stock is trading **above** the intrinsic value "
            f"of ${present_value:.2f} based on your assumptions. You would need the price "
            f"to fall to around ${fair_buy_price:.2f} for an attractive, margin-of-safety entry."
        )

    return {
        'year_projections':     year_projections,
        'year5_revenue_bn':     round(year5_revenue, 3),
        'future_market_cap_bn': round(future_market_cap, 3),
        'future_price':         round(future_price, 2),
        'present_value':        round(present_value, 2),
        'fair_buy_price':       round(fair_buy_price, 2),
        'implied_return_pct':   round(implied_return * 100, 1),
        'upside_to_pv_pct':     round(upside_to_pv, 1),
        'upside_to_fbp_pct':    round(upside_to_fbp, 1),
        'verdict':              verdict,
        'verdict_color':        verdict_color,
        'verdict_desc':         verdict_desc,
    }


# ── Sensitivity table ─────────────────────────────────────────────────────────
def build_sensitivity_table(
    ttm_revenue_bn:  float,
    shares_bn:       float,
    current_price:   float,
    base_growth:     float,
    terminal_ps:     float,
    discount_rate:   float,
    margin_of_safety:float,
    years:           int = 5,
) -> pd.DataFrame:
    """
    3×3 sensitivity table.
    Rows  = Bear / Base / Bull growth scenarios (base ± 3pp / +4pp)
    Cols  = Conservative / Base / Optimistic terminal P/S (base ± 1.5x)
    Cells = fair buy price at each combination.
    Color-coded separately in the UI.
    """
    growth_scenarios = [
        (f"Bear  ({max(0,base_growth-0.03)*100:.0f}% growth)", max(0.01, base_growth - 0.03)),
        (f"Base  ({base_growth*100:.0f}% growth)",             base_growth),
        (f"Bull  ({(base_growth+0.04)*100:.0f}% growth)",      base_growth + 0.04),
    ]
    ps_scenarios = [
        (f"Conservative  {max(1.0, terminal_ps-1.5):.1f}x P/S", max(1.0, terminal_ps - 1.5)),
        (f"Base  {terminal_ps:.1f}x P/S",                        terminal_ps),
        (f"Optimistic  {terminal_ps+1.5:.1f}x P/S",              terminal_ps + 1.5),
    ]

    rows = []
    for g_label, g_rate in growth_scenarios:
        row = {'Scenario': g_label}
        for ps_label, ps_val in ps_scenarios:
            result = calculate_revenue_intrinsic_value(
                ttm_revenue_bn, shares_bn, current_price,
                g_rate, ps_val, discount_rate, margin_of_safety, years
            )
            row[ps_label] = result['fair_buy_price']
        rows.append(row)

    return pd.DataFrame(rows).set_index('Scenario')
