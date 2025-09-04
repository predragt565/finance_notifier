# Streamlit app main file

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf
from src.app.config import load_config
from src.app.core import run_once
from pathlib import Path
from datetime import datetime, timedelta
import time
from src.app.utils import mask_secret
import logging
from dotenv import load_dotenv  # Load environment from .env

# Ensure .env variables (e.g., NTFY_TOPIC) are available
load_dotenv()
# Load default config
cfg = load_config("config.json")
# TEMP DEBUG: Show loaded topic (masked)
st.sidebar.markdown(f"🔐 Loaded topic: `{mask_secret(cfg['ntfy']['topic'])}`")
# 🛡️ DEBUG: Ensure the correct topic is loaded from .env
# assert "ntfy" in cfg and "topic" in cfg["ntfy"], "Missing ntfy.topic in config"
# print("DEBUG - topic loaded from config:", cfg["ntfy"]["topic"])


st.set_page_config(page_title="Stock Notifier Dashboard by Pred", layout="wide")

# --- Sidebar: Configuration ---
st.sidebar.title("🔧 Configuration")

# Section: Stocks
st.sidebar.markdown("---")
st.sidebar.subheader("📈 Stocks")
selected_stock = st.sidebar.selectbox("Add Stock", options=["AAPL", "MSFT", "O", "WPY.F", "QDVX.DE"])
# Initialize session state list
if "tickers" not in st.session_state:
    st.session_state["tickers"] = []
# Add selected stock to session
if st.sidebar.button("➕ Add Stock"):
    if selected_stock not in st.session_state["tickers"]:
        st.session_state["tickers"].append(selected_stock)

# Show selected tickers in multiselect
selected_tickers = st.sidebar.multiselect("Selected Tickers", options=st.session_state["tickers"], default=st.session_state["tickers"])
# Sync removals (user manually unchecking tickers)
st.session_state["tickers"] = selected_tickers

threshold_pct = st.sidebar.slider("Alert threshold (%)", min_value=0.0, max_value=10.0, value=cfg["threshold_pct"], step=0.05)

# Sub-section: Market Hours
st.sidebar.markdown("---")
st.sidebar.subheader("**🕒 Market Hours**")
market_hours_enabled = st.sidebar.radio("Use market hours?", [True, False], index=0 if cfg["market_hours"]["enabled"] else 1)
market_hours_tz = st.sidebar.text_input("Time Zone", value=cfg["market_hours"]["tz"])
market_hours_start = st.sidebar.slider("Market opens at (hour)", 0, 23, cfg["market_hours"]["start_hour"])
market_hours_end = st.sidebar.slider("Market closes at (hour)", 0, 23, cfg["market_hours"]["end_hour"])
market_hours_weekdays_only = st.sidebar.checkbox("Weekdays only", value=cfg["market_hours"]["days_mon_to_fri_only"])

# Section: News
st.sidebar.markdown("---")
st.sidebar.subheader("📰 News")
news_enabled = st.sidebar.radio("Enable News", [True, False], index=0 if cfg["news"]["enabled"] else 1)
news_limit = st.sidebar.slider("Max news", 1, 5, cfg["news"]["limit"])
news_lookback = st.sidebar.slider("News lookback (hours)", 1, 12, cfg["news"]["lookback_hours"])
news_lang = st.sidebar.selectbox("News language", ["en", "de"], index=["en", "de"].index(cfg["news"]["lang"]))
news_country = st.sidebar.selectbox("News country", ["us", "uk", "de"], index=["us", "uk", "de"].index(cfg["news"]["country"].lower()))

# Section: Ntfy
st.sidebar.markdown("---")
st.sidebar.subheader("📲 Notifications")
dry_run = st.sidebar.radio("Ntfy dry run (no push)", [True, False], index=0 if cfg["test"]["dry_run"] else 1)

# Refresh interval
st.sidebar.markdown("---")
st.sidebar.subheader("🔄 Refresh")
refresh_interval = st.sidebar.slider("Interval (min)", 1, 10, cfg["ntfy"]["refresh_interval"])

# Section: Logging
st.sidebar.markdown("---")
st.sidebar.subheader("📋 Logging")
log_level = st.sidebar.selectbox("Log level", ["DEBUG", "INFO", "WARNING", "ERROR"], index=["DEBUG", "INFO", "WARNING", "ERROR"].index(cfg["log"]["level"]))
log_to_file = st.sidebar.checkbox("Log to File", value=cfg["log"]["to_file"])

# 🔥 Override config with sidebar user inputs
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
cfg["ntfy"]["refresh_interval"] = refresh_interval


# --- Save Button ---
if st.sidebar.button("💾 Save Configuration"):
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
    except Exception as e:
        st.sidebar.error(f"❌ Failed to save config: {e}")

# --- Setup logging with user-overridden config ---  
from src.app.logging_setup import setup_logging
logger = setup_logging(cfg["log"])
logger.info("Streamlit logging initialized: level=%s, to_file=%s", cfg["log"]["level"], cfg["log"]["to_file"])

# (Optional) Display effective config in sidebar
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
    
# --- Main Content ---
st.title("📡 Stock Notifier Dashboard")

if selected_tickers:
    for ticker in selected_tickers:
        try:
            df = yf.Ticker(ticker).history(period="1d", interval="1m")
            if df.empty:
                st.warning(f"No data for {ticker}")
                continue

            fig = go.Figure()
            fig.add_trace(go.Candlestick(
                x=df.index,
                open=df['Open'],
                high=df['High'],
                low=df['Low'],
                close=df['Close'],
                name=f"{ticker}"
            ))
            fig.update_layout(title=f"{ticker} Intraday Chart", xaxis_title="Time", yaxis_title="Price")
            st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.error(f"Error loading data for {ticker}: {e}")
else:
    st.info("Please select tickers from the sidebar to display data.")


# --- Optional: Run live monitor with current settings ---
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
    
#     run_once(
#         tickers=tickers,
#         threshold_pct=threshold_pct,
#         ntfy_server=cfg["ntfy"]["server"],
#         ntfy_topic=cfg["ntfy"]["topic"],
#         state_file=Path(cfg["state_file"]),
#         market_hours_cfg={
#             "enabled": market_hours_enabled,
#             "tz": tz,
#             "start_hour": start_hour,
#             "end_hour": end_hour,
#             "days_mon_to_fri_only": days_mon_to_fri_only,
#         },
#         test_cfg={
#             "enabled": True,
#             "force_delta_pct": None,
#             "dry_run": dry_run
#         },
#         news_cfg={
#             "enabled": news_enabled,
#             "limit": news_limit,
#             "lookback_hours": lookback_hours,
#             "lang": lang,
#             "country": country
#         },
#     )
    st.success("Monitoring cycle executed. Check logs or notifications for results.")
