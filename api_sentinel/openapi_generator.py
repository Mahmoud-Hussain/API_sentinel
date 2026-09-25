"""
API Sentinel - OpenAPI Specification Generator
===============================================
Converts structured form inputs collected from the OpenAPI Documentation Portal
into a valid, standard OpenAPI 3.0.3 YAML/JSON specification document.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import yaml


def _build_field_schema(field_item: Dict[str, Any]) -> Dict[str, Any]:
    """Builds an OpenAPI Schema for a single field/property."""
    field_type = field_item.get("type", "string") or "string"
    schema: Dict[str, Any] = {"type": field_type}

    if field_item.get("description"):
        schema["description"] = field_item["description"]

    if "example" in field_item and field_item["example"] not in (None, ""):
        ex = field_item["example"]
        # Convert example to int/float/bool if applicable
        if field_type == "integer":
            try:
                ex = int(ex)
            except (ValueError, TypeError):
                pass
        elif field_type == "number":
            try:
                ex = float(ex)
            except (ValueError, TypeError):
                pass
        elif field_type == "boolean":
            if isinstance(ex, str):
                ex = ex.lower() in ("true", "1", "yes")
        schema["example"] = ex

    if "default" in field_item and field_item["default"] not in (None, ""):
        default_val = field_item["default"]
        if field_type == "integer":
            try:
                default_val = int(default_val)
            except (ValueError, TypeError):
                pass
        elif field_type == "number":
            try:
                default_val = float(default_val)
            except (ValueError, TypeError):
                pass
        elif field_type == "boolean":
            if isinstance(default_val, str):
                default_val = default_val.lower() in ("true", "1", "yes")
        schema["default"] = default_val

    return schema


def _build_object_schema(fields: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Constructs a JSON Schema object containing properties and required fields."""
    if not fields:
        return {"type": "object"}

    properties: Dict[str, Any] = {}
    required: List[str] = []

    for f in fields:
        name = str(f.get("name", "")).strip()
        if not name:
            continue
        properties[name] = _build_field_schema(f)
        if f.get("required"):
            required.append(name)

    schema: Dict[str, Any] = {
        "type": "object",
        "properties": properties,
    }
    if required:
        schema["required"] = required

    return schema


def generate_openapi_spec(form_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transforms structured form dictionary into a standard OpenAPI 3.0.3 specification dict.

    Parameters
    ----------
    form_data : dict
        Form input containing API info, servers, and endpoint definitions.

    Returns
    -------
    dict
        Standard OpenAPI 3.0.3 specification dictionary.
    """
    openapi_version = form_data.get("openapi_version", "3.0.3") or "3.0.3"

    # 1. Info Object
    info_data = form_data.get("info", {})
    title = info_data.get("title", "Generated API") or "Generated API"
    version = info_data.get("version", "1.0.0") or "1.0.0"
    description = info_data.get("description", "")

    info_obj: Dict[str, Any] = {
        "title": title,
        "version": version,
    }
    if description:
        info_obj["description"] = description

    # Optional contact info
    contact_data = info_data.get("contact") or {}
    contact_name = contact_data.get("name")
    contact_email = contact_data.get("email")
    if contact_name or contact_email:
        contact_obj: Dict[str, Any] = {}
        if contact_name:
            contact_obj["name"] = contact_name
        if contact_email:
            contact_obj["email"] = contact_email
        info_obj["contact"] = contact_obj

    # Optional license info
    license_data = info_data.get("license") or {}
    license_name = license_data.get("name")
    license_url = license_data.get("url")
    if license_name or license_url:
        license_obj: Dict[str, Any] = {}
        if license_name:
            license_obj["name"] = license_name
        if license_url:
            license_obj["url"] = license_url
        info_obj["license"] = license_obj

    spec: Dict[str, Any] = {
        "openapi": openapi_version,
        "info": info_obj,
    }

    # 2. Servers
    servers_list = form_data.get("servers", [])
    if servers_list:
        servers_spec: List[Dict[str, str]] = []
        for s in servers_list:
            url = str(s.get("url", "")).strip()
            if url:
                server_item: Dict[str, str] = {"url": url}
                if s.get("description"):
                    server_item["description"] = s["description"]
                servers_spec.append(server_item)
        if servers_spec:
            spec["servers"] = servers_spec

    # 3. Paths & Endpoints
    endpoints = form_data.get("endpoints", [])
    paths_obj: Dict[str, Dict[str, Any]] = {}

    for ep in endpoints:
        path = str(ep.get("path", "")).strip()
        if not path:
            continue
        if not path.startswith("/"):
            path = "/" + path

        method = str(ep.get("method", "get")).strip().lower()
        if method not in {"get", "post", "put", "delete", "patch", "head", "options", "trace"}:
            method = "get"

        if path not in paths_obj:
            paths_obj[path] = {}

        operation: Dict[str, Any] = {}
        if ep.get("summary"):
            operation["summary"] = ep["summary"]
        if ep.get("description"):
            operation["description"] = ep["description"]

        # 4. Parameters (path, query, header, cookie)
        params = ep.get("parameters", [])
        if params:
            op_params: List[Dict[str, Any]] = []
            for p in params:
                p_name = str(p.get("name", "")).strip()
                if not p_name:
                    continue
                p_in = str(p.get("location") or p.get("in") or "query").strip().lower()
                if p_in not in {"path", "query", "header", "cookie"}:
                    p_in = "query"

                # Path parameters are always required in OpenAPI 3.0
                p_req = True if p_in == "path" else bool(p.get("required", False))

                param_dict: Dict[str, Any] = {
                    "name": p_name,
                    "in": p_in,
                    "required": p_req,
                    "schema": _build_field_schema(p),
                }
                if p.get("description"):
                    param_dict["description"] = p["description"]

                op_params.append(param_dict)

            if op_params:
                operation["parameters"] = op_params

        # 5. Request Body
        req_body_data = ep.get("request_body") or {}
        has_req_body = req_body_data.get("enabled", False) or bool(req_body_data.get("fields")) or (method in {"post", "put", "patch"} and req_body_data.get("content_type"))

        if has_req_body:
            content_type = req_body_data.get("content_type", "application/json") or "application/json"
            fields = req_body_data.get("fields", [])

            if content_type == "application/json":
                body_schema = _build_object_schema(fields)
            else:
                body_schema = {"type": "string"}

            request_body_obj: Dict[str, Any] = {
                "required": bool(req_body_data.get("required", True)),
                "content": {
                    content_type: {
                        "schema": body_schema,
                    }
                },
            }
            if req_body_data.get("description"):
                request_body_obj["description"] = req_body_data["description"]

            operation["requestBody"] = request_body_obj

        # 6. Responses
        responses_data = ep.get("responses", [])
        responses_obj: Dict[str, Any] = {}

        if responses_data:
            for resp in responses_data:
                status_code = str(resp.get("status_code", 200)).strip()
                resp_desc = resp.get("description") or f"Response for HTTP {status_code}"
                resp_content_type = resp.get("content_type", "application/json")
                resp_fields = resp.get("fields", [])

                response_item: Dict[str, Any] = {
                    "description": resp_desc,
                }

                if resp_fields and resp_content_type:
                    response_item["content"] = {
                        resp_content_type: {
                            "schema": _build_object_schema(resp_fields),
                        }
                    }
                elif resp_content_type and status_code not in ("204", "304"):
                    response_item["content"] = {
                        resp_content_type: {
                            "schema": {"type": "object"},
                        }
                    }

                responses_obj[status_code] = response_item
        else:
            # Default fallback 200 response if none specified
            responses_obj["200"] = {
                "description": "Successful operation",
            }

        operation["responses"] = responses_obj
        paths_obj[path][method] = operation

    spec["paths"] = paths_obj
    return spec


def generate_openapi_yaml(form_data: Dict[str, Any]) -> str:
    """
    Transforms structured form dictionary into standard OpenAPI 3.0.3 YAML string.

    Parameters
    ----------
    form_data : dict
        Form input containing API info, servers, and endpoint definitions.

    Returns
    -------
    str
        Formatted OpenAPI YAML document.
    """
    spec_dict = generate_openapi_spec(form_data)
    return yaml.dump(spec_dict, sort_keys=False, default_flow_style=False, allow_unicode=True)
