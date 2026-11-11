from detectors.growth import detect_growth
from detectors.panel import build_panel
from detectors.zscore import detect_zscore

DETECTORS = {"zscore": detect_zscore, "growth": detect_growth}

__all__ = ["DETECTORS", "build_panel", "detect_zscore", "detect_growth"]
