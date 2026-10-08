from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

from .gmail import SCOPES


def authorize(client_secret_path: str, token_path: str) -> None:
    """Runs the interactive OAuth consent in the browser and saves the token.

    The container reads the saved token later.

    Args:
        client_secret_path: Path to the OAuth client JSON from Google Cloud.
        token_path: Where to write the token file.
    """
    flow = InstalledAppFlow.from_client_secrets_file(client_secret_path, SCOPES)
    creds = flow.run_local_server(port=0)
    token = Path(token_path)
    token.parent.mkdir(parents=True, exist_ok=True)
    token.write_text(creds.to_json(), encoding="utf-8")
