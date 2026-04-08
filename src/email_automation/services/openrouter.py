from __future__ import annotations

from typing import Any, TypeVar

import httpx
from pydantic import BaseModel
from pydantic_ai import Agent, ModelSettings
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from email_automation.config import Settings

TModel = TypeVar("TModel", bound=BaseModel)


class OpenRouterClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._http_client: httpx.AsyncClient | None = None
        self._model: OpenAIChatModel | None = None

    async def complete_json(
        self,
        system_prompt: str,
        user_content: Any,
        response_model: type[TModel],
    ) -> TModel:
        agent = Agent(
            self._get_model(),
            output_type=response_model,
            system_prompt=system_prompt,
            model_settings=ModelSettings(temperature=0.0),
        )
        result = await agent.run(user_content)
        return result.output

    async def aclose(self) -> None:
        if self._http_client is not None:
            await self._http_client.aclose()

    def _get_model(self) -> OpenAIChatModel:
        if self._model is None:
            if not self.settings.openrouter_api_key:
                raise RuntimeError(
                    "OPENROUTER_API_KEY is required to call the classifier"
                )

            headers: dict[str, str] = {}
            if self.settings.openrouter_site_url:
                headers["HTTP-Referer"] = self.settings.openrouter_site_url
            if self.settings.openrouter_app_name:
                headers["X-Title"] = self.settings.openrouter_app_name

            self._http_client = httpx.AsyncClient(headers=headers, timeout=120.0)
            provider = OpenAIProvider(
                base_url=self.settings.openrouter_base_url,
                api_key=self.settings.openrouter_api_key,
                http_client=self._http_client,
            )
            self._model = OpenAIChatModel(
                self.settings.openrouter_model, provider=provider
            )

        return self._model
