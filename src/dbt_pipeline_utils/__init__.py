import logging
from rich.logging import RichHandler

from pathlib import Path
from dotenv import load_dotenv
from os import getenv

def find_repo_root():
    """Find the repository root by looking for a requirements.txt file, if any."""

    current = Path.cwd()

    for parent in [current, *current.parents]:
        if any(parent.glob("*requirements.txt")):
            return parent.resolve()

    return None


# Load the .env file, if one can be found. Optional: standalone scripts should
# work from any directory, with or without a repo-style .env file present.
repo_root = find_repo_root()
if repo_root is not None:
    env_path = repo_root / ".env"
    success = load_dotenv(dotenv_path=env_path, override=True)


# setup logging
# Map PUTILS_LOGLEVEL to an integer log level
LOGLEVEL_STRING = getenv("PUTILS_LOGLEVEL", "INFO").strip().upper()
llevel = logging._nameToLevel.get(LOGLEVEL_STRING, logging.INFO)
LOGGING_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
TIME_FORMAT = "%H:%M:%S"


handler = RichHandler(
    show_time=False,  # Disable Rich's own timestamp
    show_level=True,  # Show log level
    show_path=False,  # Disable source file path in logs
    rich_tracebacks=True,  # Optional: Enable rich traceback formatting
)
handler.setFormatter(logging.Formatter(fmt=LOGGING_FORMAT, datefmt=TIME_FORMAT))

# Setup package logger
package_logger = logging.getLogger("dbt_pipeline_utils")
package_logger.setLevel(llevel)
if not package_logger.hasHandlers():
    package_logger.addHandler(handler)

# For backward compatibility, expose as 'logger'
logger = package_logger
