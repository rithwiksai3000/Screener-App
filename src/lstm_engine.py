# src/lstm_engine.py
# LSTM Deep Learning Price Target.
# Architecture: 2-layer LSTM with MC Dropout for uncertainty quantification.
# Trains on the last 2 years of price history (~30 epochs, ~10s on CPU).
# MC Dropout: runs 50 stochastic forward passes to produce a confidence band.

import numpy as np
import pandas as pd
import warnings
warnings.filterwarnings("ignore")

# Suppress TF startup noise
import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'

# ── Hyperparameters ────────────────────────────────────────────────────────────
LOOKBACK      = 40      # days of history used to predict the next day
FORECAST_DAYS = 30      # days to forecast ahead
EPOCHS        = 10      # training epochs
BATCH_SIZE    = 32
MC_SAMPLES    = 10      # stochastic forward passes for uncertainty
MIN_DAYS      = LOOKBACK + 30


# ── Data preparation ───────────────────────────────────────────────────────────
def _prepare_sequences(prices: np.ndarray, lookback: int):
    """Converts a 1-D price array into (X, y) sliding-window sequences."""
    X, y = [], []
    for i in range(lookback, len(prices)):
        X.append(prices[i - lookback:i, 0])
        y.append(prices[i, 0])
    return np.array(X)[..., np.newaxis], np.array(y)   # X: (N, lookback, 1)


# ── Model builder ──────────────────────────────────────────────────────────────
def _build_model(lookback: int):
    """2-layer LSTM with dropout. Dropout stays ON during inference (MC Dropout)."""
    import tensorflow as tf
    from tensorflow.keras.models import Sequential
    from tensorflow.keras.layers import LSTM, Dense, Dropout

    model = Sequential([
        LSTM(32, return_sequences=True, input_shape=(lookback, 1)),
        Dropout(0.2),
        LSTM(16, return_sequences=False),
        Dropout(0.2),
        Dense(1),
    ])
    model.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
                  loss='mean_squared_error')
    return model


# ── MC Dropout inference ───────────────────────────────────────────────────────
def _mc_forecast(model, seed_window: np.ndarray,
                 forecast_days: int, scaler, n_samples: int = MC_SAMPLES):
    """
    Runs `n_samples` stochastic forward passes (dropout ON) to generate
    a distribution of forecast paths. Returns (median, lower_5, upper_95).
    """
    import tensorflow as tf

    all_paths = []
    for _ in range(n_samples):
        window = seed_window.copy()        # (lookback, 1)
        path   = []
        for _ in range(forecast_days):
            x_in  = window[np.newaxis, :, :]    # (1, lookback, 1)
            # training=True keeps dropout active during inference
            pred  = model(x_in, training=True).numpy()[0, 0]
            path.append(pred)
            window = np.vstack([window[1:], [[pred]]])
        all_paths.append(path)

    paths_arr = np.array(all_paths)          # (n_samples, forecast_days)
    median    = np.median(paths_arr, axis=0)
    lower     = np.percentile(paths_arr,  5, axis=0)
    upper     = np.percentile(paths_arr, 95, axis=0)

    # Inverse-transform back to real prices
    median = scaler.inverse_transform(median.reshape(-1,1)).flatten()
    lower  = scaler.inverse_transform(lower.reshape(-1,1)).flatten()
    upper  = scaler.inverse_transform(upper.reshape(-1,1)).flatten()

    return median, lower, upper


# ── Public API ─────────────────────────────────────────────────────────────────
def get_lstm_forecast(df_stock: pd.DataFrame,
                      forecast_days: int = FORECAST_DAYS) -> dict:
    """
    Trains an LSTM on the stock's closing prices and forecasts `forecast_days` ahead.

    Returns
    -------
    {
        'forecast_dates'  : pd.DatetimeIndex,
        'median_forecast' : np.ndarray,
        'lower_band'      : np.ndarray,
        'upper_band'      : np.ndarray,
        'target_30d'      : float,
        'target_30d_low'  : float,
        'target_30d_high' : float,
        'last_price'      : float,
        'pct_change_30d'  : float,
        'train_loss'      : float,
        'plain_english'   : str,
        'error'           : str | None,
    }
    """
    base = {
        'forecast_dates':   pd.DatetimeIndex([]),
        'median_forecast':  np.array([]),
        'lower_band':       np.array([]),
        'upper_band':       np.array([]),
        'target_30d':       0.0,
        'target_30d_low':   0.0,
        'target_30d_high':  0.0,
        'last_price':       0.0,
        'pct_change_30d':   0.0,
        'train_loss':       0.0,
        'plain_english':    'Not enough data.',
        'error':            None,
    }

    try:
        from sklearn.preprocessing import MinMaxScaler

        if df_stock is None or len(df_stock) < MIN_DAYS:
            base['error'] = f"Need at least {MIN_DAYS} days of price history."
            return base

        # ── Use last 2 years only ─────────────────────────────────────────────
        close = df_stock['Close'].dropna().values.astype(float)
        close = close[-252:]        # ~1 year (252 trading days)

        last_price = float(close[-1])

        # ── Normalise ─────────────────────────────────────────────────────────
        scaler = MinMaxScaler(feature_range=(0, 1))
        scaled = scaler.fit_transform(close.reshape(-1, 1))

        # ── Build sequences ───────────────────────────────────────────────────
        X, y = _prepare_sequences(scaled, LOOKBACK)
        # 85/15 train/val split
        split  = int(len(X) * 0.85)
        X_tr, X_val = X[:split], X[split:]
        y_tr, y_val = y[:split], y[split:]

        # ── Train ─────────────────────────────────────────────────────────────
        import tensorflow as tf
        tf.random.set_seed(42)
        np.random.seed(42)

        model = _build_model(LOOKBACK)

        cb_early = tf.keras.callbacks.EarlyStopping(
            monitor='val_loss', patience=3, restore_best_weights=True
        )
        history = model.fit(
            X_tr, y_tr,
            epochs=EPOCHS,
            batch_size=BATCH_SIZE,
            validation_data=(X_val, y_val),
            callbacks=[cb_early],
            verbose=0,
        )
        train_loss = float(history.history['loss'][-1])

        # ── Forecast ─────────────────────────────────────────────────────────
        seed_window = scaled[-LOOKBACK:]        # last 60 normalised prices
        median, lower, upper = _mc_forecast(
            model, seed_window, forecast_days, scaler
        )

        # ── Forecast dates (business days) ───────────────────────────────────
        # df_stock has integer index — use the Date column for the last date
        last_date = pd.to_datetime(df_stock['Date'].iloc[-1]).tz_localize(None)
        forecast_dates = pd.date_range(
            start=last_date + pd.tseries.offsets.BDay(1),
            periods=forecast_days,
            freq='B',
        )

        target_30d     = float(median[-1])
        target_30d_low = float(lower[-1])
        target_30d_high= float(upper[-1])
        pct_30d        = ((target_30d - last_price) / last_price) * 100

        plain = _build_plain_english(
            target_30d, pct_30d, target_30d_low, target_30d_high,
            last_price, train_loss, forecast_days
        )

        return {
            'forecast_dates':   forecast_dates,
            'median_forecast':  median,
            'lower_band':       lower,
            'upper_band':       upper,
            'target_30d':       round(target_30d, 2),
            'target_30d_low':   round(target_30d_low, 2),
            'target_30d_high':  round(target_30d_high, 2),
            'last_price':       round(last_price, 2),
            'pct_change_30d':   round(pct_30d, 1),
            'train_loss':       round(train_loss, 6),
            'plain_english':    plain,
            'error':            None,
        }

    except Exception as e:
        base['error'] = str(e)
        return base


def _build_plain_english(target, pct, low, high, last_price, loss, days) -> str:
    if pct >= 8:
        direction = f"meaningful upside -rising to ${target:.2f} ({pct:+.1f}%)"
        tone = "a bullish short-term signal"
    elif pct >= 2:
        direction = f"modest gains -reaching ${target:.2f} ({pct:+.1f}%)"
        tone = "a cautiously positive signal"
    elif pct >= -2:
        direction = f"roughly flat movement around ${target:.2f} ({pct:+.1f}%)"
        tone = "a neutral short-term signal"
    elif pct >= -8:
        direction = f"a mild pullback to ${target:.2f} ({pct:+.1f}%)"
        tone = "a mildly cautionary signal"
    else:
        direction = f"a significant decline to ${target:.2f} ({pct:+.1f}%)"
        tone = "a bearish short-term signal"

    return (
        f"The LSTM deep learning model -which studied every price sequence in the last 2 years -"
        f"predicts {direction} over the next {days} trading days from today's ${last_price:.2f}. "
        f"With 90% confidence, the price should land between ${low:.2f} and ${high:.2f}. "
        f"This is {tone}. Note: the model learns patterns from history and cannot anticipate "
        f"earnings surprises, news events, or sudden macro shifts."
    )


# ── Chart builder ──────────────────────────────────────────────────────────────
def build_lstm_chart(df_stock: pd.DataFrame, lstm_result: dict) -> object:
    """
    Plotly chart: last 90 days of actual price + LSTM 30-day forecast
    with 90% MC Dropout confidence band.
    """
    import plotly.graph_objects as go

    if lstm_result.get('error') or len(lstm_result['median_forecast']) == 0:
        return go.Figure()

    hist     = df_stock[['Date', 'Close']].dropna(subset=['Close']).tail(90)
    hist_idx = pd.to_datetime(hist['Date']).dt.tz_localize(None)
    hist_prices = hist['Close'].values

    f_dates  = lstm_result['forecast_dates']
    median   = lstm_result['median_forecast']
    lower    = lstm_result['lower_band']
    upper    = lstm_result['upper_band']
    last_p   = lstm_result['last_price']

    fig = go.Figure()

    # ── Historical close ──────────────────────────────────────────────────────
    fig.add_trace(go.Scatter(
        x=hist_idx, y=hist_prices,
        name='Actual Price',
        line=dict(color='#c9d1d9', width=2),
    ))

    # ── Bridge dot (connect actual to forecast) ───────────────────────────────
    fig.add_trace(go.Scatter(
        x=[hist_idx.iloc[-1], f_dates[0]],
        y=[last_p, float(median[0])],
        mode='lines',
        line=dict(color='#A78BFA', width=1, dash='dot'),
        showlegend=False,
    ))

    # ── 90% confidence band ───────────────────────────────────────────────────
    fig.add_trace(go.Scatter(
        x=f_dates, y=upper,
        line=dict(width=0), showlegend=False, name='Upper 95%'
    ))
    fig.add_trace(go.Scatter(
        x=f_dates, y=lower,
        fill='tonexty',
        fillcolor='rgba(167,139,250,0.15)',
        line=dict(width=0),
        name='90% Confidence Band',
        showlegend=True,
    ))

    # ── Median forecast ───────────────────────────────────────────────────────
    fig.add_trace(go.Scatter(
        x=f_dates, y=median,
        name='LSTM Forecast (median)',
        line=dict(color='#A78BFA', width=2.5),
    ))

    # ── Today marker ─────────────────────────────────────────────────────────
    today_str = pd.Timestamp.today().strftime('%Y-%m-%d')
    fig.add_shape(
        type='line', x0=today_str, x1=today_str,
        y0=0, y1=1, yref='paper',
        line=dict(color='#ffffff', width=1, dash='dot'),
    )
    fig.add_annotation(
        x=today_str, y=0.97, yref='paper',
        text='Today', showarrow=False,
        font=dict(color='#ffffff', size=11),
        xanchor='left',
    )

    # ── 30D target annotation ─────────────────────────────────────────────────
    target_str = f_dates[-1].strftime('%Y-%m-%d')
    pct = lstm_result['pct_change_30d']
    t_color = '#00FFC8' if pct >= 0 else '#FF4B4B'
    fig.add_annotation(
        x=target_str, y=float(median[-1]),
        text=f"  ${lstm_result['target_30d']:.2f} ({pct:+.1f}%)",
        showarrow=False,
        font=dict(color=t_color, size=12),
        xanchor='left',
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
