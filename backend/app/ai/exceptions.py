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

    def __init__(self, user_message: str = "Die lokale KI ist derzeit nicht verfügbar.") -> None:
        super().__init__(user_message)


class AIModelMissingError(AIProviderError):
    """Ollama läuft, aber das konfigurierte Modell fehlt."""

    def __init__(self, model: str) -> None:
        super().__init__(f"Das lokale KI-Modell {model} ist nicht installiert.")
        self.model = model


class AITimeoutError(AIProviderError):
    """Anfrage hat das konfigurierte Zeitlimit überschritten."""

    def __init__(self) -> None:
        self.category = "timeout"
        super().__init__("Die lokale KI hat nicht rechtzeitig geantwortet (Zeitüberschreitung).")


class AIHTTPError(AIProviderError):
    """Ollama hat mit einem HTTP-Fehler geantwortet.

    `category` ist eine streng begrenzte, inhaltsfreie Fehlerklasse (z. B.
    `invalid_schema`), damit ein HTTP-Fehler in Diagnose und Oberfläche nicht als
    undurchsichtiges `AIHTTPError` endet. Der rohe Antworttext wird bewusst
    nicht übernommen, weil er angeforderte Inhalte enthalten kann.
    """

    MESSAGES = {
        "invalid_schema": (
            "Die lokale KI hat die strukturierte Ausgabe-Anweisung abgelehnt."
        ),
        "insufficient_memory": (
            "Das KI-Modell benötigt mehr Arbeitsspeicher als verfügbar."
        ),
        "model_runner_stopped": (
            "Das KI-Modell wurde beim Ausführen unerwartet beendet "
            "(Speicher- oder Laufzeitproblem)."
        ),
    }

    def __init__(self, status_code: int, category: str | None = None) -> None:
        self.status_code = status_code
        self.category = category
        super().__init__(
            self.MESSAGES.get(
                category or "", "Die lokale KI hat einen Fehler zurückgegeben."
            )
        )


class AIMalformedResponseError(AIProviderError):
    """Die Antwort von Ollama war kein gültiges JSON-Format."""

    def __init__(self) -> None:
        self.category = "malformed_response"
        super().__init__("Die lokale KI hat eine ungültige Antwort geliefert.")


class AIEmptyResponseError(AIProviderError):
    """Die Antwort von Ollama enthielt keinen Text."""

    def __init__(self) -> None:
        self.category = "empty_response"
        super().__init__("Die lokale KI hat keine Antwort geliefert.")
