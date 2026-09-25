"""
Tests for OpenAPI Documentation Management feature.
Covers uploading, editing, validating, saving, and runtime validator integration.
"""

import json
import os
import tempfile
import pytest
from fastapi.testclient import TestClient

from dashboard.app import app, validate_openapi_content, get_active_spec_path
from api_sentinel.config import settings
from api_sentinel.openapi_parser import OpenAPIParser, load_openapi_spec
from api_sentinel.validator import ContractValidator, RuntimeData
from api_sentinel.validation_report import ValidationStatus


VALID_OPENAPI_YAML = """
openapi: 3.0.3
info:
  title: Test Petstore API
  version: 2.1.0
  description: Sample API for testing documentation management
paths:
  /pets:
    get:
      summary: List all pets
      responses:
        '200':
          description: A paged array of pets
          content:
            application/json:
              schema:
                type: array
                items:
                  type: object
                  required: [id, name]
                  properties:
                    id:
                      type: integer
                    name:
                      type: string
  /pets/{petId}:
    get:
      summary: Info for a specific pet
      parameters:
        - name: petId
          in: path
          required: true
          schema:
            type: integer
      responses:
        '200':
          description: Expected response to a valid request
          content:
            application/json:
              schema:
                type: object
                required: [id, name]
                properties:
                  id:
                    type: integer
                  name:
                    type: string
"""

VALID_OPENAPI_JSON = json.dumps({
    "openapi": "3.0.3",
    "info": {
        "title": "JSON Inventory API",
        "version": "1.5.0",
        "description": "JSON based spec"
    },
    "paths": {
        "/items": {
            "get": {
                "summary": "Get all items",
                "responses": {
                    "200": {
                        "description": "List of items",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "array",
                                    "items": {
                                        "type": "string"
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
})


@pytest.fixture
def client():
    return TestClient(app)


# ===========================================================================
# 1. UI Page & Navigation Tests
# ===========================================================================

def test_openapi_docs_page_renders(client):
    """Confirm the OpenAPI Documentation page renders with 200 OK and expected UI elements."""
    response = client.get("/openapi-docs")
    assert response.status_code == 200
    assert "<!DOCTYPE html>" in response.text
    assert "OpenAPI Specification Management" in response.text
    assert "spec-editor" in response.text
    assert "btn-validate" in response.text
    assert "btn-save" in response.text


def test_dashboard_has_openapi_docs_navigation(client):
    """Confirm Dashboard index page contains navigation link to /openapi-docs."""
    response = client.get("/")
    assert response.status_code == 200
    assert 'href="/openapi-docs"' in response.text
    assert "OpenAPI Docs" in response.text


# ===========================================================================
# 2. Validation Helper Tests
# ===========================================================================

def test_validate_valid_yaml_content():
    """Valid YAML specification produces valid=True with parsed summary."""
    is_valid, summary, error = validate_openapi_content(VALID_OPENAPI_YAML)
    assert is_valid is True
    assert error is None
    assert summary is not None
    assert summary["title"] == "Test Petstore API"
    assert summary["version"] == "2.1.0"
    assert summary["openapi_version"] == "3.0.3"
    assert summary["paths_count"] == 2
    assert len(summary["endpoints"]) == 2
    paths = [ep["path"] for ep in summary["endpoints"]]
    assert "/pets" in paths
    assert "/pets/{petId}" in paths


def test_validate_valid_json_content():
    """Valid JSON specification produces valid=True with parsed summary."""
    is_valid, summary, error = validate_openapi_content(VALID_OPENAPI_JSON)
    assert is_valid is True
    assert error is None
    assert summary["title"] == "JSON Inventory API"
    assert summary["version"] == "1.5.0"
    assert summary["paths_count"] == 1


def test_validate_empty_content():
    """Empty content should be rejected with error."""
    is_valid, summary, error = validate_openapi_content("")
    assert is_valid is False
    assert "cannot be empty" in error.lower()


def test_validate_malformed_syntax():
    """Malformed YAML/JSON syntax should be rejected."""
    bad_yaml = "openapi: 3.0.3\ninfo: {title: 'unclosed"
    is_valid, summary, error = validate_openapi_content(bad_yaml)
    assert is_valid is False
    assert "syntax" in error.lower() or "yaml" in error.lower()


def test_validate_missing_openapi_version():
    """OpenAPI doc missing openapi/swagger field should be rejected."""
    no_version_yaml = "info:\n  title: No Version\n  version: 1.0\npaths: {}\n"
    is_valid, summary, error = validate_openapi_content(no_version_yaml)
    assert is_valid is False
    assert "version field" in error.lower()


def test_validate_missing_info_section():
    """OpenAPI doc missing info section should be rejected."""
    no_info_yaml = "openapi: 3.0.3\npaths: {}\n"
    is_valid, summary, error = validate_openapi_content(no_info_yaml)
    assert is_valid is False
    assert "info" in error.lower()


def test_validate_missing_paths_section():
    """OpenAPI doc missing paths section should be rejected."""
    no_paths_yaml = "openapi: 3.0.3\ninfo:\n  title: Test\n  version: 1.0\n"
    is_valid, summary, error = validate_openapi_content(no_paths_yaml)
    assert is_valid is False
    assert "paths" in error.lower()


# ===========================================================================
# 3. API Endpoint Tests
# ===========================================================================

def test_api_openapi_current(client):
    """GET /api/openapi/current returns current specification."""
    response = client.get("/api/openapi/current")
    assert response.status_code == 200
    data = response.json()
    assert "content" in data
    assert "format" in data
    assert "valid" in data
    assert data["valid"] is True
    assert "summary" in data


def test_api_openapi_validate_valid(client):
    """POST /api/openapi/validate returns valid=True for valid content."""
    response = client.post(
        "/api/openapi/validate",
        json={"content": VALID_OPENAPI_YAML}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert data["summary"]["title"] == "Test Petstore API"
    assert data["error"] is None


def test_api_openapi_validate_invalid(client):
    """POST /api/openapi/validate returns valid=False for invalid content."""
    response = client.post(
        "/api/openapi/validate",
        json={"content": "invalid: - syntax: [missing"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is False
    assert data["error"] is not None


def test_api_openapi_save_and_persistence(client, tmp_path, monkeypatch):
    """Saving a valid specification writes to disk and persists for runtime use."""
    temp_spec_file = tmp_path / "custom_openapi.yaml"
    temp_spec_file.write_text("openapi: 3.0.3\ninfo:\n  title: Initial\n  version: '1.0'\npaths: {}\n")

    # Point openapi_spec_path to temporary file
    monkeypatch.setattr(settings, "openapi_spec_path", str(temp_spec_file))

    # Save new valid spec
    response = client.post(
        "/api/openapi/save",
        json={"content": VALID_OPENAPI_YAML}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "saved"
    assert data["summary"]["title"] == "Test Petstore API"

    # Verify content was persisted to disk
    persisted_content = temp_spec_file.read_text(encoding="utf-8")
    assert "Test Petstore API" in persisted_content

    # Confirm OpenAPIParser can load the saved specification from file
    parser = OpenAPIParser.from_file(str(temp_spec_file))
    assert parser.spec["info"]["title"] == "Test Petstore API"
    assert "/pets/{petId}" in parser.paths

    # Confirm ContractValidator functions with the persisted specification
    validator = ContractValidator.from_file(str(temp_spec_file))
    runtime_data = RuntimeData(
        method="GET",
        path="/pets/123",
        status_code=200,
        response_body={"id": 123, "name": "Buddy"}
    )
    report = validator.validate(runtime_data)
    assert report.status == ValidationStatus.PASSED


def test_api_openapi_save_rejects_invalid(client, tmp_path, monkeypatch):
    """Saving invalid specification is rejected with HTTP 400 and preserves original file."""
    temp_spec_file = tmp_path / "original_openapi.yaml"
    original_text = "openapi: 3.0.3\ninfo:\n  title: Original\n  version: '1.0'\npaths: {}\n"
    temp_spec_file.write_text(original_text)

    monkeypatch.setattr(settings, "openapi_spec_path", str(temp_spec_file))

    response = client.post(
        "/api/openapi/save",
        json={"content": "openapi: invalid yaml [[[ {"}
    )
    assert response.status_code == 400
    data = response.json()
    assert data["status"] == "error"

    # Original file remains unmodified
    assert temp_spec_file.read_text() == original_text
