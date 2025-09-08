# Streamlit app main file

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf
from src.app.config import load_config
from src.app.core import run_once
from src.app.utils import mask_secret, commit_and_push_config
from src.app.company import get_company_meta 
from src.app.ml_functions import load_hist_prices, engineer_features, train_model, predict_move, predict_move_proba
from pathlib import Path
from dotenv import load_dotenv  # Load environment from .env


# ------------------------------ #
# --- Initial Configuration ---
# ------------------------------ #

# Ensure .env variables (e.g., NTFY_TOPIC) are available
load_dotenv()
# Load default config
cfg = load_config("config.json")

st.set_page_config(page_title="Stock Notifier Dashboard by Pred", layout="wide")

# ------------------------------ #
# --- Cache Configuration ---
# ------------------------------ #

# Cache raw price data (fast invalidation when params change)
@st.cache_data(ttl=60 * 15, show_spinner=False)  # cache for 15 minutes
def cached_hist_prices(ticker: str, period: str = "2y", interval: str = "1d"):
    # load_hist_prices already uses interval="1d"; we pass period only for key clarity
    # If you add interval later, include it in the key.
    return load_hist_prices(ticker, period=period)

# Cache feature engineering (depends only on the raw prices above)
@st.cache_data(ttl=60 * 15, show_spinner=False)
def cached_features(ticker: str, period: str = "2y"):
    df_hist = cached_hist_prices(ticker, period=period)
    return engineer_features(df_hist)

# Cache the trained model (resource cache = great for heavier objects)
@st.cache_resource(show_spinner=False)
def cached_model(ticker: str, period: str = "2y"):
    df_feat = cached_features(ticker, period=period)
    return train_model(df_feat)


# ------------------------------ #
# --- Sidebar: Configuration ---
# ------------------------------ #

# TEMP DEBUG: Show loaded topic (masked)
st.sidebar.markdown(f"🔐 Loaded topic: `{mask_secret(cfg['ntfy']['topic'])}`")
# 🛡️ DEBUG: Ensure the correct topic is loaded from .env
# assert "ntfy" in cfg and "topic" in cfg["ntfy"], "Missing ntfy.topic in config"
# print("DEBUG - topic loaded from config:", cfg["ntfy"]["topic"])
st.sidebar.title("🔧 Configuration")

# Section: Stocks
st.sidebar.markdown("---")
st.sidebar.subheader("📈 Stocks", help="Wähle die Aktien aus, die überwacht werden sollen. Du kannst mehrere hinzufügen oder entfernen.")

# Initialize session state list only once from config
if "tickers" not in st.session_state:
    st.session_state["tickers"] = cfg["tickers"] if cfg.get("tickers") else ["AAPL", "MSFT", "RHM.DE", "BMW.DE", "MBG.DE", "VOW.DE"]

# Selectbox: Add stock from dropdown
selected_stock = st.sidebar.selectbox(
    "Add Stock",
    options=[s for s in ["AAPL", "MSFT", "RHM.DE", "BMW.DE", "MBG.DE", "VOW.DE"] if s not in st.session_state["tickers"]],
    index=0
)

# Button: Add selected stock to list
if st.sidebar.button("➕ Add Stock"):
    if selected_stock and selected_stock not in st.session_state["tickers"]:
        st.session_state["tickers"].append(selected_stock)

# Multiselect: Show and allow removal
selected_tickers = st.sidebar.multiselect(
    "Selected Tickers",
    options=st.session_state["tickers"],
    default=st.session_state["tickers"]
)

# Only update session state if changed
if selected_tickers != st.session_state["tickers"]:
    st.session_state["tickers"] = selected_tickers


threshold_pct = st.sidebar.slider("Alert threshold (%)", min_value=0.02, max_value=10.0, value=cfg["threshold_pct"], step=0.02,
                                  help="Wenn die Kursänderung eines Aktienwerts diese Schwelle über- oder unterschreitet, wird eine Benachrichtigung ausgelöst.")
# Sidebar: Intraday interval
# st.sidebar.markdown("---")
st.sidebar.subheader("⏱️ Data Interval", help="Lege das Zeitintervall für Intraday-Daten fest (z. B. 1m, 5m). Beeinflusst die Genauigkeit der Kursdaten.")

# Get available intervals from config
interval_dict = cfg.get("intraday_int", {"1 Minute": "1m"})  # fallback to 1m only

# Provide user-friendly labels as options
interval_label = st.sidebar.selectbox("Interval", options=list(interval_dict.keys()))

# Get the actual interval string to use in yfinance
data_interval_str = interval_dict[interval_label]

# Sub-section: Market Hours
st.sidebar.markdown("---")
st.sidebar.subheader("🕒 Market Hours", help="Definiere das Handelszeitfenster, in dem Benachrichtigungen erlaubt sind (basierend auf Zeitzone und Uhrzeit).")
market_hours_enabled = st.sidebar.radio("Use market hours?", [True, False], index=0 if cfg["market_hours"]["enabled"] else 1)
market_hours_tz = st.sidebar.text_input("Time Zone", value=cfg["market_hours"]["tz"])
market_hours_start = st.sidebar.slider("Market opens at (hour)", 0, 23, cfg["market_hours"]["start_hour"])
market_hours_end = st.sidebar.slider("Market closes at (hour)", 0, 23, cfg["market_hours"]["end_hour"])
market_hours_weekdays_only = st.sidebar.checkbox("Weekdays only", value=cfg["market_hours"]["days_mon_to_fri_only"])

# Section: News
st.sidebar.markdown("---")
st.sidebar.subheader("📰 News", help="Aktiviere Benachrichtigungen zu Nachrichten. Konfiguriere Anzahl, Sprache, Land und Zeitfenster für relevante News.")
news_enabled = st.sidebar.radio("Enable News", [True, False], index=0 if cfg["news"]["enabled"] else 1)
news_limit = st.sidebar.slider("Max news", 1, 5, cfg["news"]["limit"])
news_lookback = st.sidebar.slider("News lookback (hours)", 1, 12, cfg["news"]["lookback_hours"])
news_lang = st.sidebar.selectbox("News language", ["en", "de"], index=["en", "de"].index(cfg["news"]["lang"]))
news_country = st.sidebar.selectbox("News country", ["us", "uk", "de"], index=["us", "uk", "de"].index(cfg["news"]["country"].lower()))

# Section: Ntfy
st.sidebar.markdown("---")
st.sidebar.subheader("📲 Notifications", help="Lege fest, ob Benachrichtigungen gesendet oder nur simuliert werden (Dry Run).")
dry_run = st.sidebar.radio("Ntfy dry run (no push)", [True, False], index=0 if cfg["test"]["dry_run"] else 1)

# Refresh interval - not implemented due to system restrictions
# st.sidebar.markdown("---")
# st.sidebar.subheader("🔄 GitHub Refresh", help="Lege das Intervall in Minuten fest, wie oft geprüft werden soll. Wird für geplante Läufe in GitHub Actions verwendet.")
# refresh_interval = st.sidebar.slider("Interval (min)", 10, 60, cfg["ntfy"]["refresh_interval"], step=5)

# Section: Logging
st.sidebar.markdown("---")
st.sidebar.subheader("📋 Logging", help="Konfiguriere das Logging-Level und ob Logs in eine Datei geschrieben werden sollen.")
print("Loaded log level:", cfg["log"]["level"])

log_level = st.sidebar.selectbox("Log level", ["DEBUG", "INFO", "WARNING", "ERROR"], index=["DEBUG", "INFO", "WARNING", "ERROR"].index(cfg["log"]["level"]))
log_to_file = st.sidebar.checkbox("Log to File", value=cfg["log"]["to_file"])

# Override config with sidebar user inputs
cfg["tickers"] = selected_tickers
cfg["threshold_pct"] = threshold_pct
cfg["market_hours"]["enabled"] = market_hours_enabled
cfg["market_hours"]["tz"] = market_hours_tz
cfg["market_hours"]["start_hour"] = market_hours_start
cfg["market_hours"]["end_hour"] = market_hours_end
cfg["market_hours"]["week_days_only"] = market_hours_weekdays_only
cfg["news"]["enabled"] = news_enabled
cfg["news"]["limit"] = news_limit
cfg["news"]["lookback_hours"] = news_lookback
cfg["news"]["lang"] = news_lang
cfg["news"]["country"] = news_country
cfg["log"]["level"] = log_level
cfg["log"]["to_file"] = log_to_file
cfg["test"]["dry_run"] = dry_run
# cfg["ntfy"]["refresh_interval"] = refresh_interval    # <- currently not in use

# GitHub Token input field (optional for push)
gh_token = st.sidebar.text_input("🔑 GitHub Token", type="password", help="Dein persönlicher Zugriffstoken (PAT), um Änderungen an config.json direkt ins GitHub-Repository zu pushen.")

# --- Save Config Button ---
if st.sidebar.button("💾 Save Configuration", help="Speichert alle aktuellen Einstellungen dauerhaft in der config.json-Datei."):
    import json
    import copy

    # Make a deep copy to avoid mutating original cfg
    config_to_save = copy.deepcopy(cfg)

    # Overwrite the topic placeholder instead of saving actual value
    if "ntfy" in config_to_save:
        config_to_save["ntfy"]["topic"] = "${NTFY_TOPIC}"  # Don't save actual topic!

    # Save to config.json
    try:
        with open("config.json", "w", encoding="utf-8") as f:
            json.dump(config_to_save, f, indent=2)
        st.sidebar.success("✅ Configuration saved to config.json")

        # Git push if token is provided
        if gh_token:
            if commit_and_push_config(gh_token):
                st.sidebar.success("🚀 Config pushed to GitHub!")
            else:
                st.sidebar.warning("⚠️ Push failed — check token or repo settings.")
    
    except Exception as e:
        st.sidebar.error(f"❌ Failed to save config: {e}")

# --- Setup logging with user-overridden config ---  
from src.app.logging_setup import setup_logging
logger = setup_logging(cfg["log"])
logger.info("Streamlit logging initialized: level=%s, to_file=%s", cfg["log"]["level"], cfg["log"]["to_file"])

# Display effective config in sidebar
with st.sidebar.expander("🔧 Effective Config"):
    safe_cfg = {
        **cfg,
        "ntfy": {
            **cfg["ntfy"],
            "topic_mask": mask_secret(cfg["ntfy"]["topic"])
        }
    }
    safe_cfg["ntfy"].pop("topic")
    st.json(safe_cfg)

    
# ------------------------------ #
# ------   Main Content   ------
# ------------------------------ #

# st.title("📡 Stock Notifier Dashboard")
# Set the logo link first
logo_link = "https://avatars.githubusercontent.com/u/213751052?v=4"
logo_url = "https://github.com/predragt565"
# Inject logo + title via Markdown/HTML (30x30px, aligned next to title)
st.markdown(
    f"""
    <div style="display: flex; align-items: center;">
        <h1 style="display: inline;">📡 Stock Notifier Dashboard by Pred</h1>
        <a href="{logo_url}" target="_blank">
        <img src="{logo_link}" width="50" height="50" style="margin-right: 10px;" />
        </a>
    </div>
    """,
    unsafe_allow_html=True
)

# --- Run live monitor with current settings ---
run_now = st.button("🚀 Run Monitoring Cycle")
if run_now:
    
    # Print parameter dump
    st.info(f"ℹ️ Monitoring configured for: {', '.join(cfg['tickers'])} | Threshold: {cfg['threshold_pct']}%")

    # for debugging only
    # print("🔍 Final topic passed to run_once():", cfg["ntfy"]["topic"])

    run_once(
        tickers=cfg["tickers"],
        threshold_pct=cfg["threshold_pct"],
        ntfy_server=cfg["ntfy"]["server"],
        ntfy_topic=cfg["ntfy"]["topic"],
        state_file=Path(cfg["state_file"]),
        market_hours_cfg=cfg["market_hours"],
        test_cfg=cfg["test"],
        news_cfg=cfg["news"],
    )
    st.success("Monitoring cycle executed. Check logs or notifications for results.")
        
# --- TABS for Each Ticker ---
if selected_tickers:
    st.subheader("Intraday Data:")
    tabs = st.tabs(selected_tickers)

    for idx, ticker in enumerate(selected_tickers):
        with tabs[idx]:
            try:
                st.subheader(f"📈 {ticker}")

                # --- Load and display stock meta/info ---
                meta = get_company_meta(ticker)
                st.markdown(f"**Company:** {meta.raw_name or meta.name}")

                # --- Get intraday data ---
                df = yf.Ticker(ticker).history(period="1d", interval=data_interval_str)
                if df.empty:
                    st.warning("No intraday data available.")
                    continue

                open_price = df["Open"].iloc[0]
                close_price = df["Close"].iloc[-1]
                delta_pct = ((close_price - open_price) / open_price) * 100.0
                arrow = "🟢 ▲" if delta_pct >= 0 else "🔴 ▼"    
                body_lines = f"{arrow} Δ={delta_pct:.2f}% vs. Open"
                last_updated = df.index[-1].strftime("%Y-%m-%d %H:%M")

                # --------  Plot charts  ----------
                fig = go.Figure()
                fig.add_trace(go.Candlestick(
                    x=df.index,
                    open=df['Open'],
                    high=df['High'],
                    low=df['Low'],
                    close=df['Close'],
                    name=ticker
                ))
                fig.update_layout(
                    title=f"{ticker} | Open: {open_price:.2f} | Last: {close_price:.2f}  {body_lines} <br>As of: {last_updated}",
                    xaxis_title="Time",
                    yaxis_title="Price"
                )
                st.plotly_chart(fig, use_container_width=True)

                # -------- Show raw intraday data
                with st.expander("📄 Show raw intraday data (last 50)", expanded=False):
                    st.dataframe(df.tail(50))

                # ------------------------------ #
                # --- ML Prediction Section ----
                # ------------------------------ #
                st.subheader("🔮 ML Prediction")
                                
                # moved to cached section at the top
                # df_hist = load_hist_prices(ticker)
                # df_feat = engineer_features(df_hist)
                # model = train_model(df_feat)
                # prediction = predict_move(model, df_feat)
                # probability_up = predict_move_proba(model, df_feat)

                # -------- Choose training window period
                training_period = "2y"

                # -------- Use cached versions
                df_feat = cached_features(ticker, period=training_period)
                model = cached_model(ticker, period=training_period)

                # -------- Label + probability
                label_up = predict_move(model, df_feat)
                prob_up = predict_move_proba(model, df_feat)

                if label_up:
                    st.success(f"⬆️ Expected to Rise (Confidence: {prob_up:.2%})")
                else:
                    st.error(f"⬇️ Expected to Fall (Confidence: {(1 - prob_up):.2%})")

                # -------- Build a plotting DataFrame with last 7 days
                df_recent = df_feat.tail(7).copy()
                idx_name = df_recent.index.name or "index"
                plot_df = df_recent.reset_index().rename(columns={idx_name: "Date"})

                # -------- Normalize timezone to avoid mixed tz issues across tickers
                plot_df["Date"] = pd.to_datetime(plot_df["Date"]).dt.tz_localize(None)

                # -------- Build a single Plotly chart with two lines:
                #   - ornage: last 7 daily closes (from plot_df["Close"])
                #   - blue: MA20
                fig7 = go.Figure()
                fig7.add_trace(
                    go.Scatter(
                        x=plot_df["Date"],
                        y=plot_df["Close"],
                        mode="lines+markers",
                        name="Last 7-Day Close",  # original last 7-day line (blue by default)
                        line=dict(color="orange")
                    )
                )
                fig7.add_trace(
                    go.Scatter(
                        x=plot_df["Date"],
                        y=plot_df["MA20"],
                        mode="lines",
                        name="MA20 Close ",
                        # line=dict(color="blue")
                    )
                )
                fig7.update_layout(title="Last 7 Daily Closes vs MA20", xaxis_title="Date", yaxis_title="Price")
                st.plotly_chart(fig7, use_container_width=True)

                # -------- Show last 7 days movement trend for reference
                if not df_recent.empty:
                    # add label column from target and drop original target
                    df_recent["target_lbl"] = df_recent["target"].map({1: "Up", 0: "Down"}).fillna("N/A")
                    if "target" in df_recent.columns:
                        df_recent = df_recent.drop(columns=["target"])
                
                # -------- Show last 7 days Close, MA5 & MA20 data
                with st.expander("📄 Show raw last 7-Day data", expanded=False):
                    st.dataframe(df_recent.tail(7))

            except Exception as e:
                st.error(f"Error processing {ticker}: {e}")
else:
    st.info("Please select tickers from the sidebar.")

