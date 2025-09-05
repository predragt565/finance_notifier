import os
import subprocess
import streamlit as st


def mask_secret(s: str, keep: int = 1) -> str:
    """Maskiert sensible Strings für Logging-Ausgaben."""
    if not s:
    # DONE: Gib "(unset)" zurück, falls der String leer oder None ist
        return "(unset)"
    # DONE: Falls die Länge > keep * 2 ist, behalte jeweils die ersten/letzten
    #       'keep' Zeichen und ersetze die Mitte durch eine Ellipse
    if len(s) > keep * 2:
        return s[:keep] + "..." + s[-keep:]
    # DONE: Andernfalls gib den ersten und letzten Buchstaben mit Ellipse dazwischen aus
    else:
        return s[0] + "..." + s[-1] if len(s) > 1 else s


import os
import subprocess
import streamlit as st

def commit_and_push_config(token: str | None = None) -> bool:
    """
    Commit config.json and push to GitHub using a token.

    Expects:
    - USR_NAME and GITHUB_REPO in .env
    - GitHub PAT provided as argument or via GH_TOKEN in env
    """
    token = token or os.environ.get("GH_TOKEN")
    usr = os.environ.get("USR_NAME")
    repo = os.environ.get("GITHUB_REPO")
    branch = "main"

    if not all([token, usr, repo]):
        st.sidebar.error("❌ GitHub credentials (USR_NAME, GITHUB_REPO, GH_TOKEN) are missing.")
        return False

    repo_url = f"https://{token}@github.com/{usr}/{repo}.git"

    try:
        subprocess.run(["git", "config", "user.email", "streamlit@example.com"], check=True)
        subprocess.run(["git", "config", "user.name", "streamlit-bot"], check=True)
        subprocess.run(["git", "config", "commit.gpgsign", "false"], check=True)
        subprocess.run(["git", "add", "config.json"], check=True)

        diff = subprocess.run(["git", "diff", "--cached", "--quiet", "--", "config.json"])
        if diff.returncode == 0:
            st.sidebar.info("ℹ️ No changes to commit.")
            return False

        subprocess.run(["git", "commit", "--no-gpg-sign", "-m", "trigger: new config saved"], check=True)
        subprocess.run(["git", "push", repo_url, branch], check=True)
        return True

    except subprocess.CalledProcessError as exc:
        err = exc.stderr or exc.stdout or str(exc)
        st.sidebar.error(f"❌ Git push failed: {err}")
        return False
