"""抖音互动：点赞、收藏、评论。"""

import logging
import time
from .bridge import BridgePage
from .urls import HOME_URL
from .selectors import LIKE_BUTTON, COLLECT_BUTTON, COMMENT_TRIGGER, COMMENT_INPUT, COMMENT_SUBMIT
from .errors import NotLoggedInError, ElementNotFoundError
from .login import check_login

logger = logging.getLogger(__name__)

def _ensure_login(page: BridgePage):
    if not check_login(page):
        raise NotLoggedInError()

def _navigate_to_video(page: BridgePage, video_id: str):
    url = f"{HOME_URL}video/{video_id}"
    if page.get_url() != url:
        page.navigate(url)
        page.wait_for_load()
    page.wait_dom_stable()
    time.sleep(1)

def like_video(page: BridgePage, video_id: str) -> bool:
    """点赞视频。"""
    _ensure_login(page)
    _navigate_to_video(page, video_id)
    
    # 查找并点击点赞按钮
    page.wait_for_element(LIKE_BUTTON, timeout=10)
    page.click_element(LIKE_BUTTON)
    logger.info(f"已点击点赞按钮：{video_id}")
    return True

def favorite_video(page: BridgePage, video_id: str) -> bool:
    """收藏视频。"""
    _ensure_login(page)
    _navigate_to_video(page, video_id)
    
    # 查找并点击收藏按钮
    page.wait_for_element(COLLECT_BUTTON, timeout=10)
    page.click_element(COLLECT_BUTTON)
    logger.info(f"已点击收藏按钮：{video_id}")
    return True

def post_comment(page: BridgePage, video_id: str, content: str) -> bool:
    """发表评论。"""
    _ensure_login(page)
    _navigate_to_video(page, video_id)
    
    # 点击评论图标以激活输入框（某些情况下需要）
    try:
        page.wait_for_element(COMMENT_TRIGGER, timeout=10)
        page.click_element(COMMENT_TRIGGER)
        time.sleep(1)
    except Exception:
        pass
        
    # 输入评论内容
    page.wait_for_element(COMMENT_INPUT, timeout=10)
    page.click_element(COMMENT_INPUT)
    page.type_text(content)
    time.sleep(0.5)
    
    # 提交评论
    page.click_element(COMMENT_SUBMIT)
    logger.info(f"已发表评论：{video_id} -> {content}")
    return True
