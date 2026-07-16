import requests, time, threading, redis, json, feedparser
from datetime import datetime, timezone
from chronos_v5.config import Config
from chronos_v5.logger_setup import logger
from chronos_v5.advanced.advanced_config import AdvancedConfig
from chronos_v5.tasks import generate_alpha_signals, optimize_rehypothecation
from chronos_v5.advanced.dynamic_calibrator import DynamicCalibrator
from chronos_v5.haircut_engine import HaircutEngine

class CBNEventListener:
    def __init__(self):
        self.redis = redis.from_url(Config.REDIS_URL)
        self.last_update = None
        self.running = False
        self.thread = None
        self.calibrator = DynamicCalibrator() if AdvancedConfig.DYNAMIC_CALIBRATION_ENABLED else None
        self.haircut_engine = HaircutEngine()

    def start(self):
        if not AdvancedConfig.CBN_EVENT_LISTENER_ENABLED:
            logger.info("CBN event listener disabled")
            return
        self.running = True
        self.thread = threading.Thread(target=self._poll, daemon=True)
        self.thread.start()
        logger.info("CBN event listener started")

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)

    def _poll(self):
        while self.running:
            try:
                self._check_feed()
            except Exception as e:
                logger.error(f"CBN event listener error: {e}")
            time.sleep(AdvancedConfig.CBN_EVENT_POLL_INTERVAL_SEC)

    def _check_feed(self):
        feed = feedparser.parse(AdvancedConfig.CBN_RSS_FEED_URL)
        if not feed.entries:
            return
        latest = feed.entries[0]
        pub_date = latest.get('published_parsed')
        if pub_date:
            dt = datetime.fromtimestamp(time.mktime(pub_date), tz=timezone.utc)
            last = self.redis.get("cbn:last_pub")
            if last is None or dt > datetime.fromisoformat(last.decode()):
                logger.info(f"CBN event detected: {latest.title} at {dt}")
                self.redis.set("cbn:last_pub", dt.isoformat())
                generate_alpha_signals.delay()
                optimize_rehypothecation.delay()
                self.redis.delete("ng:cbn:mpr")
                self._update_haircut_matrix(latest)
                self._alert(f"CBN announcement: {latest.title}")

    def _update_haircut_matrix(self, entry):
        text = entry.get('summary', '') + entry.get('title', '')
        if 'monetary policy' in text.lower() or 'mpr' in text.lower():
            new_baseline = Config.HAIRCUT_BASELINE * 1.1
            self.redis.set("haircut:baseline", new_baseline)
            logger.info(f"Haircut baseline updated to {new_baseline:.4f}")
            if self.calibrator:
                self.calibrator.force_calibration()

    def _alert(self, message):
        if Config.SLACK_WEBHOOK_URL:
            try:
                requests.post(Config.SLACK_WEBHOOK_URL, json={"text": message})
            except:
                pass

cbn_listener = CBNEventListener()
