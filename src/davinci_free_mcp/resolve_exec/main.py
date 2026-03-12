"""Executor bootstrap entrypoint."""

from __future__ import annotations

import argparse

from davinci_free_mcp.resolve_exec.executor import ResolveExecutor


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Resolve Free executor.")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process at most one request and exit.",
    )
    args = parser.parse_args()

    executor = ResolveExecutor()
    if args.once:
        executor.process_next_request_once()
        return

    executor.run_forever()


if __name__ == "__main__":
    main()
