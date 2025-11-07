"""Logging configuration and console output utilities for AI Analysis tools."""

import logging
import sys


class Colors:
    """ANSI color codes for terminal output."""

    RED = "\033[0;31m"
    GREEN = "\033[0;32m"
    YELLOW = "\033[1;33m"
    BLUE = "\033[0;34m"
    NC = "\033[0m"  # No Color


def print_header(text: str) -> None:
    """Print a colored header."""
    print(f"{Colors.BLUE}{'=' * 40}{Colors.NC}")
    print(f"{Colors.BLUE}{text}{Colors.NC}")
    print(f"{Colors.BLUE}{'=' * 40}{Colors.NC}")
    print()


def print_status(success: bool, message: str, warning: bool = False) -> None:
    """Print a status message with appropriate color."""
    if success:
        print(f"{Colors.GREEN}✓ {message}{Colors.NC}")
    elif warning:
        print(f"{Colors.YELLOW}⚠ {message}{Colors.NC}")
    else:
        print(f"{Colors.RED}✗ {message}{Colors.NC}")


def print_section(title: str) -> None:
    """Print a section header."""
    print(f"{Colors.YELLOW}{title}...{Colors.NC}")


def setup_logger(name, level=logging.INFO):
    """
    Set up a logger with consistent formatting.

    Args:
        name: Logger name
        level: Logging level

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)

        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)

        logger.addHandler(handler)

    return logger


# Default logger instance for the package
logger = setup_logger("ai_analysis")
