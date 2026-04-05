# src/sector_map.py
# GICS sector mapping for S&P 500 tickers.
# Used to populate the 'sector' column in daily_kpi_snapshot.

SECTOR_MAP = {
    # Information Technology
    "AAPL": "Technology", "MSFT": "Technology", "NVDA": "Technology", "AVGO": "Technology",
    "ORCL": "Technology", "CSCO": "Technology", "ADBE": "Technology", "CRM": "Technology",
    "INTU": "Technology", "TXN": "Technology", "AMD": "Technology", "QCOM": "Technology",
    "AMAT": "Technology", "LRCX": "Technology", "ADI": "Technology", "IBM": "Technology",
    "INTC": "Technology", "ACN": "Technology", "NOW": "Technology", "PANW": "Technology",
    "CRWD": "Technology", "KLAC": "Technology", "MCHP": "Technology", "MPWR": "Technology",
    "CDNS": "Technology", "SNPS": "Technology", "FTNT": "Technology", "CTSH": "Technology",
    "GLW": "Technology", "WDC": "Technology", "STX": "Technology", "NTAP": "Technology",
    "HPE": "Technology", "HPQ": "Technology", "KEYS": "Technology", "ZBRA": "Technology",
    "ANSS": "Technology", "PTC": "Technology", "TYL": "Technology", "FFIV": "Technology",
    "AKAM": "Technology", "VRSN": "Technology", "PAYC": "Technology", "GDDY": "Technology",
    "CDW": "Technology", "NXPI": "Technology", "JNPR": "Technology", "EPAM": "Technology",
    "TRMB": "Technology", "MSI": "Technology",

    # Communication Services
    "GOOGL": "Communication", "GOOG": "Communication", "META": "Communication",
    "NFLX": "Communication", "DIS": "Communication", "T": "Communication",
    "VZ": "Communication", "CMCSA": "Communication", "CHTR": "Communication",
    "TMUS": "Communication", "PARA": "Communication", "WBD": "Communication",
    "LYV": "Communication", "TTWO": "Communication", "EA": "Communication",
    "OMC": "Communication", "FOXA": "Communication", "FOX": "Communication",
    "NWSA": "Communication", "NYT": "Communication",

    # Consumer Discretionary
    "AMZN": "Cons. Discretionary", "TSLA": "Cons. Discretionary", "HD": "Cons. Discretionary",
    "MCD": "Cons. Discretionary", "LOW": "Cons. Discretionary", "TJX": "Cons. Discretionary",
    "NKE": "Cons. Discretionary", "SBUX": "Cons. Discretionary", "TGT": "Cons. Discretionary",
    "EBAY": "Cons. Discretionary", "ROST": "Cons. Discretionary", "BBY": "Cons. Discretionary",
    "DG": "Cons. Discretionary", "DLTR": "Cons. Discretionary", "CMG": "Cons. Discretionary",
    "YUM": "Cons. Discretionary", "DRI": "Cons. Discretionary", "EXPE": "Cons. Discretionary",
    "BKNG": "Cons. Discretionary", "MGM": "Cons. Discretionary", "LVS": "Cons. Discretionary",
    "WYNN": "Cons. Discretionary", "MAR": "Cons. Discretionary", "HLT": "Cons. Discretionary",
    "PHM": "Cons. Discretionary", "DHI": "Cons. Discretionary", "LEN": "Cons. Discretionary",
    "NVR": "Cons. Discretionary", "TOL": "Cons. Discretionary", "MAS": "Cons. Discretionary",
    "POOL": "Cons. Discretionary", "AZO": "Cons. Discretionary", "ORLY": "Cons. Discretionary",
    "GPC": "Cons. Discretionary", "LKQ": "Cons. Discretionary", "APTV": "Cons. Discretionary",
    "BWA": "Cons. Discretionary", "MHK": "Cons. Discretionary", "WHR": "Cons. Discretionary",
    "RL": "Cons. Discretionary", "PVH": "Cons. Discretionary", "TPR": "Cons. Discretionary",
    "VFC": "Cons. Discretionary", "CPRI": "Cons. Discretionary", "ABNB": "Cons. Discretionary",
    "NCLH": "Cons. Discretionary", "CCL": "Cons. Discretionary", "RCL": "Cons. Discretionary",
    "DAL": "Cons. Discretionary", "UAL": "Cons. Discretionary", "AAL": "Cons. Discretionary",
    "LUV": "Cons. Discretionary", "ALK": "Cons. Discretionary", "JBLU": "Cons. Discretionary",
    "ALGT": "Cons. Discretionary", "SKYW": "Cons. Discretionary",

    # Consumer Staples
    "WMT": "Cons. Staples", "PG": "Cons. Staples", "KO": "Cons. Staples",
    "PEP": "Cons. Staples", "COST": "Cons. Staples", "MDLZ": "Cons. Staples",
    "MO": "Cons. Staples", "PM": "Cons. Staples", "CL": "Cons. Staples",
    "SYY": "Cons. Staples", "HSY": "Cons. Staples", "GIS": "Cons. Staples",
    "KHC": "Cons. Staples", "CPB": "Cons. Staples", "CAG": "Cons. Staples",
    "HRL": "Cons. Staples", "MKC": "Cons. Staples", "CHD": "Cons. Staples",
    "CLX": "Cons. Staples", "KMB": "Cons. Staples", "WBA": "Cons. Staples",
    "CVS": "Cons. Staples", "TAP": "Cons. Staples", "STZ": "Cons. Staples",
    "EL": "Cons. Staples", "KR": "Cons. Staples", "SFM": "Cons. Staples",

    # Healthcare
    "UNH": "Healthcare", "LLY": "Healthcare", "JNJ": "Healthcare", "MRK": "Healthcare",
    "ABBV": "Healthcare", "TMO": "Healthcare", "DHR": "Healthcare", "AMGN": "Healthcare",
    "ISRG": "Healthcare", "VRTX": "Healthcare", "GILD": "Healthcare", "BSX": "Healthcare",
    "ZTS": "Healthcare", "REGN": "Healthcare", "IDXX": "Healthcare", "HOLX": "Healthcare",
    "ALGN": "Healthcare", "HSIC": "Healthcare", "BIO": "Healthcare", "TECH": "Healthcare",
    "WAT": "Healthcare", "MCK": "Healthcare", "ABT": "Healthcare", "ELV": "Healthcare",
    "SYK": "Healthcare", "HUM": "Healthcare", "MOH": "Healthcare", "CNC": "Healthcare",
    "BAX": "Healthcare", "BDX": "Healthcare", "EW": "Healthcare", "DXCM": "Healthcare",
    "PODD": "Healthcare", "RMD": "Healthcare", "STE": "Healthcare", "IQV": "Healthcare",
    "PFE": "Healthcare", "BMY": "Healthcare", "MRNA": "Healthcare", "BIIB": "Healthcare",
    "ILMN": "Healthcare", "CRL": "Healthcare", "GEHC": "Healthcare", "HCA": "Healthcare",
    "THC": "Healthcare", "UHS": "Healthcare", "VTRS": "Healthcare", "OGN": "Healthcare",
    "RVTY": "Healthcare", "MTD": "Healthcare", "A": "Healthcare",

    # Financials
    "JPM": "Financials", "BAC": "Financials", "WFC": "Financials", "GS": "Financials",
    "MS": "Financials", "C": "Financials", "BX": "Financials", "KKR": "Financials",
    "BK": "Financials", "STT": "Financials", "SCHW": "Financials", "AXP": "Financials",
    "V": "Financials", "MA": "Financials", "SPGI": "Financials", "MCO": "Financials",
    "ICE": "Financials", "CME": "Financials", "AON": "Financials", "MMC": "Financials",
    "AMP": "Financials", "AFL": "Financials", "ALL": "Financials", "AIG": "Financials",
    "MET": "Financials", "PRU": "Financials", "HIG": "Financials", "TRV": "Financials",
    "USB": "Financials", "RF": "Financials", "CFG": "Financials", "HBAN": "Financials",
    "KEY": "Financials", "FITB": "Financials", "MTB": "Financials", "ZION": "Financials",
    "NTRS": "Financials", "CB": "Financials", "CI": "Financials", "PGR": "Financials",
    "MSCI": "Financials", "COF": "Financials", "DFS": "Financials", "SYF": "Financials",
    "ALLY": "Financials", "FIS": "Financials", "FISV": "Financials", "PYPL": "Financials",
    "WRB": "Financials", "GL": "Financials", "RJF": "Financials", "CBOE": "Financials",
    "BRO": "Financials", "WTW": "Financials", "CINF": "Financials", "EG": "Financials",
    "RE": "Financials", "ACGL": "Financials", "BRK-B": "Financials",

    # Industrials
    "HON": "Industrials", "CAT": "Industrials", "DE": "Industrials", "RTX": "Industrials",
    "LMT": "Industrials", "NOC": "Industrials", "GD": "Industrials", "GE": "Industrials",
    "UPS": "Industrials", "UNP": "Industrials", "CSX": "Industrials", "NSC": "Industrials",
    "ETN": "Industrials", "PH": "Industrials", "ITW": "Industrials", "EMR": "Industrials",
    "ROK": "Industrials", "FTV": "Industrials", "AME": "Industrials", "TDY": "Industrials",
    "TDG": "Industrials", "LDOS": "Industrials", "SAIC": "Industrials", "BAH": "Industrials",
    "CACI": "Industrials", "DRS": "Industrials", "WAB": "Industrials", "EXPD": "Industrials",
    "XPO": "Industrials", "CHRW": "Industrials", "JBHT": "Industrials", "ODFL": "Industrials",
    "SAIA": "Industrials", "F": "Industrials", "GM": "Industrials", "UBER": "Industrials",
    "BA": "Industrials", "DOV": "Industrials", "IR": "Industrials", "CARR": "Industrials",
    "OTIS": "Industrials", "TT": "Industrials", "JCI": "Industrials", "ROP": "Industrials",
    "VRSK": "Industrials", "EFX": "Industrials", "CTAS": "Industrials", "RSG": "Industrials",
    "WM": "Industrials", "WCN": "Industrials", "PWR": "Industrials", "URI": "Industrials",
    "J": "Industrials", "RHI": "Industrials", "AXON": "Industrials", "CPRT": "Industrials",
    "FAST": "Industrials", "GWW": "Industrials", "NDSN": "Industrials", "AGCO": "Industrials",
    "SWK": "Industrials", "ITT": "Industrials", "PNR": "Industrials", "GNRC": "Industrials",
    "MAN": "Industrials",

    # Energy
    "XOM": "Energy", "CVX": "Energy", "COP": "Energy", "EOG": "Energy",
    "SLB": "Energy", "HAL": "Energy", "BKR": "Energy", "MPC": "Energy",
    "VLO": "Energy", "PSX": "Energy", "OXY": "Energy", "DVN": "Energy",
    "APA": "Energy", "FANG": "Energy", "OKE": "Energy", "WMB": "Energy",
    "KMI": "Energy", "LNG": "Energy", "TRGP": "Energy", "CLF": "Energy",

    # Materials
    "LIN": "Materials", "APD": "Materials", "SHW": "Materials", "ECL": "Materials",
    "PPG": "Materials", "IFF": "Materials", "EMN": "Materials", "CE": "Materials",
    "HUN": "Materials", "OLN": "Materials", "NUE": "Materials", "STLD": "Materials",
    "RS": "Materials", "ATI": "Materials", "AA": "Materials", "FCX": "Materials",
    "NEM": "Materials", "FMC": "Materials", "CF": "Materials", "MOS": "Materials",
    "ALB": "Materials", "LYB": "Materials", "IP": "Materials", "PKG": "Materials",
    "SEE": "Materials", "BALL": "Materials", "AVY": "Materials",

    # Utilities
    "NEE": "Utilities", "DUK": "Utilities", "SO": "Utilities", "D": "Utilities",
    "EXC": "Utilities", "AEP": "Utilities", "SRE": "Utilities", "PCG": "Utilities",
    "ED": "Utilities", "ES": "Utilities", "WEC": "Utilities", "XEL": "Utilities",
    "ETR": "Utilities", "CNP": "Utilities", "NI": "Utilities", "AES": "Utilities",
    "LNT": "Utilities", "PPL": "Utilities", "AWK": "Utilities", "CMS": "Utilities",
    "NRG": "Utilities", "EIX": "Utilities", "ENPH": "Utilities", "SEDG": "Utilities",

    # Real Estate
    "AMT": "Real Estate", "CCI": "Real Estate", "EQIX": "Real Estate", "DLR": "Real Estate",
    "SPG": "Real Estate", "O": "Real Estate", "AVB": "Real Estate", "EQR": "Real Estate",
    "ESS": "Real Estate", "UDR": "Real Estate", "PSA": "Real Estate", "PLD": "Real Estate",
    "WELL": "Real Estate", "VTR": "Real Estate", "ARE": "Real Estate", "BXP": "Real Estate",
    "KIM": "Real Estate", "FRT": "Real Estate", "NNN": "Real Estate", "SUI": "Real Estate",
    "CPT": "Real Estate", "MAA": "Real Estate", "INVH": "Real Estate", "AMH": "Real Estate",
    "CBRE": "Real Estate",

    # Bank (kept for category=Bank tickers)
    "WFC": "Financials",
}


def get_sector(ticker: str) -> str:
    return SECTOR_MAP.get(ticker, "Other")
