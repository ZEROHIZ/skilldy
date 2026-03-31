"""分享视频逻辑。"""

import logging
from .bridge import BridgePage
from .human import random_delay
from .urls import API_SHORTEN, SHARE_ICON_SELECTOR

logger = logging.getLogger(__name__)

def share_video(page: BridgePage, video_id: str) -> dict:
    """点击分享按钮并获取短链接。"""
    logger.debug("执行分享操作: video_id=%s", video_id)
    
    random_delay(1.0, 2.0)
    
    # 1. 检查容器与分享按钮是否存在
    check_js = f"""
    (() => {{
        const container = document.querySelector('[data-e2e-vid="{video_id}"]');
        if (!container) return "ERR_CONTAINER_NOT_FOUND";
        const icon = container.querySelector('{SHARE_ICON_SELECTOR}');
        if (!icon) return "ERR_ICON_NOT_FOUND";
        return "READY";
    }})()
    """
    status = page.evaluate(check_js)
    if status == "ERR_CONTAINER_NOT_FOUND":
        logger.debug("❌ 未找到 ID 为 %s 的视频容器。", video_id)
        return {"shareurl": ""}
    elif status == "ERR_ICON_NOT_FOUND":
        logger.debug("❌ 已找到视频容器，但内部未找到分享按钮 (%s)。", SHARE_ICON_SELECTOR)
        return {"shareurl": ""}

    # 2. 构造带作用域的选择器进行点击并监听
    scoped_selector = f'[data-e2e-vid="{video_id}"] {SHARE_ICON_SELECTOR}'
    logger.debug("✅ 容器与图标探测成功，正在点击分享并触发 API 监听 (scoped)...")
    
    api_data = page.listen_api(
        url_pattern=API_SHORTEN,
        click_selector=scoped_selector, 
        timeout=15.0,
    )

    if api_data and isinstance(api_data, dict):
        url = api_data.get("data")
        if url:
            logger.debug("API 监听成功，获取到分享短链接: %s", url)
            return {"shareurl": url}

    logger.warning("未捕获到分享 API 数据")
    return {"shareurl": ""}
