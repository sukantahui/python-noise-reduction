"""CNAT NOISERELIEF - Main Application Entry Point.
Created by Coder & AccoTax
Website: www.codernaccotax.co.in | Phone: 7003756860
"""
import sys
import os
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.logger import setup_logger
from src.gui.app import NoiseReliefApp

logger = setup_logger("NoiseRelief")


def main() -> None:
    """Initializes and runs CNAT NOISERELIEF desktop GUI application."""
    logger.info("Starting CNAT NOISERELIEF (Created by Coder & AccoTax - www.codernaccotax.co.in)...")
    try:
        app = NoiseReliefApp()
        app.mainloop()
    except Exception as ex:
        logger.critical(f"Unhandled exception during app runtime: {ex}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
