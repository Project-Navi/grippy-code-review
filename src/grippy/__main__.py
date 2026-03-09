# SPDX-License-Identifier: MIT
"""Package entry point -- run Grippy via ``python -m grippy``.

Subcommands
-----------
``python -m grippy``            Legacy CI pipeline (requires GITHUB_TOKEN / EVENT_PATH)
``python -m grippy serve``      Start the MCP server over stdio
``python -m grippy install-mcp``  Interactive MCP client installer

Using ``python -m grippy`` instead of ``python -m grippy.review`` avoids
a RuntimeWarning caused by __init__.py eagerly importing grippy.review
before the -m mechanism executes it as __main__.
"""

from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

# Subcommands that are intercepted before argparse sees them
_SUBCOMMANDS = {"serve", "install-mcp"}

# Project root: __main__.py -> src/grippy/ -> src/ -> project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


# ---------------------------------------------------------------------------
# serve
# ---------------------------------------------------------------------------


def _serve(argv: list[str]) -> None:
    """Start the Grippy MCP server over stdio."""
    parser = argparse.ArgumentParser(
        prog="grippy serve",
        description="Start the Grippy MCP server over stdio",
    )
    parser.parse_args(argv)

    from grippy.mcp_server import main as serve_main

    serve_main()


# ---------------------------------------------------------------------------
# install-mcp
# ---------------------------------------------------------------------------


def _install_mcp(argv: list[str]) -> None:
    """Interactive MCP client installer."""
    parser = argparse.ArgumentParser(
        prog="grippy install-mcp",
        description="Install Grippy as an MCP server in supported clients",
    )
    parser.add_argument(
        "--transport",
        choices=["openai", "anthropic", "google", "groq", "mistral", "local"],
        default=None,
        help="LLM transport for audit_diff",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="API key for the chosen provider (prompted if not provided)",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="Base URL for local LLM endpoint",
    )
    parser.add_argument(
        "--model-id",
        default=None,
        help="Model identifier for local LLM endpoint",
    )
    parser.add_argument(
        "--clients",
        default=None,
        help="Comma-separated list of clients to install into",
    )
    parser.add_argument(
        "--profile",
        choices=["general", "security", "strict-security"],
        default="security",
        help="Security profile (default: security)",
    )
    parser.add_argument(
        "--dev",
        action="store_true",
        default=False,
        help="Use dev-mode entry (uv run --directory) instead of uvx",
    )
    args = parser.parse_args(argv)

    from grippy.mcp_config import (
        MCPClient,
        add_to_client,
        generate_server_entry,
        get_available_clients,
    )

    # -- Collect transport --
    transports = ["openai", "anthropic", "google", "groq", "mistral", "local"]
    transport: str = args.transport or ""
    if not transport:
        print("Select LLM transport for audit_diff:")
        for i, t in enumerate(transports, 1):
            print(f"  {i}) {t}")
        choice = input(f"Choice [1-{len(transports)}]: ").strip()
        try:
            transport = transports[int(choice) - 1]
        except (ValueError, IndexError):
            transport = "local"

    # -- Collect transport-specific config --
    # Map provider names to their expected API key env vars
    api_key_envs: dict[str, str] = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "google": "GOOGLE_API_KEY",
        "groq": "GROQ_API_KEY",
        "mistral": "MISTRAL_API_KEY",
    }

    env: dict[str, str] = {
        "GRIPPY_TRANSPORT": transport,
        "GRIPPY_PROFILE": args.profile,
    }

    if transport == "local":
        base_url = args.base_url or input("Base URL [http://localhost:1234/v1]: ").strip()
        if base_url:
            env["GRIPPY_BASE_URL"] = base_url
        model_id = args.model_id or input("Model ID [devstral-small-2-24b-instruct-2512]: ").strip()
        if model_id:
            env["GRIPPY_MODEL_ID"] = model_id
    elif transport in api_key_envs:
        key_env = api_key_envs[transport]
        api_key = args.api_key or getpass.getpass(f"{key_env}: ")
        env[key_env] = api_key

    # -- Collect target clients --
    selected_clients: list[MCPClient]
    if args.clients:
        name_map = {c.value.lower().replace(" ", "-"): c for c in MCPClient}
        selected_clients = []
        for name in args.clients.split(","):
            name = name.strip().lower()
            client = name_map.get(name)
            if client is None:
                print(f"Unknown client: {name!r}")
                sys.exit(1)
            selected_clients.append(client)
    else:
        available = get_available_clients()
        if not available:
            print("No supported MCP clients detected.")
            sys.exit(1)
        print("\nAvailable MCP clients:")
        for i, client in enumerate(available, 1):
            print(f"  {i}) {client.value}")
        selection = input("Select clients (comma-separated numbers, or 'all'): ").strip()
        if selection.lower() == "all":
            selected_clients = available
        else:
            indices = [int(x.strip()) for x in selection.split(",")]
            selected_clients = [available[i - 1] for i in indices]

    # -- Generate and install --
    root = _PROJECT_ROOT if args.dev else None
    entry = generate_server_entry(root, env)

    for client in selected_clients:
        ok = add_to_client(client, entry)
        if ok:
            print(f"  [OK] {client.value}")
        else:
            print(f"  [FAIL] {client.value}")


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------


def _get_version() -> str:
    """Return the package version string."""
    from grippy import __version__

    return __version__


def main() -> None:
    """Console script entry point — dispatches subcommands."""
    if len(sys.argv) > 1 and sys.argv[1] in _SUBCOMMANDS:
        subcommand = sys.argv[1]
        rest = sys.argv[2:]
        if subcommand == "serve":
            _serve(rest)
        elif subcommand == "install-mcp":
            _install_mcp(rest)
        return

    # Top-level: CI review with --version and subcommand-aware --help
    parser = argparse.ArgumentParser(
        prog="grippy",
        description="Grippy — the reluctant code inspector.",
        epilog=(
            "subcommands:\n"
            "  serve         Start the MCP server over stdio\n"
            "  install-mcp   Interactive MCP client installer\n"
            "\n"
            "Run 'grippy <subcommand> --help' for subcommand-specific help."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s {_get_version()}",
    )
    parser.add_argument(
        "--profile",
        choices=["general", "security", "strict-security"],
        default=None,
        help="Security profile (overrides GRIPPY_PROFILE env var)",
    )
    args = parser.parse_args()

    from grippy.review import main as review_main

    review_main(profile=args.profile)


if __name__ == "__main__":
    main()
