# Nutze yfinance, um historische Kursdaten zu beziehen:
import yfinance as yf
import pandas as pd

def load_hist_prices(ticker: str, period: str = "2y") -> pd.DataFrame:
    """
    Lädt historische Kursdaten für den angegebenen Ticker.
    
    Args:
        ticker: Börsenticker, z. B. "AAPL".
        period: Zeitraum (z. B. "2y", "1y", "6mo").

    Returns:
        DataFrame mit OHLC-Kursdaten (Open, High, Low, Close, Volume).
    """
    df = yf.download(ticker, period=period, interval="1d", auto_adjust=True)
    # 🔧 Flatten yfinance MultiIndex columns (common for non-US tickers)
    if isinstance(df.columns, pd.MultiIndex):
        # keep only the OHLCV names as single-level columns
        df.columns = df.columns.get_level_values(0)
    df.dropna(inplace=True)
    return df

# Leite aus den historischen Daten Features ab und definiere eine Zielvariable:
def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Erstellt Trainingsfeatures und eine Zielvariable (steigt/fällt am nächsten Tag).
    """
    df["return"] = df["Close"].pct_change()
    df["MA5"] = df["Close"].rolling(5).mean()
    df["MA20"] = df["Close"].rolling(20).mean()
    df["target"] = (df["return"].shift(-1) > 0).astype(int)  # 1 = Kurs steigt
    df.dropna(inplace=True)
    return df

# Wähle ein geeignetes Modell (z.B. RandomForestClassifier, LogisticRegression). Trainiere, evaluiere und verwende es zur Vorhersage:
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score

def train_model(df: pd.DataFrame):
    """
    Trainiert ein Klassifikationsmodell und gibt es zusammen mit dem Test-Score zurück.
    """
    X = df[["return", "MA5", "MA20"]]
    y = df["target"]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)
    
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    
    preds = model.predict(X_test)
    acc = accuracy_score(y_test, preds)
    print(f"Test-Accuracy: {acc:.2f}")
    return model

# Prognose für den letzten Tag:
def predict_move(model, df: pd.DataFrame) -> bool:
    """
    Erzeugt eine Vorhersage für die letzte Zeile des DataFrames.
    
    Returns:
        True, wenn Modell einen Kursanstieg erwartet, sonst False.
    """
    last_row = df[["return", "MA5", "MA20"]].iloc[-1].values.reshape(1, -1)
    pred = model.predict(last_row)[0]
    return bool(pred)

def predict_move_proba(model, df: pd.DataFrame) -> float:
    """
    Returns the probability that the stock will rise tomorrow.

    Args:
        model: Trained classification model.
        df: Feature-engineered DataFrame.

    Returns:
        Probability (0.0–1.0) that the next day's close will be higher.
    """
    last_row = df[["return", "MA5", "MA20"]].iloc[-1].values.reshape(1, -1)
    proba = model.predict_proba(last_row)[0]  # [prob_down, prob_up]
    return float(proba[1])  # probability of "up"