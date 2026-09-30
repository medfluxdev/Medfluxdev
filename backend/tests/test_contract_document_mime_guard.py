"""Document download guards: MIME-extension pairing and invalid suffix ranges."""
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.routes import contracts


@pytest.mark.parametrize("extension,mime", [
    (".pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    (".docx", "application/pdf"),
])
def test_document_download_rejects_mismatched_extension_and_mime(monkeypatch, extension, mime):
    org_id, contract_id, version_id = uuid4(), uuid4(), uuid4()
    session = MagicMock()
    version = SimpleNamespace(document_file_id=uuid4())
    session.scalars.return_value.first.return_value = version
    session.get.return_value = SimpleNamespace(file_extension=extension, mime_type=mime)
    monkeypatch.setattr(contracts, "create_session", lambda: session)
    monkeypatch.setattr(contracts, "get_organization", lambda *_: SimpleNamespace(id=org_id))
    monkeypatch.setattr(contracts, "_scope_denies", lambda *_: False)
    monkeypatch.setattr(contracts, "DocumentPersistenceService", MagicMock)
    request = SimpleNamespace(
        state=SimpleNamespace(actor=SimpleNamespace(organization_id=org_id)),
        headers={},
    )
    with pytest.raises(HTTPException) as exc:
        contracts.contract_document_content(request, "hospital", str(contract_id), str(version_id))
    assert exc.value.status_code == 415
    session.close.assert_called_once()
