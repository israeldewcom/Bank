import numpy as np
from scipy import stats
from chronos_v5.config import Config
from chronos_v5.logger_setup import logger

class DriftDetector:
    def __init__(self):
        self.threshold = Config.CONCEPT_DRIFT_THRESHOLD
        self.window = []
        self.max_window = 100
        self.drift_detected = False
        self.adwin = None
        self.cusum = None
        try:
            from river.drift import ADWIN
            self.adwin = ADWIN(delta=self.threshold)
        except ImportError:
            logger.warning("River not installed; drift detection will use simple threshold")
        # CUSUM parameters
        self.cusum_mean = 0.0
        self.cusum_high = 0.0
        self.cusum_low = 0.0
        self.cusum_threshold = 1.0  # Adjust based on desired sensitivity

    def update(self, value: float):
        if self.adwin is not None:
            self.adwin.update(value)
            self.drift_detected = self.adwin.drift_detected
        else:
            # Fallback: use CUSUM
            self.window.append(value)
            if len(self.window) > self.max_window:
                self.window.pop(0)
            if len(self.window) > 10:
                # Update CUSUM
                mean = np.mean(self.window)
                std = np.std(self.window)
                if std > 0:
                    z = (value - mean) / std
                    # CUSUM for positive shift
                    self.cusum_high = max(0, self.cusum_high + z - self.threshold)
                    # CUSUM for negative shift
                    self.cusum_low = min(0, self.cusum_low + z + self.threshold)
                    if self.cusum_high > self.cusum_threshold or self.cusum_low < -self.cusum_threshold:
                        self.drift_detected = True
                        logger.warning("Concept drift detected by CUSUM")
                        # Reset CUSUM after detection to avoid repeated triggers
                        self.cusum_high = 0
                        self.cusum_low = 0
                    else:
                        self.drift_detected = False
                else:
                    self.drift_detected = False
