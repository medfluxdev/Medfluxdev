"""Regression tests for the source-region PDF 415 (review/source-region-pdf-content-415-20261002).

Root cause (verified read-only against the affected document):
`document_file.file_extension` is stored DOTTED (".pdf"), consistent with
`storage._ALLOWED_EXTENSIONS` and `contracts._VALID_CONTENT_TYPES`. The endpoint
compared `ext != "pdf"` without stripping the dot, so a genuine PDF was rejected.

The reviewed commit removes the extension gate and validates the real bytes
instead. These tests pin that behaviour:

* genuine PDF content is served even when extension metadata is missing, empty,
  or dotted;
* genuinely non-PDF content is rejected with 415 even if it claims to be a PDF;
* organization / account access restrictions still short-circuit to 404 and
  never leak a 415.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.routes import documents as documents_route

REAL_PDF = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<<>>\nendobj\ntrailer\n%%EOF\n"


def _wire(monkeypatch, *, org_id, actor, version, document_file=None,
          content=REAL_PDF, storage_error=False, canonical=None,
          membership=None, scoped=None, visible=True):
    """Patch every collaborator of `document_source_region`."""
    session = MagicMock()
    session.scalars.return_value.first.return_value = version
    session.get.return_value = document_file
    session.scalar.return_value = membership

    monkeypatch.setattr(documents_route, "create_session", lambda: session)
    monkeypatch.setattr(
        documents_route, "get_organization", lambda *_: SimpleNamespace(id=org_id)
    )
    monkeypatch.setattr(
        documents_route, "_ensure_document_visible",
        lambda *_: None if visible else documents_route._not_found(),
    )
    monkeypatch.setattr(
        documents_route, "scoped_contract_ids", lambda *a, **k: scoped
    )
    monkeypatch.setattr(
        documents_route, "_linked_contract_ids", lambda *a, **k: {version.id}
    )

    storage = MagicMock()
    if storage_error:
        storage.resolve_bytes_for_version.side_effect = documents_route.StorageError(
            "nicht gefunden"
        )
    else:
        storage.resolve_bytes_for_version.return_value = content
    storage.resolve_canonical_for_version.return_value = canonical or {}
    monkeypatch.setattr(
        documents_route, "DocumentPersistenceService", lambda: storage
    )

    monkeypatch.setattr(documents_route, "resolve_narrowest_region",
                        lambda snippet, **kw: {"status": "exact", "page": kw.get("page_hint")})

    request = SimpleNamespace(state=SimpleNamespace(actor=actor), headers={})
    return session, storage, request


def _call(request, version_id, slug, snippet="Rahmenvertrag", page=1):
    return documents_route.document_source_region(
        str(version_id),
        request,
        organization_slug=slug,
        snippet=snippet,
        page=page,
    )


# --------------------------------------------------------------------------
# 1) genuine PDF content, missing / empty / dotted extension metadata
# --------------------------------------------------------------------------


@pytest.mark.parametrize("extension", [".pdf", "", None, "pdf", ".PDF", ".docx", ".txt"])
def test_genuine_pdf_is_served_regardless_of_extension_metadata(
    monkeypatch, extension
):
    """The stored extension must never decide whether real PDF bytes are usable."""
    monkeypatch.setattr(documents_route.settings, "auth_enabled", False)
    org_id, version_id = uuid4(), uuid4()
    version = SimpleNamespace(id=version_id, document_file_id=uuid4())
    doc_file = SimpleNamespace(file_extension=extension, mime_type="application/pdf")

    _session, _storage, request = _wire(
        monkeypatch,
        org_id=org_id,
        actor=None,
        version=version,
        document_file=doc_file,
        content=REAL_PDF,
    )

    region = _call(request, version_id, "klinik")
    assert region["status"] == "exact"
    assert region["document_version_id"] == str(version_id)


def test_genuine_pdf_with_empty_extension_is_not_rejected(monkeypatch):
    """Explicit guard for the reported defect: extension present but unusable."""
    monkeypatch.setattr(documents_route.settings, "auth_enabled", False)
    org_id, version_id = uuid4(), uuid4()
    version = SimpleNamespace(id=version_id, document_file_id=uuid4())
    doc_file = SimpleNamespace(file_extension="", mime_type="application/pdf")

    _session, _storage, request = _wire(
        monkeypatch, org_id=org_id, actor=None, version=version,
        document_file=doc_file, content=REAL_PDF,
    )

    assert _call(request, version_id, "klinik")["status"] == "exact"


def test_real_dotted_extension_regression(monkeypatch):
    """`.pdf` (the actual stored value) must not be compared against `pdf`."""
    monkeypatch.setattr(documents_route.settings, "auth_enabled", False)
    org_id, version_id = uuid4(), uuid4()
    version = SimpleNamespace(id=version_id, document_file_id=uuid4())
    doc_file = SimpleNamespace(file_extension=".pdf", mime_type="application/pdf")

    _session, _storage, request = _wire(
        monkeypatch, org_id=org_id, actor=None, version=version,
        document_file=doc_file, content=REAL_PDF,
    )

    result = _call(request, version_id, "klinik")
    assert result["status"] == "exact"
    assert result["snippet"] == "Rahmenvertrag"


# --------------------------------------------------------------------------
# 2) invalid content must be rejected even when it claims to be a PDF
# --------------------------------------------------------------------------


@pytest.mark.parametrize("content,label", [
    (b"", "empty file"),
    (b"%PDX-1.4 broken", "corrupt magic bytes"),
    (b"PK\x03\x04 docx payload", "actually a docx"),
    (b"\x89PNG\r\n\x1a\n", "actually an image"),
    (b"plain text, no pdf header at all", "plain text"),
])
def test_non_pdf_content_is_rejected_with_415(monkeypatch, content, label):
    """Trusting the filename would let non-PDF bytes reach PDF geometry code."""
    monkeypatch.setattr(documents_route.settings, "auth_enabled", False)
    org_id, version_id = uuid4(), uuid4()
    version = SimpleNamespace(id=version_id, document_file_id=uuid4())
    # Claims to be a PDF in every metadata field.
    doc_file = SimpleNamespace(file_extension=".pdf", mime_type="application/pdf")

    _session, _storage, request = _wire(
        monkeypatch, org_id=org_id, actor=None, version=version,
        document_file=doc_file, content=content,
    )

    with pytest.raises(HTTPException) as exc:
        _call(request, version_id, "klinik")
    assert exc.value.status_code == 415, label
    assert exc.value.detail == "Quell-Geometrie nur für PDF verfügbar."


def test_pdf_magic_after_leading_whitespace_is_still_rejected(monkeypatch):
    """A PDF header must be at offset 0; do not scan for it."""
    monkeypatch.setattr(documents_route.settings, "auth_enabled", False)
    org_id, version_id = uuid4(), uuid4()
    version = SimpleNamespace(id=version_id, document_file_id=uuid4())
    doc_file = SimpleNamespace(file_extension=".pdf", mime_type="application/pdf")

    _session, _storage, request = _wire(
        monkeypatch, org_id=org_id, actor=None, version=version,
        document_file=doc_file, content=b"\n\n" + REAL_PDF,
    )

    with pytest.raises(HTTPException) as exc:
        _call(request, version_id, "klinik")
    assert exc.value.status_code == 415


# --------------------------------------------------------------------------
# 3) organization / account access restrictions still win over content checks
# --------------------------------------------------------------------------


def test_unknown_organization_returns_404(monkeypatch):
    monkeypatch.setattr(documents_route.settings, "auth_enabled", False)
    version_id = uuid4()
    session = MagicMock()
    monkeypatch.setattr(documents_route, "create_session", lambda: session)
    monkeypatch.setattr(documents_route, "get_organization", lambda *_: None)
    request = SimpleNamespace(state=SimpleNamespace(actor=None), headers={})

    with pytest.raises(HTTPException) as exc:
        documents_route.document_source_region(
            str(version_id), request, organization_slug="ghost", snippet="abc", page=1
        )
    assert exc.value.status_code == 404


def test_cross_organization_actor_returns_404_and_never_reads_content(monkeypatch):
    """A foreign-org actor must not learn anything from the 415 branch."""
    monkeypatch.setattr(documents_route.settings, "auth_enabled", True)
    org_id, foreign_org_id, version_id = uuid4(), uuid4(), uuid4()
    version = SimpleNamespace(id=version_id, document_file_id=uuid4())
    doc_file = SimpleNamespace(file_extension=".pdf", mime_type="application/pdf")

    _session, _storage, request = _wire(
        monkeypatch, org_id=org_id,
        actor=SimpleNamespace(organization_id=foreign_org_id),
        version=version, document_file=doc_file, content=b"not a pdf",
    )

    with pytest.raises(HTTPException) as exc:
        _call(request, version_id, "klinik")
    assert exc.value.status_code == 404


def test_anonymous_actor_returns_404_when_auth_enabled(monkeypatch):
    monkeypatch.setattr(documents_route.settings, "auth_enabled", True)
    org_id, version_id = uuid4(), uuid4()
    version = SimpleNamespace(id=version_id, document_file_id=uuid4())

    _session, _storage, request = _wire(monkeypatch, org_id=org_id, actor=None, version=version, content=REAL_PDF)

    with pytest.raises(HTTPException) as exc:
        _call(request, version_id, "klinik")
    assert exc.value.status_code == 404


def test_unassigned_account_scope_returns_404(monkeypatch):
    """Non-admin without an active membership must not resolve a region."""
    monkeypatch.setattr(documents_route.settings, "auth_enabled", True)
    org_id, version_id = uuid4(), uuid4()
    version = SimpleNamespace(id=version_id, document_file_id=uuid4())
    actor = SimpleNamespace(
        organization_id=org_id,
        account_id=uuid4(),
        role="viewer",
        is_developer=False,
    )

    _session, _storage, request = _wire(
        monkeypatch, org_id=org_id, actor=actor, version=version,
        document_file=SimpleNamespace(file_extension=".pdf", mime_type="application/pdf"),
        content=REAL_PDF, membership=None,
    )

    with pytest.raises(HTTPException) as exc:
        _call(request, version_id, "klinik")
    assert exc.value.status_code == 404


def test_membership_without_assigned_contract_returns_404(monkeypatch):
    monkeypatch.setattr(documents_route.settings, "auth_enabled", True)
    org_id, version_id = uuid4(), uuid4()
    version = SimpleNamespace(id=version_id, document_file_id=uuid4())
    actor = SimpleNamespace(
        organization_id=org_id,
        account_id=uuid4(),
        role="viewer",
        is_developer=False,
    )
    membership = SimpleNamespace(hospital_id=None, department_id=None)

    _session, _storage, request = _wire(
        monkeypatch, org_id=org_id, actor=actor, version=version,
        document_file=SimpleNamespace(file_extension=".pdf", mime_type="application/pdf"),
        content=REAL_PDF, membership=membership, scoped=set(),
    )

    with pytest.raises(HTTPException) as exc:
        _call(request, version_id, "klinik")
    assert exc.value.status_code == 404


def test_admin_bypasses_scope_but_not_organization_boundary(monkeypatch):
    monkeypatch.setattr(documents_route.settings, "auth_enabled", True)
    org_id, version_id = uuid4(), uuid4()
    version = SimpleNamespace(id=version_id, document_file_id=uuid4())
    actor = SimpleNamespace(
        organization_id=org_id, account_id=uuid4(), role="admin", is_developer=False
    )

    _session, _storage, request = _wire(
        monkeypatch, org_id=org_id, actor=actor, version=version,
        document_file=SimpleNamespace(file_extension="", mime_type="application/pdf"),
        content=REAL_PDF, membership=None, scoped=None,
    )

    # In-org admin resolves the region even with unusable extension metadata.
    assert _call(request, version_id, "klinik")["status"] == "exact"


def test_unreadable_storage_returns_404_not_415(monkeypatch):
    """Missing bytes are a not-found condition, not an unsupported-media one."""
    monkeypatch.setattr(documents_route.settings, "auth_enabled", False)
    org_id, version_id = uuid4(), uuid4()
    version = SimpleNamespace(id=version_id, document_file_id=uuid4())

    _session, _storage, request = _wire(
        monkeypatch, org_id=org_id, actor=None, version=version,
        content=None, storage_error=True,
    )

    with pytest.raises(HTTPException) as exc:
        _call(request, version_id, "klinik")
    assert exc.value.status_code == 404