# src/universe.py
# S&P 500 ticker universe — fetches live from Wikipedia, falls back to hardcoded list

import pandas as pd

FALLBACK_SP500 = [
    # Mega-cap Tech & Growth
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "GOOG", "META", "BRK-B", "TSLA", "LLY",
    "JPM", "V", "XOM", "UNH", "WMT", "MA", "JNJ", "PG", "AVGO", "HD",
    "MRK", "COST", "ABBV", "CVX", "KO", "NFLX", "BAC", "AMD", "PEP", "TMO",
    "CRM", "ACN", "ADBE", "MCD", "ABT", "CSCO", "DIS", "ORCL", "INTC", "VZ",
    "DHR", "TXN", "WFC", "PM", "NEE", "AMGN", "IBM", "CAT", "RTX", "INTU",
    "SPGI", "NOW", "UPS", "LOW", "QCOM", "ISRG", "GS", "LMT", "ELV", "SYK",
    "BX", "HON", "PLD", "AXP", "AMAT", "T", "DE", "MS", "GE", "VRTX",
    "MDLZ", "CB", "CI", "MO", "GILD", "C", "MMC", "TJX", "SO", "ETN",
    "CL", "SCHW", "ZTS", "BSX", "PGR", "LRCX", "ADI", "SLB", "ICE", "CME",
    "PH", "EOG", "KKR", "REGN", "ITW", "MCO", "USB", "DUK", "FCX", "EMR",
    "AON", "PSA", "NSC", "NOC", "GD", "F", "GM", "UBER", "ABNB", "SNOW",
    "PLTR", "PANW", "CRWD", "DDOG", "ZS", "MDB", "NET", "BILL", "HUBS", "TEAM",
    "WDAY", "OKTA", "ZM", "DOCU", "TWLO", "FIVN", "PEGA",
    "MSCI", "MCK", "AMP", "AFL", "ALL", "AIG", "MET", "PRU", "HIG", "TRV",
    "BK", "STT", "NTRS", "RF", "CFG", "HBAN", "KEY", "FITB", "MTB", "ZION",
    "AMT", "CCI", "EQIX", "DLR", "SPG", "O", "AVB", "EQR", "ESS", "UDR",
    "LIN", "APD", "SHW", "ECL", "PPG", "IFF", "EMN", "CE", "HUN", "OLN",
    "NUE", "STLD", "RS", "ATI", "AA", "CLF", "APA", "DVN", "HAL",
    "BKR", "MPC", "VLO", "PSX", "COP", "OXY", "FANG",
    "UNP", "CSX", "WAB", "EXPD", "XPO", "CHRW", "JBHT", "ODFL", "SAIA",
    "DAL", "UAL", "AAL", "LUV", "ALK", "JBLU", "ALGT", "SKYW",
    "NCLH", "CCL", "RCL", "MHK", "WHR", "SWK", "ITT", "PNR", "GNRC",
    "ROK", "FTV", "AME", "TDY", "TDG", "LDOS", "SAIC", "BAH", "CACI", "DRS",
    "TMO", "A", "BIO", "TECH", "WAT", "HOLX", "IDXX", "ALGN", "HSIC",

    # Technology (additional)
    "KLAC", "MCHP", "MPWR", "CDNS", "SNPS", "FTNT", "CTSH", "GLW", "WDC", "STX",
    "NTAP", "HPE", "HPQ", "KEYS", "ZBRA", "ANSS", "PTC", "TYL", "FFIV", "AKAM",
    "VRSN", "PAYC", "GDDY", "CDW", "NXPI", "JNPR", "EPAM", "TRMB", "ENPH", "SEDG",

    # Consumer Discretionary (additional)
    "NKE", "SBUX", "TGT", "EBAY", "ROST", "BBY", "DG", "DLTR", "CMG", "YUM",
    "DRI", "EXPE", "BKNG", "MGM", "LVS", "WYNN", "MAR", "HLT", "PHM", "DHI",
    "LEN", "NVR", "TOL", "MAS", "POOL", "AZO", "ORLY", "GPC", "LKQ", "APTV",
    "BWA", "LEA", "RL", "PVH", "TPR", "HBI", "VFC", "CPRI", "MOH",

    # Consumer Staples (additional)
    "SYY", "HSY", "GIS", "KHC", "CPB", "CAG", "HRL", "MKC", "CHD", "CLX",
    "KMB", "WBA", "CVS", "TAP", "STZ", "EL", "KR", "SFM",

    # Healthcare (additional)
    "HUM", "CNC", "BAX", "BDX", "EW", "DXCM", "PODD", "RMD", "STE", "IQV",
    "PFE", "BMY", "MRNA", "BIIB", "ILMN", "CRL", "GEHC", "HCA", "THC", "UHS",
    "VTRS", "OGN", "RVTY", "MTD", "BARD",

    # Industrials (additional)
    "BA", "DOV", "IR", "CARR", "OTIS", "TT", "JCI", "ROP", "VRSK", "EFX",
    "CTAS", "RSG", "WM", "WCN", "PWR", "URI", "J", "RHI", "AXON", "CPRT",
    "FAST", "GWW", "MSI", "NDSN", "FLR", "MAN", "AGCO",

    # Energy (additional)
    "OKE", "WMB", "KMI", "LNG", "TRGP",

    # Utilities (additional)
    "D", "EXC", "AEP", "SRE", "PCG", "ED", "ES", "WEC", "XEL", "ETR",
    "CNP", "NI", "AES", "LNT", "PPL", "AWK", "CMS", "NRG", "EIX",

    # Real Estate (additional)
    "WELL", "VTR", "ARE", "BXP", "KIM", "FRT", "NNN", "SUI", "CPT", "MAA",
    "INVH", "AMH", "CBRE",

    # Materials (additional)
    "NEM", "FMC", "CF", "MOS", "ALB", "LYB", "IP", "PKG", "SEE", "BALL", "AVY",

    # Communication Services (additional)
    "CMCSA", "CHTR", "TMUS", "PARA", "WBD", "LYV", "TTWO", "EA", "OMC",
    "IPG", "FOXA", "FOX", "NWSA", "NYT",

    # Financials (additional)
    "COF", "DFS", "SYF", "ALLY", "FIS", "FISV", "PYPL", "WRB", "GL", "RJF",
    "CBOE", "BRO", "WTW", "CINF", "EG", "RE", "ACGL", "HIG",
]

# Remove duplicates that might have slipped in
FALLBACK_SP500 = list(dict.fromkeys(FALLBACK_SP500))


def get_sp500_tickers() -> list[str]:
    """
    Returns the current S&P 500 ticker list.
    Tries Wikipedia first, falls back to the hardcoded list.
    """
    try:
        tables = pd.read_html(
            "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
            header=0
        )
        tickers = tables[0]["Symbol"].tolist()
        # yfinance uses BRK-B not BRK.B
        tickers = [t.replace(".", "-") for t in tickers]
        print(f"[Universe] Loaded {len(tickers)} S&P 500 tickers from Wikipedia.")
        return tickers
    except Exception as e:
        print(f"[Universe] Wikipedia fetch failed ({e}). Using fallback list of {len(FALLBACK_SP500)} tickers.")
        return FALLBACK_SP500


def get_nse_tickers() -> list[str]:
    """
    Returns a curated list of top NSE (India) tickers in yfinance format (.NS suffix).
    Expand this list when scaling to Indian markets.
    """
    nse_top = [
        "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
        "HINDUNILVR.NS", "ITC.NS", "SBIN.NS", "BHARTIARTL.NS", "KOTAKBANK.NS",
        "LT.NS", "AXISBANK.NS", "ASIANPAINT.NS", "MARUTI.NS", "SUNPHARMA.NS",
        "TITAN.NS", "BAJFINANCE.NS", "WIPRO.NS", "ULTRACEMCO.NS", "NESTLEIND.NS",
        "POWERGRID.NS", "NTPC.NS", "BAJAJFINSV.NS", "TECHM.NS", "HCLTECH.NS",
        "ONGC.NS", "COALINDIA.NS", "JSWSTEEL.NS", "TATASTEEL.NS", "GRASIM.NS",
        "INDUSINDBK.NS", "TATAMOTORS.NS", "ADANIPORTS.NS", "CIPLA.NS", "DRREDDY.NS",
        "DIVISLAB.NS", "APOLLOHOSP.NS", "EICHERMOT.NS", "HEROMOTOCO.NS", "M&M.NS",
        "BRITANNIA.NS", "DABUR.NS", "MARICO.NS", "PIDILITIND.NS", "BERGEPAINT.NS",
        "HAVELLS.NS", "TATACONSUM.NS", "UPL.NS", "DMART.NS", "ZOMATO.NS",
    ]
    return nse_top


if __name__ == "__main__":
    tickers = get_sp500_tickers()
    print(f"Total tickers: {len(tickers)}")
    print(tickers[:10])
