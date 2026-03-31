"""博主主页视频列表。"""

import logging

from .bridge import BridgePage
from .human import random_delay, scroll_and_browse
from .types import VideoItem
from .urls import API_AUTHOR_POSTS

logger = logging.getLogger(__name__)

AUTHOR_URL = "https://www.douyin.com/user/"


def get_author_posts(page: BridgePage, sec_uid: str = None, url: str = None) -> list[VideoItem]:
    """获取博主主页的视频发布列表。"""
    if not url and not sec_uid:
        logger.error("get_author_posts: sec_uid 和 url 均未提供")
        return []

    if not url:
        url = f"{AUTHOR_URL}{sec_uid}"
    
    logger.info("获取博主视频列表: %s", url)

    # 使用 listen_api：先启动监听，再导航触发 API
    api_data = page.listen_api(
        url_pattern=API_AUTHOR_POSTS,
        navigate_url=url,
        timeout=20.0,
        new_tab=True # 使用新标签页打开，不影响当前页面
    )

    if api_data and isinstance(api_data, dict):
        results = VideoItem.parse_api_list(api_data)
        logger.info("API 监听成功，获取到 %d 条博主视频", len(results))
        return results

    logger.warning("API 监听未获取到博主视频数据")
    return []
