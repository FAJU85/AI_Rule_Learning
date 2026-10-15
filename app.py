"""AI Rule Learning root application entry point for dev server."""

import os
import subprocess
import sys
from pathlib import Path

# Ensure root directory and space directory are in python path
ROOT_DIR = Path(__file__).resolve().parent
SPACE_DIR = ROOT_DIR / "space"
for directory in (ROOT_DIR, SPACE_DIR):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))


def ensure_environment() -> None:
    """Ensure required packages are present so dev server never dies on cold start."""
    os.environ["PIP_BREAK_SYSTEM_PACKAGES"] = "1"
    pip_conf = Path("/etc/pip.conf")
    if not pip_conf.exists():
        try:
            pip_conf.write_text("[global]\nbreak-system-packages = true\n", encoding="utf-8")
        except Exception:
            pass

    try:
        import gradio  # noqa: F401
    except ImportError:
        print("[AI Rule Learning] Installing dependencies from requirements.txt...")
        req_file = ROOT_DIR / "requirements.txt"
        if req_file.exists():
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "--break-system-packages", "-r", str(req_file)],
                check=True,
            )
        mcp_dir = ROOT_DIR / "mcp"
        if mcp_dir.exists():
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "--break-system-packages", "-e", str(mcp_dir)],
                check=False,
            )


if __name__ == "__main__":
    ensure_environment()

    from space.app import demo  # noqa: E402

    port_env = os.environ.get("PORT")
    # In AI Studio, PORT can be set to 8080 (container proxy), but the dev server must bind to 3000
    if port_env and port_env != "8080":
        port = int(port_env)
    else:
        port = int(os.environ.get("GRADIO_SERVER_PORT", 3000))

    demo.launch(server_name="0.0.0.0", server_port=port, share=False)
