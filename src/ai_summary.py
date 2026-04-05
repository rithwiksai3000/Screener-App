# src/ai_summary.py
# Generates a plain-English "Why this stock?" summary from KPI results.
# Rule-based — no API required, always works.

def generate_summary(ticker: str, results: dict, total_score: float, category: str) -> str:
    """
    Returns a 3-4 sentence plain English summary of the stock's KPI profile.
    """
    lines = []

    # ── Sentence 1: Overall verdict ───────────────────────────────────────────
    if total_score >= 10:
        verdict = "a strong buy candidate"
    elif total_score >= 8:
        verdict = "a solid stock worth watching"
    elif total_score >= 6:
        verdict = "a mixed picture — some strengths, some weaknesses"
    elif total_score >= 4:
        verdict = "a weak profile with limited upside signals"
    else:
        verdict = "a stock to avoid at current levels"

    lines.append(f"{ticker} scores {total_score:.1f}/12, making it {verdict}.")

    # ── Sentence 2: Fundamental highlights ───────────────────────────────────
    funda_parts = []

    eff   = results.get("Efficiency",  {})
    mar   = results.get("Margin",      {})
    rev   = results.get("RevGrowth",   {})
    solv  = results.get("Solvency",    {})
    val   = results.get("Valuation",   {})
    growth= results.get("Growth_Adj",  {})

    # Efficiency / profitability
    if eff.get("score") == 1:
        funda_parts.append(f"exceptional {eff.get('label','efficiency')} of {eff.get('formatted','')}")
    elif eff.get("score") == 0:
        funda_parts.append(f"weak {eff.get('label','efficiency')} at {eff.get('formatted','')}")

    # Margin
    if mar.get("score") == 1:
        funda_parts.append(f"strong {mar.get('label','margin')} of {mar.get('formatted','')}")
    elif mar.get("score") == 0:
        funda_parts.append(f"thin {mar.get('label','margin')} at {mar.get('formatted','')}")

    # Revenue growth
    if rev.get("score") == 1:
        funda_parts.append(f"impressive revenue growth of {rev.get('formatted','')}")
    elif rev.get("score") == 0:
        rev_val = rev.get("value", 0)
        if isinstance(rev_val, (int, float)) and rev_val < 0:
            funda_parts.append(f"declining revenue ({rev.get('formatted','')})")
        else:
            funda_parts.append(f"sluggish revenue growth of {rev.get('formatted','')}")

    # Solvency
    if solv.get("score") == 1:
        funda_parts.append(f"a clean balance sheet ({solv.get('label','')} {solv.get('formatted','')})")
    elif solv.get("score") == 0:
        funda_parts.append(f"elevated leverage ({solv.get('label','')} {solv.get('formatted','')})")

    # Valuation
    if val.get("score") == 1:
        funda_parts.append(f"attractive valuation ({val.get('label','')} {val.get('formatted','')})")
    elif val.get("score") == 0:
        funda_parts.append(f"stretched valuation ({val.get('label','')} {val.get('formatted','')})")

    if funda_parts:
        if len(funda_parts) == 1:
            funda_sentence = f"Fundamentally, the standout is {funda_parts[0]}."
        elif len(funda_parts) == 2:
            funda_sentence = f"Fundamentally, it shows {funda_parts[0]} alongside {funda_parts[1]}."
        else:
            main = ", ".join(funda_parts[:-1])
            funda_sentence = f"Fundamentally, it shows {main}, and {funda_parts[-1]}."
        lines.append(funda_sentence)

    # ── Sentence 3: Technical situation ──────────────────────────────────────
    rsi_data   = results.get("RSI",            {})
    trend_data = results.get("LongTermTrend",  {})
    gc_data    = results.get("MediumTermTrend",{})
    dip_data   = results.get("PriceStrength",  {})

    rsi_val    = rsi_data.get("value",     50)
    trend_str  = trend_data.get("formatted", "")
    gc_str     = gc_data.get("formatted",  "")
    dip_val    = dip_data.get("value",      0)

    tech_parts = []

    # Trend
    if "Bullish" in str(trend_str):
        tech_parts.append("trading above its 200-day SMA (bullish trend)")
    elif "Bearish" in str(trend_str):
        tech_parts.append("trading below its 200-day SMA (bearish trend)")

    # Golden cross
    if "Yes" in str(gc_str):
        tech_parts.append("the 50-day has crossed above the 200-day (golden cross)")
    elif "No" in str(gc_str):
        tech_parts.append("no golden cross in place")

    # RSI
    if isinstance(rsi_val, (int, float)):
        if rsi_val < 30:
            tech_parts.append(f"deeply oversold RSI of {rsi_val:.0f} — potential bounce territory")
        elif rsi_val < 40:
            tech_parts.append(f"RSI at {rsi_val:.0f}, suggesting the stock is oversold")
        elif rsi_val > 75:
            tech_parts.append(f"RSI at {rsi_val:.0f} indicating overbought conditions")
        elif rsi_val > 65:
            tech_parts.append(f"RSI at {rsi_val:.0f}, momentum is elevated")

    # Price vs 52W high
    if isinstance(dip_val, (int, float)):
        if dip_val < -25:
            tech_parts.append(f"currently {abs(dip_val):.0f}% below its 52-week high — a deep dip")
        elif dip_val < -10:
            tech_parts.append(f"{abs(dip_val):.0f}% off its 52-week high")
        elif dip_val > -5:
            tech_parts.append(f"trading near its 52-week high ({dip_val:.0f}%)")

    if tech_parts:
        tech_sentence = "Technically, " + ", and ".join(tech_parts[:3]) + "."
        lines.append(tech_sentence)

    # ── Sentence 4: Actionable takeaway ──────────────────────────────────────
    fund_score = sum(v.get("score", 0) for k, v in results.items()
                     if k in ("Efficiency","Margin","RevGrowth","Solvency","Valuation","Growth_Adj")
                     and isinstance(v, dict))
    tech_score = sum(v.get("score", 0) for k, v in results.items()
                     if k in ("RSI","LongTermTrend","MediumTermTrend","PriceStrength")
                     and isinstance(v, dict))

    is_oversold = isinstance(rsi_val, (int, float)) and rsi_val < 40
    is_dip = isinstance(dip_val, (int, float)) and dip_val < -15
    is_bullish = "Bullish" in str(trend_str)
    is_bearish = "Bearish" in str(trend_str)

    if fund_score >= 5 and is_oversold and is_dip:
        takeaway = f"The combination of strong fundamentals and technical weakness could represent a value entry point for patient investors."
    elif fund_score >= 5 and is_bullish:
        takeaway = f"Strong fundamentals aligned with a bullish trend make this a conviction candidate."
    elif fund_score >= 5 and is_bearish and is_dip:
        takeaway = f"Solid fundamentals, but the stock is technically broken — worth waiting for a trend reversal before entering."
    elif fund_score < 3 and tech_score >= 2:
        takeaway = f"The technicals look decent but the fundamentals don't support a high-conviction buy — monitor rather than act."
    elif fund_score < 3 and is_bearish:
        takeaway = f"Weak fundamentals and a bearish trend — avoid until the business shows improvement."
    elif total_score >= 9:
        takeaway = f"Overall, this is one of the stronger setups in the current universe."
    else:
        takeaway = f"No clear catalyst — hold on the watchlist until conditions improve."

    lines.append(takeaway)

    return " ".join(lines)
