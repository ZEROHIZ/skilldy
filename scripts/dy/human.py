"""人类行为模拟参数（延迟、滚动、悬停）。"""

from __future__ import annotations

import logging
import random
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .bridge import BridgePage

logger = logging.getLogger(__name__)

def sleep_random(min_ms: int, max_ms: int) -> None:
    """随机延迟。"""
    if max_ms <= min_ms:
        time.sleep(min_ms / 1000.0)
        return
    delay = random.randint(min_ms, max_ms) / 1000.0
    time.sleep(delay)

def navigation_delay() -> None:
    """页面导航后的随机等待，模拟人类阅读。"""
    sleep_random(1000, 2500)

def get_scroll_interval(speed: str) -> float:
    """根据速度获取滚动间隔（秒）。"""
    if speed == "slow":
        return (1200 + random.randint(0, 300)) / 1000.0
    if speed == "fast":
        return (300 + random.randint(0, 100)) / 1000.0
    return (600 + random.randint(0, 200)) / 1000.0

def calculate_scroll_delta(viewport_height: int, base_ratio: float) -> float:
    """计算滚动距离。"""
    scroll_delta = viewport_height * (base_ratio + random.random() * 0.2)
    if scroll_delta < 400:
        scroll_delta = 400.0
    return scroll_delta + random.randint(-50, 50)


# ─── 高级人类行为模拟 ────────────────────────────────────────────

def random_delay(min_s: float = 0.5, max_s: float = 2.0) -> None:
    """随机等待秒数，模拟人类操作间隔。"""
    time.sleep(random.uniform(min_s, max_s))

def human_click(page: BridgePage, selector: str,
                pre_delay: tuple = (0.3, 1.0),
                post_delay: tuple = (0.5, 1.5)) -> None:
    """人类式点击：随机延迟 → 点击 → 随机延迟。"""
    random_delay(*pre_delay)
    page.click_element(selector)
    random_delay(*post_delay)
    logger.debug("human_click: %s", selector)

def random_scroll(page: BridgePage,
                  min_y: int = 200, max_y: int = 600) -> None:
    """随机幅度滚动页面。"""
    delta = random.randint(min_y, max_y)
    page.scroll_by(0, delta)
    random_delay(0.3, 1.0)
    logger.debug("random_scroll: %d px", delta)

def scroll_and_browse(page: BridgePage,
                      times: int = 2,
                      scroll_range: tuple = (300, 800),
                      wait_range: tuple = (1.0, 3.0)) -> None:
    """模拟人类浏览：多次滚动，每次随机幅度和等待时间。"""
    for i in range(times):
        delta = random.randint(*scroll_range)
        page.scroll_by(0, delta)
        wait = random.uniform(*wait_range)
        logger.debug("scroll_and_browse [%d/%d]: %d px, 等待 %.1fs", i + 1, times, delta, wait)
        time.sleep(wait)

