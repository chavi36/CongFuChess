"""Result writer service package for Kung-Fu Chess."""

from .service import get_last_result, get_result, run_result_writer, write_result

__all__ = ["get_last_result", "get_result", "write_result", "run_result_writer"]
