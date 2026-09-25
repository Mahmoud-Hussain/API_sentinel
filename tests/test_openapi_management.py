"""
Tests for OpenAPI Documentation Management and Guided Form-to-YAML Generation.
Covers form data generation, schema mapping, validation, saving, and runtime integration.
"""

import json
import os
import tempfile
import pytest
import yaml
from fastapi.testclient import TestClient

from dashboard.app import app, validate_openapi_content, get_active_spec_path
from api_sentinel.config import settings
from api_sentinel.openapi_parser import OpenAPIParser, load_openapi_spec
from api_sentinel.openapi_generator import generate_openapi_spec, generate_openapi_yaml
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

SAMPLE_FORM_DATA = {
    "openapi_version": "3.0.3",
    "info": {
        "title": "E-Commerce User Service API",
        "version": "1.2.0",
        "description": "API for managing customers and authentication",
        "contact": {"name": "Dev Team", "email": "dev@ecommerce.com"},
        "license": {"name": "MIT", "url": "https://opensource.org/licenses/MIT"}
    },
    "servers": [
        {"url": "https://api.ecommerce.com", "description": "Production Server"},
        {"url": "http://127.0.0.1:8000", "description": "Local Test Server"}
    ],
    "endpoints": [
        {
            "path": "/api/v1/users",
            "method": "GET",
            "summary": "List users",
            "description": "Returns paginated list of users",
            "parameters": [
                {
                    "name": "page",
                    "location": "query",
                    "type": "integer",
                    "required": False,
                    "description": "Page number",
                    "example": 1,
                    "default": 1
                },
                {
                    "name": "role",
                    "location": "query",
                    "type": "string",
                    "required": False,
                    "description": "Filter by role",
                    "example": "admin"
                },
                {
                    "name": "X-Client-Id",
                    "location": "header",
                    "type": "string",
                    "required": True,
                    "description": "Client ID header",
                    "example": "client-123"
                }
            ],
            "request_body": {"enabled": False, "content_type": "application/json", "fields": []},
            "responses": [
                {
                    "status_code": "200",
                    "description": "List of users",
                    "content_type": "application/json",
                    "fields": [
                        {"name": "id", "type": "integer", "required": True, "example": 1},
                        {"name": "name", "type": "string", "required": True, "example": "Alice"},
                        {"name": "email", "type": "string", "required": True, "example": "alice@example.com"}
                    ]
                }
            ]
        },
        {
            "path": "/api/v1/users",
            "method": "POST",
            "summary": "Create user",
            "description": "Register a new user account",
            "parameters": [],
            "request_body": {
                "enabled": True,
                "content_type": "application/json",
                "description": "User registration payload",
                "required": True,
                "fields": [
                    {"name": "name", "type": "string", "required": True, "example": "Bob"},
                    {"name": "email", "type": "string", "required": True, "example": "bob@example.com"},
                    {"name": "age", "type": "integer", "required": False, "example": 28, "default": 18}
                ]
            },
            "responses": [
                {
                    "status_code": "201",
                    "description": "User created successfully",
                    "content_type": "application/json",
                    "fields": [
                        {"name": "id", "type": "integer", "required": True, "example": 2},
                        {"name": "name", "type": "string", "required": True, "example": "Bob"}
                    ]
                },
                {
                    "status_code": "400",
                    "description": "Validation failure",
                    "content_type": "application/json",
                    "fields": [
                        {"name": "error", "type": "string", "required": True, "example": "Invalid email"}
                    ]
                }
            ]
        },
        {
            "path": "/api/v1/users/{id}",
            "method": "DELETE",
            "summary": "Delete user",
            "description": "Deletes a user by ID",
            "parameters": [
                {
                    "name": "id",
                    "location": "path",
                    "type": "integer",
                    "required": True,
                    "description": "User ID",
                    "example": 42
                }
            ],
            "request_body": {"enabled": False},
            "responses": [
                {
                    "status_code": "204",
                    "description": "User deleted successfully",
                    "content_type": ""
                }
            ]
        }
    ]
}


@pytest.fixture
def client():
    return TestClient(app)


# ===========================================================================
# 1. UI Page & Navigation Tests
# ===========================================================================

def test_openapi_docs_page_renders(client):
    """Confirm the OpenAPI Documentation page renders with 200 OK and wizard UI elements."""
    response = client.get("/openapi-docs")
    assert response.status_code == 200
    assert "<!DOCTYPE html>" in response.text
    assert "OpenAPI Guided Builder" in response.text
    assert "step-section-1" in response.text
    assert "btn-load-sample" in response.text
    assert "yaml-preview-editor" in response.text


def test_dashboard_has_openapi_docs_navigation(client):
    """Confirm Dashboard index page contains navigation link to /openapi-docs."""
    response = client.get("/")
    assert response.status_code == 200
    assert 'href="/openapi-docs"' in response.text
    assert "OpenAPI" in response.text


# ===========================================================================
# 2. Form to OpenAPI Generator Unit Tests
# ===========================================================================

def test_generate_basic_api_info():
    """1. Basic API information creates valid OpenAPI data structure."""
    form = {
        "openapi_version": "3.0.3",
        "info": {
            "title": "Inventory Service",
            "version": "2.0.0",
            "description": "Inventory tracking API",
            "contact": {"name": "Ops", "email": "ops@test.com"},
            "license": {"name": "Apache-2.0", "url": "https://www.apache.org/licenses/LICENSE-2.0"}
        },
        "endpoints": []
    }
    spec = generate_openapi_spec(form)
    assert spec["openapi"] == "3.0.3"
    assert spec["info"]["title"] == "Inventory Service"
    assert spec["info"]["version"] == "2.0.0"
    assert spec["info"]["description"] == "Inventory tracking API"
    assert spec["info"]["contact"]["name"] == "Ops"
    assert spec["info"]["license"]["name"] == "Apache-2.0"


def test_generate_servers_information():
    """2. Server information is generated correctly."""
    form = {
        "info": {"title": "Test", "version": "1.0"},
        "servers": [
            {"url": "https://api.prod.com", "description": "Production"},
            {"url": "https://api.stage.com", "description": "Staging"}
        ],
        "endpoints": []
    }
    spec = generate_openapi_spec(form)
    assert "servers" in spec
    assert len(spec["servers"]) == 2
    assert spec["servers"][0]["url"] == "https://api.prod.com"
    assert spec["servers"][0]["description"] == "Production"


def test_generate_endpoints_and_http_methods():
    """3 & 4. Endpoints and various HTTP methods are generated correctly."""
    methods = ["get", "post", "put", "patch", "delete", "head", "options"]
    endpoints = [
        {"path": f"/resource-{m}", "method": m.upper(), "summary": f"{m} resource"}
        for m in methods
    ]
    form = {
        "info": {"title": "Method Test", "version": "1.0"},
        "endpoints": endpoints
    }
    spec = generate_openapi_spec(form)
    for m in methods:
        path_key = f"/resource-{m}"
        assert path_key in spec["paths"]
        assert m.lower() in spec["paths"][path_key]
        assert spec["paths"][path_key][m.lower()]["summary"] == f"{m} resource"


def test_generate_parameters():
    """5. Parameters in path, query, header, and cookie with data types are generated correctly."""
    form = {
        "info": {"title": "Param Test", "version": "1.0"},
        "endpoints": [
            {
                "path": "/items/{itemId}",
                "method": "GET",
                "parameters": [
                    {"name": "itemId", "location": "path", "type": "integer", "required": True, "description": "Item ID", "example": 10},
                    {"name": "q", "location": "query", "type": "string", "required": False, "description": "Search query"},
                    {"name": "X-Trace-Id", "location": "header", "type": "string", "required": False},
                    {"name": "session_id", "location": "cookie", "type": "string", "required": False}
                ]
            }
        ]
    }
    spec = generate_openapi_spec(form)
    op = spec["paths"]["/items/{itemId}"]["get"]
    params = op["parameters"]
    assert len(params) == 4

    p_map = {p["name"]: p for p in params}
    assert p_map["itemId"]["in"] == "path"
    assert p_map["itemId"]["required"] is True
    assert p_map["itemId"]["schema"]["type"] == "integer"
    assert p_map["itemId"]["schema"]["example"] == 10

    assert p_map["q"]["in"] == "query"
    assert p_map["q"]["required"] is False
    assert p_map["q"]["schema"]["type"] == "string"

    assert p_map["X-Trace-Id"]["in"] == "header"
    assert p_map["session_id"]["in"] == "cookie"


def test_generate_request_bodies():
    """6. Request bodies are generated correctly for JSON and other types."""
    form = {
        "info": {"title": "Body Test", "version": "1.0"},
        "endpoints": [
            {
                "path": "/submit",
                "method": "POST",
                "request_body": {
                    "enabled": True,
                    "content_type": "application/json",
                    "description": "Payload",
                    "required": True,
                    "fields": [
                        {"name": "username", "type": "string", "required": True, "example": "john"},
                        {"name": "score", "type": "number", "required": False, "example": 99.5, "default": 0.0}
                    ]
                }
            }
        ]
    }
    spec = generate_openapi_spec(form)
    rb = spec["paths"]["/submit"]["post"]["requestBody"]
    assert rb["required"] is True
    assert rb["description"] == "Payload"
    schema = rb["content"]["application/json"]["schema"]
    assert schema["type"] == "object"
    assert "username" in schema["properties"]
    assert schema["properties"]["username"]["type"] == "string"
    assert schema["properties"]["score"]["type"] == "number"
    assert schema["properties"]["score"]["example"] == 99.5
    assert schema["required"] == ["username"]


def test_generate_responses():
    """7. Responses are generated correctly with status codes and schemas."""
    form = {
        "info": {"title": "Response Test", "version": "1.0"},
        "endpoints": [
            {
                "path": "/products",
                "method": "GET",
                "responses": [
                    {
                        "status_code": "200",
                        "description": "Products found",
                        "content_type": "application/json",
                        "fields": [
                            {"name": "count", "type": "integer", "required": True, "example": 5}
                        ]
                    },
                    {
                        "status_code": "500",
                        "description": "Server error",
                        "content_type": "application/json",
                        "fields": [
                            {"name": "message", "type": "string", "required": True}
                        ]
                    }
                ]
            }
        ]
    }
    spec = generate_openapi_spec(form)
    responses = spec["paths"]["/products"]["get"]["responses"]
    assert "200" in responses
    assert "500" in responses
    assert responses["200"]["description"] == "Products found"
    assert responses["200"]["content"]["application/json"]["schema"]["properties"]["count"]["type"] == "integer"
    assert responses["500"]["description"] == "Server error"


def test_generate_multiple_endpoints_and_responses():
    """8 & 9. Multiple endpoints and multiple responses per endpoint work seamlessly."""
    yaml_content = generate_openapi_yaml(SAMPLE_FORM_DATA)
    parsed = yaml.safe_load(yaml_content)
    assert len(parsed["paths"]) == 2  # /api/v1/users and /api/v1/users/{id}
    assert "get" in parsed["paths"]["/api/v1/users"]
    assert "post" in parsed["paths"]["/api/v1/users"]
    assert "delete" in parsed["paths"]["/api/v1/users/{id}"]

    post_responses = parsed["paths"]["/api/v1/users"]["post"]["responses"]
    assert "201" in post_responses
    assert "400" in post_responses


def test_generated_yaml_can_be_parsed_and_passes_validation():
    """10 & 11. Generated YAML can be parsed and passes existing validate_openapi_content()."""
    yaml_content = generate_openapi_yaml(SAMPLE_FORM_DATA)
    assert isinstance(yaml_content, str)
    assert "openapi: 3.0.3" in yaml_content

    is_valid, summary, error = validate_openapi_content(yaml_content)
    assert is_valid is True
    assert error is None
    assert summary is not None
    assert summary["title"] == "E-Commerce User Service API"
    assert summary["version"] == "1.2.0"
    assert summary["paths_count"] == 2
    assert len(summary["endpoints"]) == 2


# ===========================================================================
# 3. API Route Tests: /api/openapi/generate, /api/openapi/validate, /api/openapi/save
# ===========================================================================

def test_api_openapi_generate_endpoint(client):
    """POST /api/openapi/generate generates validated OpenAPI YAML from form payload."""
    response = client.post(
        "/api/openapi/generate",
        json=SAMPLE_FORM_DATA
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["valid"] is True
    assert "yaml" in data
    assert "E-Commerce User Service API" in data["yaml"]
    assert data["summary"]["title"] == "E-Commerce User Service API"


def test_api_openapi_generate_handles_invalid(client):
    """POST /api/openapi/generate handles malformed payload safely."""
    response = client.post(
        "/api/openapi/generate",
        json={"endpoints": [{"path": "/bad", "method": "invalid_method"}]}
    )
    # Even with fallback, it should return a structured response
    assert response.status_code in (200, 400)


def test_api_openapi_save_rejects_invalid(client, tmp_path, monkeypatch):
    """12. Invalid generated data is rejected with HTTP 400 and does not get saved."""
    temp_spec_file = tmp_path / "original_spec.yaml"
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

    # File remains unchanged
    assert temp_spec_file.read_text() == original_text


def test_save_generated_yaml_and_runtime_integration(client, tmp_path, monkeypatch):
    """13, 14 & 15. Valid generated YAML can be saved and loaded by existing OpenAPIParser and ContractValidator."""
    temp_spec_file = tmp_path / "generated_active_spec.yaml"
    temp_spec_file.write_text("openapi: 3.0.3\ninfo:\n  title: Initial\n  version: '1.0'\npaths: {}\n")

    monkeypatch.setattr(settings, "openapi_spec_path", str(temp_spec_file))

    # 1. Generate YAML
    generated_yaml = generate_openapi_yaml(SAMPLE_FORM_DATA)

    # 2. Save YAML through /api/openapi/save
    response = client.post(
        "/api/openapi/save",
        json={"content": generated_yaml}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "saved"
    assert data["summary"]["title"] == "E-Commerce User Service API"

    # 3. Verify file persisted on disk
    persisted = temp_spec_file.read_text(encoding="utf-8")
    assert "E-Commerce User Service API" in persisted

    # 4. Verify existing OpenAPIParser can load it
    parser = OpenAPIParser.from_file(str(temp_spec_file))
    assert parser.spec["info"]["title"] == "E-Commerce User Service API"
    assert "/api/v1/users/{id}" in parser.paths

    # 5. Verify existing ContractValidator validates runtime traffic against this spec
    validator = ContractValidator(parser)
    valid_data = RuntimeData(
        method="GET",
        path="/api/v1/users",
        status_code=200,
        query_params={"page": "1", "role": "admin"},
        response_body={"id": 1, "name": "Alice", "email": "alice@example.com"}
    )
    report = validator.validate(valid_data)
    assert report.status == ValidationStatus.PASSED

    # 6. Verify ContractValidator detects drift / undocumented routes
    drift_data = RuntimeData(
        method="GET",
        path="/api/v1/nonexistent",
        status_code=404,
        response_body={"detail": "Not found"}
    )
    drift_report = validator.validate(drift_data)
    assert drift_report.status == ValidationStatus.FAILED
