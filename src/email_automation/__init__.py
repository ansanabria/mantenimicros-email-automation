from email_automation.app import create_app


def main() -> None:
    import uvicorn

    uvicorn.run(
        "email_automation.app:create_app",
        factory=True,
        host="0.0.0.0",
        port=8000,
        reload=False,
    )


__all__ = ["create_app", "main"]
