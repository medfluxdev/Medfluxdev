"""Ollama-Provider – ausschließlich lokale Kommunikation über die Ollama-API.

Es werden nur die lokalen Endpunkte `/api/tags` (Modell-Liste), `/api/show`
(Modell-Metadaten) und `/api/chat` (Generierung) verwendet. Keine externen
Netzwerkaufrufe. Modell-Fähigkeiten werden aus autoritativen Metadaten
(`model_info` aus `/api/show`) abgeleitet – nie aus Modell-Namen.
"""

import contextlib
import hashlib
import json
import logging
from typing import Any

import httpx

from app.ai.base import AIProvider
from app.ai.exceptions import (
    AIEmptyResponseError,
    AIHTTPError,
    AIMalformedResponseError,
    AIModelMissingError,
    AITimeoutError,
    AIUnavailableError,
)
from app.ai.schemas import AIStatus, ModelCapabilities, ModelDescriptor, ModelInfo
from app.core.config import Settings

logger = logging.getLogger(__name__)

MSG_OK = "Lokale KI verfügbar."
MSG_UNAVAILABLE = "Die lokale KI ist derzeit nicht verfügbar."
MSG_TIMEOUT = "Die lokale KI hat nicht rechtzeitig geantwortet (Zeitüberschreitung)."

# Familien, die NUR Einbettungen liefern (kein Chat).
EMBEDDING_ONLY_FAMILIES = {
    "all-minilm",
    "snowflake-arctic-embed",
    "nomic-embed",
    "mxbai-embed",
    "bge-m3",
    "nomic",
}

# Familien mit autoritativem Vision-/Multimodal-Support laut Ollama-Metadaten.
# Rein informatorisch – primär wird `model_info` mit `*.vision.*`-Schlüsseln
# ausgewertet (autoritative Quelle).
VISION_FAMILIES = {
    "qwen3vl",
    "qwen2vl",
    "llava",
    "llava-phi3",
    "bakllava",
    "command-r-v",
    "moondream",
    "minicpmv",
    "internvl",
    "gemma3",
    "llava-next",
}

MAX_SHOW_ENRICHMENT = 40


class OllamaProvider(AIProvider):
    """Lokale KI über eine laufende Ollama-Instanz."""

    provider_id = "ollama"
    display_name = "Ollama"
    kind = "native"
    supports_structured_output = True

    def __init__(
        self,
        settings: Settings,
        model_resolver=None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(settings, model_resolver=model_resolver, client=client)
        # Per-request metadata only; never retain raw contract/model content.
        self.last_done_reason = None
        self.last_usage: dict[str, Any] = {}
        self.last_response_sha256: str | None = None
        self.last_response_chars: int = 0

    @contextlib.asynccontextmanager
    async def _get_client(self):
        if self._client is not None:
            yield self._client
        else:
            # Getrennte Zeitlimits: Connect/Write/Pool duerfen niemals eine
            # legitime langlaufende Generierung abwuergen; nur der Read-Budget
            # ist das (konfigurierte) Gesamtzeitlimit einer Antwort.
            timeout = httpx.Timeout(
                connect=10.0,
                read=self.settings.ai_request_timeout_seconds,
                write=30.0,
                pool=60.0,
            )
            async with httpx.AsyncClient(timeout=timeout) as c:
                yield c

    @property
    def _base_url(self) -> str:
        return self.settings.ollama_base_url.rstrip("/")

    async def _json_get(self, path: str) -> dict[str, Any]:
        async with self._get_client() as client:
            try:
                resp = await client.get(f"{self._base_url}{path}")
            except httpx.TimeoutException as exc:
                logger.warning("Ollama %s Timeout: %s", path, exc)
                raise AITimeoutError() from exc
            except httpx.HTTPError as exc:
                logger.warning("Ollama %s nicht erreichbar: %s", path, exc)
                raise AIUnavailableError() from exc
        if resp.status_code != 200:
            raise AIHTTPError(resp.status_code)
        try:
            data = resp.json()
        except ValueError as exc:
            raise AIMalformedResponseError() from exc
        if not isinstance(data, dict):
            raise AIMalformedResponseError()
        return data

    async def _json_post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        async with self._get_client() as client:
            try:
                resp = await client.post(f"{self._base_url}{path}", json=payload)
            except httpx.TimeoutException as exc:
                logger.warning("Ollama %s Timeout: %s", path, exc)
                raise AITimeoutError() from exc
            except httpx.HTTPError as exc:
                logger.warning("Ollama %s nicht erreichbar: %s", path, exc)
                raise AIUnavailableError() from exc
        if resp.status_code != 200:
            raise AIHTTPError(resp.status_code)
        try:
            data = resp.json()
        except ValueError as exc:
            raise AIMalformedResponseError() from exc
        if not isinstance(data, dict):
            raise AIMalformedResponseError()
        return data

    async def _list_models(self) -> list[str]:
        data = await self._json_get("/api/tags")
        models = data.get("models", [])
        return [m.get("name", "") for m in models if isinstance(m, dict)]

    async def model_info(self) -> ModelInfo:
        models = await self._list_models()
        return ModelInfo(
            name=self._model(),
            available=self._model() in models,
        )

    async def health_check(self) -> AIStatus:
        model = self._model()
        try:
            models = await self._list_models()
        except AIUnavailableError as exc:
            return AIStatus(
                provider=self.provider_id,
                available=False,
                model=model,
                model_available=False,
                message=exc.user_message,
            )
        except AITimeoutError as exc:
            return AIStatus(
                provider=self.provider_id,
                available=False,
                model=model,
                model_available=False,
                message=exc.user_message,
            )

        model_available = model in models
        if model_available:
            return AIStatus(
                provider=self.provider_id,
                available=True,
                model=model,
                model_available=True,
                message=MSG_OK,
            )
        return AIStatus(
            provider=self.provider_id,
            available=True,
            model=model,
            model_available=False,
            message=f"Das lokale KI-Modell {model} ist nicht installiert.",
        )

    # --------------------------------------------------------------- Erkennung

    async def discover_models(self) -> list[ModelDescriptor]:
        """Modellliste aus /api/tags, angereichert durch /api/show (autoritativ)."""
        data = await self._json_get("/api/tags")
        entries = data.get("models", [])
        tags_models = [e for e in entries if isinstance(e, dict)]
        result: list[ModelDescriptor] = []
        for entry in tags_models[:MAX_SHOW_ENRICHMENT]:
            name = entry.get("name", "")
            if not name:
                continue
            details = entry.get("details") if isinstance(entry.get("details"), dict) else {}
            try:
                show = await self._json_post("/api/show", {"model": name})
            except (AIUnavailableError, AITimeoutError, AIHTTPError, AIMalformedResponseError):
                show = {}
            result.append(self._descriptor_from_show(name, details, show))
        return result

    @staticmethod
    def _descriptor_from_show(
        name: str, details: dict[str, Any], show: dict[str, Any]
    ) -> ModelDescriptor:
        model_info = show.get("model_info") if isinstance(show.get("model_info"), dict) else {}
        show_details = show.get("details") if isinstance(show.get("details"), dict) else {}
        details = {**(show_details or {}), **(details or {})}

        caps = ModelCapabilities()
        arch = model_info.get("general.architecture") if isinstance(model_info, dict) else None
        family = details.get("family")

        # Text-/Chat-Fähigkeit: autoritativ über die Familie (Embedding-only
        # Modelle können nicht chatten); unbekannt, wenn keine Details vorliegen.
        if family is not None:
            caps.text = family not in EMBEDDING_ONLY_FAMILIES

        # Vision: autoritativ über `{arch}.vision.*`-Metadaten von /api/show.
        # FEHLT die Metadaten-Quelle, bleibt die Fähigkeit unbekannt (None).
        # Familien-Liste ist nur eine unterstützende Quelle – nie aus Namen.
        if isinstance(model_info, dict) and any(
            isinstance(key, str) and ".vision." in key for key in model_info
        ):
            caps.vision = True
        elif caps.vision is None and family in VISION_FAMILIES:
            caps.vision = True
        elif caps.vision is None and arch in VISION_FAMILIES:
            caps.vision = True

        if family in EMBEDDING_ONLY_FAMILIES:
            caps.embedding = True

        context_length = None
        if isinstance(model_info, dict):
            for key, val in model_info.items():
                if (
                    isinstance(key, str)
                    and key.endswith("context_length")
                    and isinstance(val, (int, float))
                ):
                    context_length = int(val)
                    break

        return ModelDescriptor(
            provider_id="ollama",
            model_id=name,
            display_name=None,
            state="available",
            loaded=None,
            context_length=context_length,
            quantization=details.get("quantization_level"),
            family=family,
            parameter_size=details.get("parameter_size"),
            capabilities=caps,
        )

    # ------------------------------------------------------------- Generierung

    def _options(self, max_tokens: int | None) -> dict[str, Any]:
        options: dict[str, Any] = {
            "temperature": self.settings.ai_temperature,
            "num_predict": max_tokens or self.settings.ai_max_tokens,
        }
        rp = self.settings.ai_repeat_penalty
        if rp is not None and rp > 0:
            options["repeat_penalty"] = rp
        if self.settings.ollama_num_gpu is not None:
            options["num_gpu"] = int(self.settings.ollama_num_gpu)
        return options

    def _payload(
        self,
        messages: list[dict[str, Any]],
        options: dict[str, Any],
        schema: dict[str, Any] | None,
        *,
        stream: bool = True,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self._model(),
            "messages": messages,
            "stream": stream,
            "think": self.settings.ollama_think,
            "options": options,
        }
        if schema is not None:
            payload["format"] = schema
        keep_alive = getattr(self.settings, "ollama_keep_alive", "") or ""
        if keep_alive and keep_alive != "0":
            payload["keep_alive"] = keep_alive
        return payload

    async def generate(
        self, text: str, system_prompt: str, max_tokens: int | None = None
    ) -> str:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ]
        return await self._chat(
            self._payload(messages, self._options(max_tokens), None, stream=False)
        )

    async def generate_structured(
        self,
        text: str,
        system_prompt: str,
        schema: dict[str, Any],
        max_tokens: int | None = None,
    ) -> str:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ]
        # Native strukturierte Ausgabe: Ollama erzwingt die Struktur/Enums
        # des übergebenen (selbstenthaltenen) JSON-Schemas.
        return await self._chat(
            self._payload(messages, self._options(max_tokens), schema)
        )

    async def generate_request(self, text, system_prompt, schema, max_tokens,
                               context_tokens, images=None) -> str:
        user = {"role": "user", "content": text}
        if images:
            user["images"] = images
        options = self._options(max_tokens)
        # Harness calls are schema-constrained extraction/verification tasks.
        # Ollama recommends low temperature for reliable structured output; keep
        # ordinary chat/generation settings unchanged.
        options["temperature"] = 0.0
        options["num_ctx"] = int(context_tokens)
        return await self._chat(
            self._payload(
                [{"role": "system", "content": system_prompt}, user],
                options,
                schema,
            )
        )

    async def _chat(self, payload: dict[str, Any]) -> str:
        model = self._model()
        async with self._get_client() as client:
            try:
                resp = await client.post(f"{self._base_url}/api/chat", json=payload)
            except httpx.TimeoutException as exc:
                logger.warning("Ollama /api/chat Timeout (Modell %s): %s", model, exc)
                raise AITimeoutError() from exc
            except httpx.HTTPError as exc:
                logger.warning("Ollama /api/chat nicht erreichbar (Modell %s): %s", model, exc)
                raise AIUnavailableError() from exc

        if resp.status_code == 404:
            raise AIModelMissingError(model)
        if resp.status_code != 200:
            raise AIHTTPError(resp.status_code)

        # Streaming (stream=true): NDJSON-Zeilen, Token fuer Token. Der Read-
        # Timeout gilt so nur fuer die Zeit zwischen zwei eingehenden Zeilen;
        # eine langsam aber voranschreitende Generierung wird nie abgewuergt.
        # Ein einzelnes JSON-Objekt (Legacy-/Test-Mock) wird als eine Zeile
        # erkannt und identisch verarbeitet.
        content_parts: list[str] = []
        done_reason: Any = None
        usage: dict[str, Any] = {}
        parsed_any = False
        try:
            async for line in resp.aiter_lines():
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    chunk = json.loads(stripped)
                except ValueError:
                    continue
                if not isinstance(chunk, dict):
                    continue
                parsed_any = True
                message = chunk.get("message")
                if isinstance(message, dict):
                    piece = message.get("content")
                    if isinstance(piece, str) and piece:
                        content_parts.append(piece)
                if chunk.get("done"):
                    done_reason = chunk.get("done_reason")
                    usage = {
                        "prompt_tokens": chunk.get("prompt_eval_count"),
                        "completion_tokens": chunk.get("eval_count"),
                    }
        except httpx.TimeoutException as exc:
            logger.warning("Ollama /api/chat Timeout (Modell %s): %s", model, exc)
            raise AITimeoutError() from exc
        except httpx.HTTPError as exc:
            logger.warning("Ollama /api/chat nicht erreichbar (Modell %s): %s", model, exc)
            raise AIUnavailableError() from exc

        self.last_done_reason = done_reason
        self.last_usage = usage
        rendered = "".join(content_parts).strip()
        if rendered:
            self.last_response_sha256 = hashlib.sha256(rendered.encode("utf-8")).hexdigest()
            self.last_response_chars = len(rendered)
            return rendered

        self.last_response_sha256 = None
        self.last_response_chars = 0
        if not parsed_any:
            raise AIMalformedResponseError()
        raise AIEmptyResponseError()


async def detect_ollama(client: httpx.AsyncClient, base_url: str) -> bool:
    """Ob eine lokale Ollama-Instanz unter `base_url` läuft (nativer Fingerabdruck)."""
    try:
        resp = await client.get(f"{base_url.rstrip('/')}/api/tags")
    except (httpx.TimeoutException, httpx.HTTPError):
        return False
    if resp.status_code != 200:
        return False
    try:
        data = resp.json()
    except ValueError:
        return False
    if not isinstance(data, dict) or not isinstance(data.get("models"), list):
        return False
    return True


def build_ollama_provider(
    settings: Settings,
    model_resolver=None,
    client: httpx.AsyncClient | None = None,
) -> OllamaProvider:
    """Erzeugt einen OllamaProvider aus den zentralen Settings.

    `client` erlaubt das Injizieren eines (gemockten) httpx-Clients in Tests.
    """
    return OllamaProvider(settings, model_resolver=model_resolver, client=client)
