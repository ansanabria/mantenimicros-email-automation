from email_automation.config import get_settings
from email_automation.services.microsoft_graph import MicrosoftGraphClient


def main() -> None:
    settings = get_settings()
    if settings.microsoft_auth_mode != "delegated":
        raise RuntimeError(
            "MICROSOFT_AUTH_MODE must be 'delegated' to use email-automation-auth"
        )

    client = MicrosoftGraphClient(settings)
    client.authenticate_interactive()
    print(
        "Microsoft Graph authentication succeeded and the token cache was updated at "
        f"{settings.microsoft_token_cache_path}"
    )
