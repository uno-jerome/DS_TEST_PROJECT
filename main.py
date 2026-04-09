"""Application entrypoint for launching admin or buyer UI from one command."""

from __future__ import annotations

import argparse
import importlib
import logging
import subprocess
import sys
from pathlib import Path


APP_MODES = {
    "admin": "admin_app",
    "buyer": "buyer_app",
}
APP_MODE_BOTH = "both"


def setup_logging() -> None:
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
        )


def build_argument_parser() -> argparse.ArgumentParser:
    """Create CLI parser for selecting which desktop app to launch."""

    parser = argparse.ArgumentParser(description="ITC Desktop E-Commerce launcher")
    parser.add_argument(
        "--app",
        choices=sorted([*APP_MODES.keys(), APP_MODE_BOTH]),
        default="buyer",
        help="Choose which app to launch (admin, buyer, or both; default: buyer)",
    )
    return parser


def launch_both_applications() -> None:
    """Launch admin and buyer apps in separate processes."""

    logger = logging.getLogger(__name__)
    launcher_dir = Path(__file__).resolve().parent
    python_executable = sys.executable or "python"
    launched_processes: list[tuple[str, subprocess.Popen]] = []

    try:
        for app_mode, module_name in APP_MODES.items():
            script_path = launcher_dir / f"{module_name}.py"
            if not script_path.exists():
                raise FileNotFoundError(f"Missing app launcher script: {script_path}")

            process = subprocess.Popen([python_executable, str(script_path)])
            launched_processes.append((app_mode, process))
            logger.info(
                "Launched desktop application process",
                extra={"app_mode": app_mode, "app_script": script_path.name, "pid": process.pid},
            )

        failing_processes: list[str] = []
        for app_mode, process in launched_processes:
            exit_code = process.wait()
            if exit_code != 0:
                failing_processes.append(f"{app_mode}:{exit_code}")

        if failing_processes:
            raise RuntimeError("One or more launched apps exited with failure: " + ", ".join(failing_processes))
    except Exception:
        for _, process in launched_processes:
            if process.poll() is None:
                process.terminate()
        raise


def launch_application(app_mode: str) -> None:
    """Import and run the selected legacy UI module."""

    if app_mode == APP_MODE_BOTH:
        launch_both_applications()
        return

    module_name = APP_MODES[app_mode]
    logger = logging.getLogger(__name__)
    logger.info("Launching desktop application", extra={"app_mode": app_mode, "app_module": module_name})
    importlib.import_module(module_name)


def main() -> int:
    """Program entrypoint."""

    setup_logging()
    parser = build_argument_parser()
    args = parser.parse_args()

    try:
        launch_application(args.app)
        return 0
    except Exception as unexpected_error:
        logger = logging.getLogger(__name__)
        logger.error(
            "Application failed with unhandled error",
            extra={"error": str(unexpected_error)},
            exc_info=True,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
