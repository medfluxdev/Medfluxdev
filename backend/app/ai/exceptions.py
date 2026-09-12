"""Saubere interne Fehler für die lokale KI (mit deutschen Nutzer-Meldungen)."""


class AIProviderError(Exception):
    """Basis für alle KI-Provider-Fehler.

    `user_message` ist eine deutsche, nicht-technische Meldung,
    die gefahrlos an die UI weitergereicht werden kann.
    """

    def __init__(self, user_message: str) -> None:
        super().__init__(user_message)
        self.user_message = user_message


class AIUnavailableError(AIProviderError):
    """Ollama ist nicht erreichbar / nicht gestartet."""

    def __init__(self) -> None:
        super().__init__("Die lokale KI ist derzeit nicht verfügbar.")


class AIModelMissingError(AIProviderError):
    """Ollama läuft, aber das konfigurierte Modell fehlt."""

    def __init__(self, model: str) -> None:
        super().__init__(f"Das lokale KI-Modell {model} ist nicht installiert.")
        self.model = model


class AITimeoutError(AIProviderError):
    """Anfrage hat das konfigurierte Zeitlimit überschritten."""

    def __init__(self) -> None:
        super().__init__("Die lokale KI hat nicht rechtzeitig geantwortet (Zeitüberschreitung).")


class AIHTTPError(AIProviderError):
    """Ollama hat mit einem HTTP-Fehler geantwortet."""

    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        super().__init__("Die lokale KI hat einen Fehler zurückgegeben.")


class AIMalformedResponseError(AIProviderError):
    """Die Antwort von Ollama war kein gültiges JSON-Format."""

    def __init__(self) -> None:
        super().__init__("Die lokale KI hat eine ungültige Antwort geliefert.")


class AIEmptyResponseError(AIProviderError):
    """Die Antwort von Ollama enthielt keinen Text."""

    def __init__(self) -> None:
        super().__init__("Die lokale KI hat keine Antwort geliefert.")
