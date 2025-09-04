import requests
import logging
from src.app.utils import mask_secret

logger = logging.getLogger("stock-alerts")


def notify_ntfy(
    server: str,
    topic: str,
    title: str,
    message: str,
    *,
    dry_run: bool = False,
    markdown: bool = False,
    click_url: str | None = None,
) -> None:
    """
    Send a push notification via ntfy.sh.

    Args:
        server (str): ntfy server URL (e.g. "https://ntfy.sh").
        topic (str): Secret topic string subscribed in the ntfy app.
        title (str): Notification title (header).
        message (str): Notification body text (supports Unicode + Emojis).
        dry_run (bool, optional): If True, do not actually send,
                                  only log message content. Default: False.
        markdown (bool, optional): If True, enable Markdown rendering
                                   in ntfy (web app only for now).
                                   Default: False.
        click_url (str | None, optional): Optional URL that opens when
                                          tapping the notification.

    Returns:
        None

    Side effects:
        - Performs an HTTP POST request to the ntfy server.
        - On success, the subscribed app receives a push message.

    Example:
        >>> notify_ntfy(
                "https://ntfy.sh",
                "my-secret-topic",
                "Stock Alert",
                "AAPL is up 5% 📈",
                markdown=True,
                click_url="https://finance.yahoo.com/quote/AAPL"
            )
    """
    # DONE: If dry_run is True, log the message and return without sending
    if dry_run:
        logger.info(
            "DRY-RUN ntfy: server=%s topic(masked)=%s title=%r msg=%r click=%s md=%s",
            server,
            mask_secret(topic),
            title,
            message,
            click_url,
            markdown
        )
        return

    # DONE: Construct the topic URL and prepare request headers
    url = f"{server.rstrip('/')}/{topic}"
    # print(url)
    headers = {
        "Title": title,
        "Priority": "high",
    }

    # DONE: If markdown is enabled, set the appropriate header
    if markdown:
        headers["Markdown"] = "yes"

    # DONE: If a click_url is provided, add it to headers
    if click_url:
        headers["Click"] = click_url

    # DONE: Perform the POST request inside a try/except block and handle errors
    try:
        r = requests.post(url, data=message.encode("utf-8"), headers=headers, timeout=20)
        r.raise_for_status()
        logger.debug("ntfy POST success to %s (%d)", url, r.status_code)
    except requests.RequestException as e:
        logger.warning("ntfy POST failed to %s: %s", url, e)

    # pass  # Remove once implemented
