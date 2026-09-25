"""
API Sentinel - Command Line Interface (CLI)
Provides terminal commands to start the dashboard, validate specs, and inspect health.
"""

import argparse
import sys
import os

from api_sentinel import __version__


def run_dashboard(host: str = "127.0.0.1", port: int = 8001, reload: bool = False):
    """Launches the API Sentinel interactive dashboard server."""
    try:
        import uvicorn
    except ImportError:
        print("Error: uvicorn is required to run the dashboard. Install it with: pip install uvicorn")
        sys.exit(1)

    print(f"Starting API Sentinel Dashboard on http://{host}:{port} ...")
    uvicorn.run("api_sentinel.dashboard.app:app", host=host, port=port, reload=reload)


def run_validate(spec_path: str):
    """Validates an OpenAPI YAML or JSON specification file."""
    if not os.path.exists(spec_path):
        print(f"Error: Specification file not found: {spec_path}")
        sys.exit(1)

    try:
        from api_sentinel.openapi_parser import OpenAPIParser
        parser = OpenAPIParser.from_file(spec_path)
        endpoints = list(parser.paths.keys())
        print(f"Success: '{spec_path}' is a valid OpenAPI specification!")
        print(f"Found {len(endpoints)} documented endpoint(s):")
        for ep in endpoints:
            print(f"  • {ep}")
    except Exception as exc:
        print(f"Validation failed for '{spec_path}': {exc}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        prog="api-sentinel",
        description="API Sentinel - Real-time OpenAPI Schema Drift Detection & Telemetry Dashboard",
    )
    parser.add_argument(
        "-v", "--version", action="version", version=f"API Sentinel v{__version__}"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Command: dashboard
    dash_parser = subparsers.add_parser("dashboard", help="Start the interactive monitoring dashboard")
    dash_parser.add_argument("--host", default="127.0.0.1", help="Host address to bind (default: 127.0.0.1)")
    dash_parser.add_argument("-p", "--port", type=int, default=8001, help="Port to bind (default: 8001)")
    dash_parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")

    # Command: validate
    val_parser = subparsers.add_parser("validate", help="Validate an OpenAPI specification file")
    val_parser.add_argument("--spec", default="openapi.yaml", help="Path to OpenAPI spec file (default: openapi.yaml)")

    # Command: version
    subparsers.add_parser("version", help="Print API Sentinel version")

    args = parser.parse_args()

    if args.command == "dashboard":
        run_dashboard(host=args.host, port=args.port, reload=args.reload)
    elif args.command == "validate":
        run_validate(args.spec)
    elif args.command == "version":
        print(f"API Sentinel v{__version__}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
