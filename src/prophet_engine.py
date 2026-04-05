# src/prophet_engine.py
# Prophet-based time series decomposition and forecast.
# Breaks price into: trend + weekly seasonality + yearly seasonality,
# then forecasts forward with uncertainty intervals.
# Retail-friendly output: seasonal calendar, trend direction, 6M forecast.

import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings("ignore")


# ── Main public function ───────────────────────────────────────────────────────
def get_prophet_forecast(df_stock: pd.DataFrame, periods: int = 180) -> dict:
    """
    Fits a Prophet model on the stock's closing prices and returns
    a structured dict for the UI.

    Parameters
    ----------
    df_stock : DataFrame with DatetimeIndex and 'Close' column
    periods  : trading days to forecast (default 180 ~ 6 months)

    Returns
    -------
    {
        'forecast_df'    : pd.DataFrame,   # full Prophet output (ds, yhat, yhat_lower, yhat_upper)
        'future_only'    : pd.DataFrame,   # forecast rows only (no historical fit)
        'trend_direction': str,            # 'Upward' | 'Downward' | 'Flat'
        'trend_slope'    : float,          # $ per month
        'target_6m'      : float,          # median forecast price at 6 months
        'target_6m_low'  : float,          # lower bound
        'target_6m_high' : float,          # upper bound
        'last_price'     : float,
        'pct_change_6m'  : float,          # % from last_price to target_6m
        'monthly_seasonal': list[dict],    # [{month_name, avg_effect, label}]
        'best_months'    : list[str],      # top 3 seasonally strong months
        'worst_months'   : list[str],      # bottom 3 seasonally weak months
        'weekly_seasonal': list[dict],     # [{day_name, avg_effect}]
        'components_df'  : pd.DataFrame,  # full components (trend, weekly, yearly)
        'plain_english'  : str,
        'error'          : str | None,
    }
    """
    base = {
        'forecast_df':      pd.DataFrame(),
        'future_only':      pd.DataFrame(),
        'trend_direction':  'Unknown',
        'trend_slope':      0.0,
        'target_6m':        0.0,
        'target_6m_low':    0.0,
        'target_6m_high':   0.0,
        'last_price':       0.0,
        'pct_change_6m':    0.0,
        'monthly_seasonal': [],
        'best_months':      [],
        'worst_months':     [],
        'weekly_seasonal':  [],
        'components_df':    pd.DataFrame(),
        'plain_english':    'Not enough data.',
        'error':            None,
    }

    try:
        from prophet import Prophet

        if df_stock is None or len(df_stock) < 252:
            base['error'] = "Need at least 1 year of price history for Prophet."
            return base

        # ── Prepare Prophet input (needs 'ds' and 'y') ───────────────────────
        # df_stock has an integer index — use the Date column for timestamps
        tmp = df_stock[['Date', 'Close']].dropna(subset=['Close']).copy()
        df_p = pd.DataFrame({
            'ds': pd.to_datetime(tmp['Date']).dt.tz_localize(None),
            'y':  tmp['Close'].values,
        }).reset_index(drop=True)
        last_price = float(df_p['y'].iloc[-1])
        last_date  = df_p['ds'].iloc[-1]

        # ── Fit model ────────────────────────────────────────────────────────
        # Use 5 years: gives 5 observations per calendar month for reliable
        # seasonality detection. changepoint_prior_scale is kept very low (0.01)
        # so old multi-year bull/bear runs don't get extrapolated into the forecast
        # — the trend stays anchored to the current regime while seasonality
        # benefits from the fuller history.
        cutoff = df_p['ds'].max() - pd.Timedelta(days=1825)
        df_p   = df_p[df_p['ds'] >= cutoff].reset_index(drop=True)

        model = Prophet(
            daily_seasonality=False,
            weekly_seasonality=True,
            yearly_seasonality=True,
            seasonality_mode='additive',
            changepoint_prior_scale=0.01,        # very conservative — trend stays flat/gentle
            seasonality_prior_scale=10.0,        # seasonal patterns can flex freely
            interval_width=0.80,
        )
        model.fit(df_p)

        # ── Forecast ─────────────────────────────────────────────────────────
        future     = model.make_future_dataframe(periods=periods, freq='B')
        forecast   = model.predict(future)
        components = model.predict(future)     # same object; contains trend/weekly/yearly

        # Split historical fit vs pure future
        future_only = forecast[forecast['ds'] > last_date].copy()

        # 6-month target (last row of forecast)
        row_6m     = future_only.iloc[-1]
        target_6m      = float(row_6m['yhat'])
        target_6m_low  = float(row_6m['yhat_lower'])
        target_6m_high = float(row_6m['yhat_upper'])
        pct_6m     = ((target_6m - last_price) / last_price) * 100

        # ── Trend direction + slope ───────────────────────────────────────────
        trend_start = float(future_only['trend'].iloc[0])
        trend_end   = float(future_only['trend'].iloc[-1])
        slope_per_month = (trend_end - trend_start) / 6   # $/month over 6M

        if slope_per_month > last_price * 0.005:
            trend_direction = "Upward"
        elif slope_per_month < -last_price * 0.005:
            trend_direction = "Downward"
        else:
            trend_direction = "Flat"

        # ── Monthly seasonality from yearly component ─────────────────────────
        # additive mode: yearly component is in price dollars, not a multiplier.
        # Normalise by mean price to get a clean ± % effect.
        mean_price = float(df_p['y'].mean())

        season_frame = pd.DataFrame({
            'ds': pd.date_range('2024-01-01', periods=365, freq='D')
        })
        season_pred = model.predict(season_frame)

        season_pred['month'] = season_pred['ds'].dt.month
        monthly = (
            season_pred.groupby('month')['yearly']
            .mean()
            .reset_index()
        )
        month_names = ['Jan','Feb','Mar','Apr','May','Jun',
                       'Jul','Aug','Sep','Oct','Nov','Dec']
        monthly_seasonal = []
        for _, row in monthly.iterrows():
            m_idx     = int(row['month']) - 1
            effect    = float(row['yearly'])
            effect_pct = round((effect / mean_price) * 100, 2)   # $/mean → %
            label = ("Strong" if effect_pct > 0.5
                     else "Weak" if effect_pct < -0.5
                     else "Neutral")
            monthly_seasonal.append({
                'month':      month_names[m_idx],
                'month_num':  m_idx + 1,
                'avg_effect': effect_pct,
                'label':      label,
            })

        sorted_monthly = sorted(monthly_seasonal, key=lambda x: x['avg_effect'], reverse=True)
        best_months  = [m['month'] for m in sorted_monthly[:3]]
        worst_months = [m['month'] for m in sorted_monthly[-3:]]

        # ── Weekly seasonality ────────────────────────────────────────────────
        week_frame = pd.DataFrame({
            'ds': pd.date_range('2024-01-01', periods=7, freq='D')
        })
        week_pred = model.predict(week_frame)
        day_names = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun']
        weekly_seasonal = []
        for i, (_, row) in enumerate(week_pred.iterrows()):
            effect     = float(row['weekly'])
            effect_pct = round((effect / mean_price) * 100, 2)   # $/mean → %
            weekly_seasonal.append({
                'day':        day_names[row['ds'].dayofweek],
                'avg_effect': effect_pct,
            })

        plain = _build_plain_english(
            trend_direction, slope_per_month, target_6m, pct_6m,
            target_6m_low, target_6m_high, best_months, worst_months, last_price
        )

        return {
            'forecast_df':       forecast,
            'future_only':       future_only,
            'trend_direction':   trend_direction,
            'trend_slope':       round(slope_per_month, 2),
            'target_6m':         round(target_6m, 2),
            'target_6m_low':     round(target_6m_low, 2),
            'target_6m_high':    round(target_6m_high, 2),
            'last_price':        round(last_price, 2),
            'pct_change_6m':     round(pct_6m, 1),
            'monthly_seasonal':  monthly_seasonal,
            'best_months':       best_months,
            'worst_months':      worst_months,
            'weekly_seasonal':   weekly_seasonal,
            'components_df':     components,
            'plain_english':     plain,
            'error':             None,
        }

    except Exception as e:
        base['error'] = str(e)
        return base


def _build_plain_english(direction, slope, target, pct, low, high,
                          best_months, worst_months, last_price) -> str:
    if direction == "Upward":
        trend_sent = (
            f"Prophet's trend model sees a clear upward drift, adding roughly "
            f"${abs(slope):.2f} per month to the stock's underlying value."
        )
    elif direction == "Downward":
        trend_sent = (
            f"Prophet's trend model sees a downward drift, subtracting roughly "
            f"${abs(slope):.2f} per month from the stock's underlying value."
        )
    else:
        trend_sent = (
            "Prophet's trend model sees little directional drift - "
            "the stock's underlying value has been moving sideways."
        )

    forecast_sent = (
        f"Over the next 6 months, the model's central forecast is "
        f"${target:.2f} ({pct:+.1f}% from today's ${last_price:.2f}), "
        f"with an 80% probability the price lands between ${low:.2f} and ${high:.2f}."
    )

    seasonal_sent = (
        f"Historically, this stock tends to be strongest in "
        f"{', '.join(best_months[:2])} and weakest in {', '.join(worst_months[:2])}."
    )

    return f"{trend_sent} {forecast_sent} {seasonal_sent}"


# ── Chart builders ─────────────────────────────────────────────────────────────
def build_prophet_forecast_chart(prophet_result: dict) -> object:
    """
    Returns a Plotly figure showing: historical close, forecast line,
    80% uncertainty band, and a vertical 'Today' marker.
    """
    import plotly.graph_objects as go

    fc   = prophet_result['forecast_df']
    hist = fc[fc['ds'] <= pd.Timestamp.today()]
    fut  = prophet_result['future_only']

    if fc.empty:
        return go.Figure()

    fig = go.Figure()

    # Historical actual (thin line)
    fig.add_trace(go.Scatter(
        x=hist['ds'], y=hist['yhat'],
        name='Historical Fit',
        line=dict(color='#484f58', width=1),
        showlegend=True,
    ))

    # Uncertainty band (future only)
    fig.add_trace(go.Scatter(
        x=fut['ds'], y=fut['yhat_upper'],
        line=dict(width=0), showlegend=False, name='Upper'
    ))
    fig.add_trace(go.Scatter(
        x=fut['ds'], y=fut['yhat_lower'],
        fill='tonexty',
        fillcolor='rgba(0,255,200,0.12)',
        line=dict(width=0), showlegend=True, name='80% Confidence Band'
    ))

    # Central forecast (future)
    fig.add_trace(go.Scatter(
        x=fut['ds'], y=fut['yhat'],
        name='Prophet Forecast',
        line=dict(color='#00FFC8', width=2.5),
    ))

    # Today marker — add_vline triggers a Plotly annotation arithmetic bug with string x;
    # use add_shape + add_annotation separately to avoid it entirely.
    today_str = pd.Timestamp.today().strftime('%Y-%m-%d')
    fig.add_shape(
        type='line',
        x0=today_str, x1=today_str,
        y0=0, y1=1, yref='paper',
        line=dict(color='#ffffff', width=1, dash='dot'),
    )
    fig.add_annotation(
        x=today_str, y=1, yref='paper',
        text='Today', showarrow=False,
        font=dict(color='#ffffff', size=11),
        xanchor='left', bgcolor='rgba(0,0,0,0)',
    )

    fig.update_layout(
        template='plotly_dark',
        hovermode='x unified',
        height=380,
        margin=dict(t=10, b=10, l=0, r=0),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        legend=dict(orientation='h', y=1.08),
        xaxis=dict(gridcolor='#21262d'),
        yaxis=dict(gridcolor='#21262d', tickprefix='$'),
    )
    return fig


def build_seasonality_chart(monthly_seasonal: list) -> object:
    """
    Bar chart of monthly seasonal effects (% above/below trend).
    Green = strong months, red = weak months.
    """
    import plotly.graph_objects as go

    months  = [m['month']      for m in monthly_seasonal]
    effects = [m['avg_effect'] for m in monthly_seasonal]
    colors  = ['#00FFC8' if e >= 0 else '#FF4B4B' for e in effects]

    fig = go.Figure(go.Bar(
        x=months, y=effects,
        marker_color=colors,
        text=[f"{e:+.1f}%" for e in effects],
        textposition='outside',
    ))
    fig.update_layout(
        template='plotly_dark',
        height=280,
        margin=dict(t=10, b=10, l=0, r=0),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(gridcolor='#21262d'),
        yaxis=dict(gridcolor='#21262d', ticksuffix='%', title='Seasonal Effect (%)'),
        showlegend=False,
    )
    return fig


# ── Raw historical monthly analysis (all available data) ──────────────────────

MONTH_NAMES = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']

def _compute_monthly_returns(df_stock: pd.DataFrame) -> pd.DataFrame:
    """
    Computes actual month-by-month returns from all available price history.
    Returns a DataFrame with columns: year, month, return_pct.
    """
    df = df_stock[['Date', 'Close']].copy()
    df['Date']  = pd.to_datetime(df['Date'])
    df['year']  = df['Date'].dt.year
    df['month'] = df['Date'].dt.month

    agg = df.groupby(['year', 'month'])['Close'].agg(['first', 'last']).reset_index()
    agg['return_pct'] = (agg['last'] - agg['first']) / agg['first'] * 100
    return agg[['year', 'month', 'return_pct']]


def build_monthly_avg_chart(df_stock: pd.DataFrame):
    """
    Bar chart of average monthly return across all available years, with hit-rate
    (% of years the month was positive) in the hover tooltip.

    Returns (fig, best_months, worst_months, summary_list).
    """
    import plotly.graph_objects as go

    monthly = _compute_monthly_returns(df_stock)
    n_years = monthly['year'].nunique()

    summary = []
    for m in range(1, 13):
        m_data   = monthly[monthly['month'] == m]['return_pct'].dropna()
        avg      = float(m_data.mean())      if len(m_data) else 0.0
        hit_rate = float((m_data > 0).mean() * 100) if len(m_data) else 0.0
        summary.append({
            'month':      MONTH_NAMES[m - 1],
            'month_num':  m,
            'avg_return': round(avg, 2),
            'hit_rate':   round(hit_rate, 1),
            'n_obs':      len(m_data),
        })

    sorted_s     = sorted(summary, key=lambda x: x['avg_return'], reverse=True)
    best_months  = [s['month'] for s in sorted_s[:3]]
    worst_months = [s['month'] for s in sorted_s[-3:]]

    months    = [s['month']      for s in summary]
    avgs      = [s['avg_return'] for s in summary]
    hit_rates = [s['hit_rate']   for s in summary]
    colors    = ['#00FFC8' if a >= 0 else '#FF4B4B' for a in avgs]

    fig = go.Figure(go.Bar(
        x=months,
        y=avgs,
        marker_color=colors,
        text=[f"{a:+.1f}%" for a in avgs],
        textposition='outside',
        customdata=list(zip(hit_rates, [s['n_obs'] for s in summary])),
        hovertemplate=(
            '<b>%{x}</b><br>'
            'Avg return: %{y:+.2f}%<br>'
            'Positive %{customdata[0]:.0f}% of years '
            '(%{customdata[1]} observations)<extra></extra>'
        ),
    ))
    fig.update_layout(
        template='plotly_dark',
        height=300,
        margin=dict(t=30, b=10, l=0, r=0),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(gridcolor='#21262d'),
        yaxis=dict(gridcolor='#21262d', ticksuffix='%', title='Avg Return (%)'),
        showlegend=False,
        title=dict(
            text=f'Average Monthly Return — {n_years} Years of History',
            font=dict(size=13, color='#8b949e'),
            x=0,
        ),
    )
    return fig, best_months, worst_months, summary


def build_monthly_heatmap(df_stock: pd.DataFrame):
    """
    Plotly heatmap: rows = calendar years (most recent on top),
    columns = Jan–Dec, cells = actual % return for that month.
    Green = positive, red = negative.
    """
    import plotly.graph_objects as go

    monthly = _compute_monthly_returns(df_stock)
    pivot   = monthly.pivot(index='year', columns='month', values='return_pct')
    pivot.columns = MONTH_NAMES
    pivot   = pivot.sort_index(ascending=False)   # most recent year at top

    z    = pivot.values.tolist()
    x    = list(pivot.columns)
    y    = [str(yr) for yr in pivot.index]

    # Build cell text — blank for NaN (partial years)
    text = [
        [f"{v:+.1f}%" if not np.isnan(v) else "" for v in row]
        for row in pivot.values
    ]

    fig = go.Figure(go.Heatmap(
        z=z,
        x=x,
        y=y,
        text=text,
        texttemplate="%{text}",
        colorscale=[
            [0.0,  '#7f1d1d'],
            [0.35, '#FF4B4B'],
            [0.50, '#21262d'],
            [0.65, '#00FFC8'],
            [1.0,  '#064e3b'],
        ],
        zmid=0,
        zmin=-15,
        zmax=15,
        showscale=False,
        hovertemplate='<b>%{y} %{x}</b>: %{text}<extra></extra>',
    ))
    fig.update_layout(
        template='plotly_dark',
        height=max(320, len(pivot) * 24 + 60),
        margin=dict(t=10, b=10, l=55, r=10),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(side='top', gridcolor='#21262d'),
        yaxis=dict(gridcolor='#21262d'),
        font=dict(size=11),
    )
    return fig
