"""首页推荐流列表。

⚠️ 已废弃：推荐流数据在抖音沙箱中渲染，无法通过 Network 监听获取。
请使用 search.py（搜索视频）或 author_posts.py（博主主页）替代。
"""

import json
import logging

from .bridge import BridgePage
from .errors import NoFeedsError
from .human import random_delay, random_scroll
from .types import VideoItem
from .urls import HOME_URL

logger = logging.getLogger(__name__)


def list_feeds(page: BridgePage) -> list[VideoItem]:
    """获取推荐流视频列表（仅 DOM 解析，数据质量有限）。"""
    logger.warning("推荐流功能数据质量有限，建议使用 search_videos 或 get_author_posts")

    current_url = page.get_url()
    if current_url.strip("/") != HOME_URL.strip("/"):
        page.navigate(HOME_URL)
        page.wait_for_load(timeout=30.0)

    page.wait_dom_stable()
    random_delay(1.5, 3.0)
    random_scroll(page)
    random_delay(1.0, 2.0)

    js_code = """
    (() => {
        const items = document.querySelectorAll('.xgplayer-playing, .slider-video, [data-e2e="feed-active-video"]');
        const results = [];
        for (const item of items) {
            const accountEl = document.querySelector('.account-name');
            const titleEl = document.querySelector('.video-info-detail');
            results.push({
                aweme_id: "feed_" + Math.random().toString(36).substring(7),
                desc: titleEl ? titleEl.innerText.replace(/\\n/g, ' ').substring(0, 100) : "",
                author: {nickname: accountEl ? accountEl.innerText : ""}
            });
        }
        return JSON.stringify(results);
    })()
    """

    result = page.evaluate(js_code)
    if not result:
        raise NoFeedsError()

    feeds_data = json.loads(result)
    return [VideoItem.from_dict(f) for f in feeds_data]
