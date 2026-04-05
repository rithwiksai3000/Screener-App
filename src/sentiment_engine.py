# src/sentiment_engine.py
# FinBERT-based news sentiment analysis for any ticker.
# Uses yfinance .news feed + ProsusAI/finbert model.
# First call downloads the model (~500 MB); subsequent calls use local cache.

import yfinance as yf
import numpy as np
from datetime import datetime, timezone

# Lazy-load the pipeline so it doesn't slow app startup
_pipeline = None

def _get_pipeline():
    global _pipeline
    if _pipeline is None:
        from transformers import pipeline
        _pipeline = pipeline(
            "text-classification",
            model="ProsusAI/finbert",
            tokenizer="ProsusAI/finbert",
            top_k=None,          # return all 3 label scores
            truncation=True,
            max_length=512,
        )
    return _pipeline


def get_sentiment_analysis(ticker: str, max_headlines: int = 15) -> dict:
    """
    Fetches the latest news for `ticker` via yfinance and scores each headline
    with FinBERT. Returns a structured dict for use in the UI and chatbot.

    Returns
    -------
    {
        'ticker': str,
        'headline_count': int,
        'avg_positive': float,   # 0-1
        'avg_negative': float,
        'avg_neutral':  float,
        'overall_label': str,    # 'Positive' | 'Negative' | 'Neutral'
        'overall_score': float,  # net sentiment -1 to +1
        'sentiment_pct': float,  # 0-100 gauge value
        'headlines': [
            {'title': str, 'label': str, 'score': float, 'age_hours': float}
        ],
        'error': str | None,
    }
    """
    base = {
        'ticker': ticker,
        'headline_count': 0,
        'avg_positive': 0.0,
        'avg_negative': 0.0,
        'avg_neutral':  0.0,
        'overall_label': 'Neutral',
        'overall_score': 0.0,
        'sentiment_pct': 50.0,
        'headlines': [],
        'error': None,
    }

    try:
        info  = yf.Ticker(ticker)
        news  = info.news or []
        if not news:
            base['error'] = "No news found for this ticker."
            return base

        # Extract titles and publication times
        items = []
        now   = datetime.now(tz=timezone.utc).timestamp()
        for n in news[:max_headlines]:
            content = n.get('content', {})
            # yfinance v0.2+ nests data inside 'content'
            title = (
                content.get('title') or
                n.get('title') or ''
            )
            pub_ts = (
                content.get('pubDate') or
                n.get('providerPublishTime') or
                now
            )
            # pub_ts may be a string like "2026-04-03T14:22:00Z" or a Unix int
            if isinstance(pub_ts, str):
                try:
                    pub_ts = datetime.fromisoformat(
                        pub_ts.replace('Z', '+00:00')
                    ).timestamp()
                except Exception:
                    pub_ts = now
            age_hours = (now - float(pub_ts)) / 3600
            if title:
                items.append({'title': title, 'age_hours': round(age_hours, 1)})

        if not items:
            base['error'] = "Could not parse news headlines."
            return base

        # Run FinBERT
        nlp    = _get_pipeline()
        titles = [i['title'] for i in items]
        raw    = nlp(titles)   # list of lists: [[{label,score}, ...], ...]

        scored = []
        pos_acc, neg_acc, neu_acc = [], [], []

        for item, label_scores in zip(items, raw):
            scores = {ls['label'].lower(): ls['score'] for ls in label_scores}
            p = scores.get('positive', 0.0)
            n_ = scores.get('negative', 0.0)
            nu = scores.get('neutral',  0.0)

            dominant = max(scores, key=scores.get)
            dominant_label = dominant.capitalize()
            dominant_score = scores[dominant]

            pos_acc.append(p)
            neg_acc.append(n_)
            neu_acc.append(nu)

            scored.append({
                'title':      item['title'],
                'label':      dominant_label,
                'score':      round(dominant_score, 3),
                'age_hours':  item['age_hours'],
            })

        avg_pos = float(np.mean(pos_acc))
        avg_neg = float(np.mean(neg_acc))
        avg_neu = float(np.mean(neu_acc))

        # Net score: +1 = all positive, -1 = all negative
        net = avg_pos - avg_neg

        # Map net (-1..+1) to pct (0..100) for a gauge
        sentiment_pct = round((net + 1) / 2 * 100, 1)

        if net >= 0.10:
            overall_label = "Positive"
        elif net <= -0.10:
            overall_label = "Negative"
        else:
            overall_label = "Neutral"

        return {
            'ticker':          ticker,
            'headline_count':  len(scored),
            'avg_positive':    round(avg_pos, 3),
            'avg_negative':    round(avg_neg, 3),
            'avg_neutral':     round(avg_neu, 3),
            'overall_label':   overall_label,
            'overall_score':   round(net, 3),
            'sentiment_pct':   sentiment_pct,
            'headlines':       scored,
            'error':           None,
        }

    except Exception as e:
        base['error'] = str(e)
        return base


def sentiment_to_plain_english(result: dict) -> str:
    """
    Converts the structured sentiment result into a 1-2 sentence plain-English
    summary suitable for the AI Analyst chatbot context.
    """
    if result.get('error') or result['headline_count'] == 0:
        return f"No recent news sentiment data available for {result['ticker']}."

    label  = result['overall_label']
    pct    = result['sentiment_pct']
    count  = result['headline_count']
    ticker = result['ticker']

    if label == "Positive":
        tone = f"the news flow around {ticker} is broadly positive"
        action = "This supports the bullish thesis in the near term."
    elif label == "Negative":
        tone = f"recent news around {ticker} carries a negative tone"
        action = "This adds short-term headline risk — check the news before acting."
    else:
        tone = f"recent news around {ticker} is mixed or neutral"
        action = "No strong news-driven catalyst in either direction right now."

    return (
        f"Across {count} recent headlines, {tone} "
        f"(net sentiment score: {result['overall_score']:+.2f}). {action}"
    )
