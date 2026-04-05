import pandas as pd
import numpy as np
import os

from src.kpis import compute_fundamentals, compute_technicals
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split
from sqlalchemy import create_engine
from sklearn.ensemble import IsolationForest



# Helper function for Fair value Engine
def get_trend_analysis(df_historical):
    """
    Phase 4: Calculates if the stock is in a Technical 'Buy' or 'Wait' zone.
    """
    latest = df_historical.tail(1).iloc[0]
    
    # Calculate 50-day and 200-day SMA
    sma50 = df_historical['Close'].rolling(window=50).mean().iloc[-1]
    sma200 = df_historical['Close'].rolling(window=200).mean().iloc[-1]
    
    # Calculate % distance from 52-week high
    high_52w = df_historical['High'].rolling(window=252).max().iloc[-1]
    dist_from_high = ((latest['Close'] - high_52w) / high_52w) * 100
    
    return {
        "sma50": round(sma50, 2),
        "sma200": round(sma200, 2),
        "dist_high": round(dist_from_high, 1),
        "is_bullish": latest['Close'] > sma200
    }




# 1 : The drift : Monte Carlo Simulation : Bull / Bear / Base Case : 10% / 12% / 15% : 1,000 simulations : 252 trading days


# 1. Define the path to your data folder
# Using 'os.path' makes sure it works correctly on Windows
BASE_PATH = r"C:\Users\rithw\Screener"
DATA_PATH = os.path.join(BASE_PATH, "data")
# A
def load_stock_data(ticker):
    """
    Finds the CSV file for a specific ticker and loads it into a Pandas DataFrame.
    """
    file_name = f"{ticker}_historical_prices.csv" # Adjust if your naming is different
    full_path = os.path.join(DATA_PATH, file_name)
    
    if os.path.exists(full_path):
        # Load the data and make 'Date' the index so the math knows time order
        df = pd.read_csv(full_path)
        df['Date'] = pd.to_datetime(df['Date'],utc=True) # Ensure 'Date' is in datetime format
        df.set_index('Date', inplace=True)
        return df
    else:
        print(f"Error: Could not find file at {full_path}")
        return None
    
    
# B
def calculate_price_metrics(df):
    """
    Calculates the 'Heartbeat' of the stock: Daily Returns and Volatility.
    """
    # We use 'Close' since you mentioned that's your column name
    # .pct_change() calculates the % move from one day to the next
    df['Daily_Return'] = df['Close'].pct_change()
    
    # Calculate Average Daily Return (Drift) and Standard Deviation (Volatility)
    # We drop the first row because it will be 'NaN' (no previous day to compare to)
    avg_daily_return = df['Daily_Return'].mean()
    daily_volatility = df['Daily_Return'].std()
    
    # We also calculate the 'Annualized' versions (standard for finance)
    # There are roughly 252 trading days in a year
    annual_return = avg_daily_return * 252
    annual_volatility = daily_volatility * np.sqrt(252)
    
    return avg_daily_return, daily_volatility, annual_return, annual_volatility



# C
def run_simulation(start_price, drift, volatility, days=252, iterations=1000):
    """
    Runs 1,000 random price paths. This version uses list-collection 
    to prevent DataFrame fragmentation warnings.
    """
    daily_drift = drift / 252
    daily_vol = volatility / np.sqrt(252)
    
    # Instead of an empty DataFrame, we use a list to collect results
    all_paths = []
    
    for i in range(iterations):
        price_series = [start_price]
        
        for d in range(days):
            shock = np.random.normal() * daily_vol
            price_today = price_series[-1]
            price_tomorrow = price_today * np.exp(daily_drift + shock)
            price_series.append(price_tomorrow)
        
        # Add this path to our list
        all_paths.append(price_series)
    
    # Join all paths at once at the very end (Very fast!)
    simulation_df = pd.DataFrame(all_paths).transpose()
        
    return simulation_df

# D
def get_scenario_results(df, bear_rate=0.10, base_rate=0.12, bull_rate=0.15):
    """
    Runs simulations for all 3 cases and returns the final average paths.
    """
    last_price = df['Close'].iloc[-1]
    # We use the historical volatility we calculated in Step B
    _, vol, _, _ = calculate_price_metrics(df)
    
    # Run the 3 different "Future Worlds"
    bear_sim = run_simulation(last_price, bear_rate, vol)
    base_sim = run_simulation(last_price, base_rate, vol)
    bull_sim = run_simulation(last_price, bull_rate, vol)
    
    # Calculate the average (mean) path for each scenario to plot on a chart
    results = pd.DataFrame({
        'Bear_Case': bear_sim.mean(axis=1),
        'Base_Case': base_sim.mean(axis=1),
        'Bull_Case': bull_sim.mean(axis=1)
    })
    
    return results




# Trend Prediction  for Technical Momentum

def get_adaptive_forecasts(df_stock, iterations=1000):
    """
    Calculates 4-horizon forecasts using Log-Normal stability and
    Jensen's Inequality adjustment to prevent 'Exponential Collapse'.
    """
    # 1. Drift: 40% long-term (5y) + 60% recent (1y) so a current downtrend
    #    actually pulls the forecast down rather than being masked by older gains.
    history_5y  = df_stock.tail(1260)   # ~5 trading years
    history_1y  = df_stock.tail(252)    # ~1 trading year
    log_5y = np.log(history_5y['Close'] / history_5y['Close'].shift(1)).dropna()
    log_1y = np.log(history_1y['Close'] / history_1y['Close'].shift(1)).dropna()

    mu    = 0.4 * log_5y.mean() + 0.6 * log_1y.mean()   # trend-aware blended drift
    sigma = log_1y.std()                                  # recent daily volatility

    # Cap sigma at 3.5% daily (~55% annualised) so high-vol stocks don't produce
    # bands that explode beyond any realistic price range.
    sigma = min(sigma, 0.035)

    last_price = float(df_stock['Close'].iloc[-1])

    # Cap annualised drift to ±25% — wide enough for fast-movers, tight enough
    # to block fantasy forecasts from outlier years.
    annual_drift = mu * 252
    annual_drift = max(-0.25, min(0.25, annual_drift))
    mu = annual_drift / 252

    # 3. Apply Jensen's Inequality Adjustment: (mu - 0.5 * sigma^2)
    drift = mu - (0.5 * sigma**2)

    # 4. Run a 365-day simulation matrix
    days = 365
    simulation_matrix = np.zeros((days, iterations))
    simulation_matrix[0] = last_price

    for t in range(1, days):
        # Generate random shocks for all 1,000 paths at once (Vectorized)
        random_shocks = np.random.normal(0, 1, iterations)
        # Standard GBM Formula: P_t = P_{t-1} * exp(drift + sigma * shock)
        simulation_matrix[t] = simulation_matrix[t-1] * np.exp(drift + (sigma * random_shocks))

    # 5. Extract 90, 180, 270, 365 day boundaries
    #    Use 20th/80th percentiles for the "Likely hi-low" band — a 60% confidence
    #    interval. The old 5th/95th bands were extreme tails, not "likely" outcomes,
    #    and produced 50%+ upside on downtrending stocks purely from log-normal spread.
    sim_df = pd.DataFrame(simulation_matrix)
    horizons = [90, 180, 270, 365]
    final_outputs = []

    for h in horizons:
        slice_df = sim_df.iloc[:h]
        upper = slice_df.quantile(0.80, axis=1)
        median = slice_df.quantile(0.50, axis=1)
        lower = slice_df.quantile(0.20, axis=1)
        final_outputs.append((upper, median, lower))

    return final_outputs



if __name__ == "__main__":
    # 1. Load your actual data (Update the ticker to one you have)
    test_ticker = "AMZN" 
    df_raw = load_stock_data(test_ticker)
    
    if df_raw is not None:
        # 2. Generate the 3 scenario paths (10%, 12%, 15%)
        # This calls our 'Manager' function from Block 2
        scenario_results = get_scenario_results(df_raw)
        
        # 3. Print the results to verify the math
        print(f"\n--- Scenario Forecast for {test_ticker} (Next 252 Days) ---")
        print(f"Starting Price: ${df_raw['Close'].iloc[-1]:.2f}")
        print("-" * 45)
        
        # We look at the very last row (Day 252) to see where the price ended
        final_day = scenario_results.iloc[-1]
        print(f"BEAR CASE (10%) Ending Price: ${final_day['Bear_Case']:.2f}")
        print(f"BASE CASE (12%) Ending Price: ${final_day['Base_Case']:.2f}")
        print(f"BULL CASE (15%) Ending Price: ${final_day['Bull_Case']:.2f}")
        print("-" * 45)
        print("Verification Successful: 1,000 simulations complete.")
        
        






        
# 2 XG Boost Model for predicting confidence of the KPI scores and Output
def build_feature_matrix(ticker, category, df_historical):
    """
    Step A: Merges your 10-point logic into a full historical timeline.
    """
    # 1. Get the 6 Fundamental DNA points (KPIs 1-6)
    f = compute_fundamentals(ticker, category)
    
    # 2. Prepare the Technical Timeline (KPIs 7-10)
    # We calculate these for the entire history, not just 'today'
    df = df_historical.copy()
    df['SMA_200'] = df['Close'].rolling(200).mean()
    df['SMA_50'] = df['Close'].rolling(50).mean()
    
    # RSI Calculation for the whole history
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['RSI_History'] = 100 - (100 / (1 + (gain / loss)))

    # 3. Combine everything into one "Learning Table"
    features = pd.DataFrame(index=df.index)
    # Fundamentals (KPIs 1-8) - Applied as constants to the history
    features['efficiency'] = f['Efficiency']['value']
    features['margin']     = f['Margin']['value']
    features['rev_growth'] = f['RevGrowth']['value']
    features['solvency']   = f['Solvency']['value']
    features['valuation']  = f['Valuation']['value']
    features['peg_ratio']  = f['Growth_Adj']['value']
    features['roce']       = f.get('ROCE', {}).get('value', 0)
    features['roic']       = f.get('ROIC', {}).get('value', 0)

    # Technicals (KPIs 9-12) - These change daily
    features['rsi']           = df['RSI_History']
    features['above_sma200']  = (df['Close'] > df['SMA_200']).astype(int)
    features['golden_cross']  = (df['SMA_50'] > df['SMA_200']).astype(int)
    features['dist_52w_high'] = (df['Close'] / df['High'].rolling(252).max()) - 1

    return features.dropna()

# Creates the target variables XG Boost tries to predict
def create_target_labels(df_historical, horizon_days=252, target_return=0.15):
    """ Updated to calculate labels based on the specific scenario target """
    future_price = df_historical['Close'].shift(-horizon_days)
    price_change = (future_price - df_historical['Close']) / df_historical['Close']
    
    # Marks a 1 if the stock hit the specific target for that gauge
    labels = (price_change >= target_return).astype(int)
    return labels


# The XGB Training Function
def train_signal_model(final_data):
    """
    Step C: Trains the XGBoost model to recognize 'Win' patterns.
    """
    # 1. Separate Features (X) from the Answer Key (y)
    X = final_data.drop(columns=['Target'])
    y = final_data['Target']
    
    # 2. Split data: 80% for learning, 20% for testing the AI's accuracy
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # 3. Initialize and Train the Model
    # 3. Initialize and Train the Model (Optimized for 4-year dataset)
    model = XGBClassifier(
        n_estimators=50,    # Reduced from 100 to prevent overfitting
        learning_rate=0.05, # Smaller steps for better learning on small data
        max_depth=3,        # Shallower trees because we have fewer data points
        random_state=42
    )
    model.fit(X_train, y_train)
    
    # 4. Check accuracy
    accuracy = model.score(X_test, y_test)
    print(f"[OK] Model Trained! Validation Accuracy: {accuracy:.2%}")
    
    return model


# Prediction Function

def predict_success_probability(model, current_features):
    """
    Step D: Asks the AI for the % chance of hitting the +15% target.
    """
    # model.predict_proba returns [chance of 0, chance of 1]
    # We want the 'chance of 1' (The Bull Case)
    probs = model.predict_proba(current_features)
    bull_probability = probs[0][1] * 100 
    
    return round(bull_probability, 1)



def run_ai_signal_analysis(ticker, category, df_historical, target_return=0.15):
    """ Updated to accept target_return for multi-gauge support """
    features = build_feature_matrix(ticker, category, df_historical)
    
    # We pass the target (15%, 12%, or 10%) into the labeling logic
    labels = create_target_labels(df_historical, target_return=target_return)
    
    train_df = align_features_and_labels(features, labels)
    model = train_signal_model(train_df)
    
    latest_vitals = features.tail(1)
    confidence = predict_success_probability(model, latest_vitals)
    
    return confidence, model
























# Ensures features and labels line up perfectly by date for XGBoost training

def align_features_and_labels(feature_df, label_series):
    """
    Ensures we don't have 'missing' data rows before we feed them to XGBoost.
    """
    # Combine them into one table
    combined = feature_df.copy()
    combined['Target'] = label_series
    
    # Drop rows where we don't have future data yet (the most recent 60 days)
    final_data = combined.dropna()
    
    return final_data




# Feature Importance Extraction for Explainability
def get_feature_importance_data(model, feature_columns):
    """
    Standalone helper: Extracts importance without touching your training logic.
    """
    # 1. Get raw scores from the trained XGBoost model
    importances = model.get_booster().get_score(importance_type='weight')
    
    # 2. Map internal names (f0, f1...) to your 10 KPI names
    feature_map = {f'f{i}': col for i, col in enumerate(feature_columns)}
    
    # 3. Create a clean dictionary of { 'KPI Name': Score }
    importance_dict = {feature_map.get(k, k): v for k, v in importances.items()}
    
    # 4. Sort it so the most influential KPI is at the top
    return dict(sorted(importance_dict.items(), key=lambda item: item[1], reverse=True))









# Phase 3 : Fair Value Engine
from sklearn.ensemble import RandomForestRegressor

def calculate_fair_value(df_funda, df_historical):
    """
    Phase 3: Predicts the 'Fair Price' based on 4 years of Financials.
    """
    # 1. Align the Financial Dates with the Stock Prices
    df_historical['date'] = df_historical.index
    data = pd.merge(df_funda, df_historical[['date', 'Close']], on='date')
    
    # 2. Features: Margin, Debt-to-Equity, and Equity (Book Value)
    X = data[['net_margin', 'debt_to_equity', 'book_value']]
    y = data['Close']
    
    # 3. Train the Regressor
    # Random Forest is great for finding 'Fair Value' ranges
    rf_model = RandomForestRegressor(n_estimators=100, random_state=42)
    rf_model.fit(X, y)
    
    # 4. Predict based on the LATEST known fundamentals
    current_funda = X.tail(1)
    fair_value = rf_model.predict(current_funda)[0]
    
    return round(float(fair_value), 2)




# Getting data from sql for last 4 yrs of financials for the Fair Value Engine

def get_valuation_data(ticker):
    """
    Phase 3 - Step A: Joins your specific Income and Balance tables 
    to create a fundamental profile for the Random Forest.
    """
    
    # 1. Connection Details (from environment variables)
    import os as _os
    host     = _os.getenv("DB_HOST", "localhost")
    user     = _os.getenv("DB_USER", "root")
    password = _os.getenv("DB_PASS", "Bank1234")
    port     = _os.getenv("DB_PORT", "3306")
    db_name  = _os.getenv("DB_NAME", "bank_data")
    engine = create_engine(f"mysql+mysqlconnector://{user}:{password}@{host}:{port}/{db_name}")
    
    # 2. The Multi-Table Join Query using your exact column names
    query = f"""
    SELECT 
        i.Date, 
        i.`Net Income`, 
        i.`Total Revenue`, 
        b.`Stockholders Equity`, 
        b.`Total Debt`
    FROM income_statement_annual i
    INNER JOIN balance_sheet_annual b 
        ON i.Company = b.Company AND i.Date = b.Date
    WHERE i.Company = '{ticker}'
    ORDER BY i.Date ASC
    """
    
    try:
        df_funda = pd.read_sql(query, engine)
        
        # 3. Ratio Calculation (The 'Food' for the AI)
        # Margin: How much profit per dollar of sales
        df_funda['net_margin'] = df_funda['Net Income'] / df_funda['Total Revenue']
        
        # Debt-to-Equity: Financial leverage
        df_funda['debt_to_equity'] = df_funda['Total Debt'] / df_funda['Stockholders Equity']
        
        # Book Value: Using Equity as the base
        df_funda['book_value'] = df_funda['Stockholders Equity']
        
        # Clean up the date format
        df_funda['date'] = pd.to_datetime(df_funda['Date'])
        
        return df_funda[['date', 'net_margin', 'debt_to_equity', 'book_value']].dropna()
        
    except Exception as e:
        print(f"Extraction Error: {e}")
        return pd.DataFrame()


# Random forest for Fair Value Engine
def calculate_fair_value(df_funda, df_historical):
    """
    Phase 3: Fixed Date Matching for RangeIndex.
    """
    from sklearn.ensemble import RandomForestRegressor
    import pandas as pd

    if df_funda.empty:
        return 0.0

    # 1. Clean up Fundamentals Dates
    df_funda['date_only'] = pd.to_datetime(df_funda['date']).dt.date
    
    # 2. Clean up Historical Price Dates (Handling RangeIndex)
    # If 'Date' is a column, use it; if it's the index, reset it.
    temp_hist = df_historical.copy()
    if 'Date' not in temp_hist.columns:
        temp_hist = temp_hist.reset_index()
    
    temp_hist['date_only'] = pd.to_datetime(temp_hist['Date']).dt.date
    
    # 3. Merge on the cleaned 'date_only' column
    data = pd.merge(df_funda, temp_hist, on='date_only')
    
    # Fallback: If no exact date match, match by Year
    if data.empty:
        df_funda['year'] = pd.to_datetime(df_funda['date']).dt.year
        temp_hist['year'] = pd.to_datetime(temp_hist['Date']).dt.year
        data = pd.merge(df_funda, temp_hist[['year', 'Close']], on='year').drop_duplicates('year')

    if data.empty:
        return 0.0

    # 4. Train the Random Forest
    X = data[['net_margin', 'debt_to_equity', 'book_value']]
    y = data['Close']
    
    rf_model = RandomForestRegressor(n_estimators=100, random_state=42)
    rf_model.fit(X, y)
    
    # 5. Predict Today's 'Fair Value'
    latest_vitals = df_funda[['net_margin', 'debt_to_equity', 'book_value']].tail(1)
    fair_value = rf_model.predict(latest_vitals)[0]
    
    return round(float(fair_value), 2)





# Isolation Forest for Anomaly Detection in Phase 4 (Risk Assessment)

def detect_anomalies(df_historical, ticker):
    """
    Phase 4: The Safety Net. 
    Detects if current Price/Volume/Volatility is an outlier.
    """
    # 1. Prepare Features for the "Forest"
    df = df_historical.copy()
    
    # Calculate Daily Returns and Volatility
    df['Returns'] = df['Close'].pct_change()
    df['Vol_Shock'] = df['Volume'] / df['Volume'].rolling(window=20).mean()
    df['Price_ZScore'] = (df['Returns'] - df['Returns'].rolling(window=20).mean()) / df['Returns'].rolling(window=20).std()
    
    # Drop the empty rows created by rolling windows
    df_clean = df[['Returns', 'Vol_Shock', 'Price_ZScore']].dropna()

    # 2. Initialize the Isolation Forest
    # contamination=0.05 means we expect 5% of days to be "weird"
    iso_forest = IsolationForest(contamination=0.30, random_state=42)
    
    # 3. Fit and Predict
    # 1 = Normal, -1 = Anomaly
    df_clean['Anomaly_Score'] = iso_forest.fit_predict(df_clean)
    
    # 4. Check the LATEST day
    latest_status = df_clean['Anomaly_Score'].iloc[-1]
    is_anomaly = True if latest_status == -1 else False
    
    # 5. Determine the "Risk Level"
    risk_msg = "[!] HIGH RISK: Unusual Market Activity" if is_anomaly else "[OK] STABLE: Normal Trading Pattern"
    
    return {
        "is_anomaly": is_anomaly,
        "risk_message": risk_msg,
        "score": latest_status
    }