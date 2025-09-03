import logging
from pathlib import Path
from src.app.config import load_config
from src.app.logging_setup import setup_logging
from src.app.core import run_once
from src.app.utils import mask_secret
# Imports für Testing:
from src.app.ntfy import notify_ntfy
from datetime import datetime
# Import market data functions
from src.app.market import get_open_and_last
from src.app.state import load_state, save_state
from src.app.ntfy import notify_ntfy


def main():
    """
    Entry point of the Stock Notifier application.
    """
    # DONE: Load configuration from "config.json"
    cfg = load_config("config.json")
    # print("Loaded log config:", cfg["log"])

    # DONE: Initialize the logging system with setup_logging
    logger = setup_logging(cfg["log"])

    # DONE: Log the loaded configuration, masking secrets with mask_secret
    # logger.debug("This is a DEBUG test message")
    logger.info(
        "Configuration loaded: ntfy.server=%s | ntfy.topic(masked)=%s | log.level=%s",
        cfg["ntfy"]["server"],
        mask_secret(cfg["ntfy"]["topic"]),
        cfg["log"]["level"],
    )

    # DONE: Run one monitoring cycle via run_once using settings from cfg
    run_once(
        tickers=cfg["tickers"],
        threshold_pct=float(cfg["threshold_pct"]),
        ntfy_server=cfg["ntfy"]["server"],
        ntfy_topic=cfg["ntfy"]["topic"],
        state_file=Path(cfg["state_file"]),
        market_hours_cfg=cfg["market_hours"],
        test_cfg=cfg["test"],
        news_cfg=cfg["news"],
    )
    
    # Für Test:
    # from src.app.config import deep_merge
    # test1 = {
    #     "log": 
    #         {"level": "INFO",
    #             "to_file": False
    #         },
    #         "tickers": ["AAPL"]
    #     }
    # test2 = {"log": {"level": "DEBUG"}}
    # new = deep_merge(test1, test2)      # Olex's self-made function
    # print(new)
    # print(mask_secret(cfg["ntfy"]["topic"]))
    # print(cfg["ntfy"]["server"])
    
    current_time = datetime.now().strftime("%H:%M:%S") # Full DT .strftime("%Y-%m-%d %H:%M:%S")
    
#     notify_ntfy(
#     server=cfg["ntfy"]["server"],
#     topic=cfg["ntfy"]["topic"],
#     title=f"Stock Notifier ✅ {current_time}",
#     message=f"Notification sent at {current_time}. Monitoring active for: {', '.join(cfg['tickers'])}",
#     dry_run=cfg.get("test", {}).get("dry_run", False),
#     markdown=True,
#     click_url=f"https://finance.yahoo.com/quote/{cfg['tickers'][0]}"
# )
    

if __name__ == "__main__":
    main()
