"""视频详情 - 纯 ID 定位模式。

前置条件：用户已在页面（如搜索结果或博主主页）。
流程：锁定 ID 容器 -> 计算中心坐标 -> 模拟 Native 点击。
"""

import logging
import time

from .bridge import BridgePage
from .human import random_delay
from .selectors import COMMENT_ICON
from .types import VideoDetail

logger = logging.getLogger(__name__)


def get_video_detail(page: BridgePage, video_id: str) -> VideoDetail:
    """获取视频详情（纯 ID 定位 + 坐标点击仿真）。"""
    logger.info("获取视频详情: video_id=%s", video_id)
    random_delay(1.0, 2.0)

    # 极简版 JS：仅定位 ID 容器并返回坐标
    click_js = f"""
    (async () => {{
        const vid = "{video_id}";
        const logs = [];
        const log = (msg) => logs.push(`[JS] ${{msg}}`);
        
        log(`开始 ID 定位流程: ${{vid}}`);

        // 查找容器：搜索结果页的 div 或 博主页的 a
        const container = document.getElementById(`waterfall_item_${{vid}}`) || 
                          document.querySelector(`a[href*="${{vid}}"]`);

        if (!container) {{
            log(`错误: 未找到对应的视频容器`);
            return {{ success: false, logs }};
        }}

        // 滚动并等待稳定
        container.scrollIntoView({{block: 'center', behavior: 'smooth'}});
        await new Promise(r => setTimeout(r, 1500)); 

        // 计算中心点
        const rect = container.getBoundingClientRect();
        if (rect.width > 0 && rect.height > 0) {{
            const x = rect.left + rect.width / 2;
            const y = rect.top + rect.height / 2;
            log(`锁定坐标: (${{x.toFixed(0)}}, ${{y.toFixed(0)}})`);
            return {{ success: true, x, y, logs }};
        }}

        log(`错误: 容器不可见`);
        return {{ success: false, logs }};
    }})()
    """
    
    res = page.evaluate(click_js)
    if not res:
        logger.error("JS 执行未返回有效结果")
        return VideoDetail(video_id="failed", desc="failed", author_name="unknown")

    for l in res.get("logs", []):
        logger.info(l)

    if res.get("success"):
        x, y = res.get("x"), res.get("y")
        
        if y < 0:
            logger.warning("坐标异常 (y=%d)，强制 instant 滚动对齐...", y)
            page.evaluate(f"document.getElementById('waterfall_item_{video_id}')?.scrollIntoView({{block: 'center', behavior: 'instant'}})")
            time.sleep(0.5)
            res = page.evaluate(click_js.replace("behavior: 'smooth'", "behavior: 'instant'"))
            if res and res.get("success"):
                x, y = res["x"], res["y"]

        if y > 0:
            logger.info("执行 Native 点击仿真: 移动并点击坐标 (%d, %d)", x, y)
            page.mouse_move(x, y)
            random_delay(0.5, 0.8) 
            page.mouse_click(x, y)
            
            logger.info("已点击，等待进入播放页...")
            try:
                page.wait_for_element(COMMENT_ICON, timeout=12.0)
                logger.info("确认已进入播放页")
                return VideoDetail(video_id=video_id, desc="clicked", author_name="unknown")
            except Exception:
                logger.warning("点击后未在预期内发现播放页标识")

    # 兜底：检测当前是否已在播放页
    if page.has_element(COMMENT_ICON):
        logger.info("确认当前已在播放页")
        return VideoDetail(video_id=video_id, desc="present", author_name="unknown")
    
    logger.error("操作失败，无法进入目标视频")
    return VideoDetail(video_id="failed", desc="failed", author_name="unknown")


def get_video_detail_by_url(page: BridgePage, share_url: str, target_comments: int = 0) -> dict:
    """通过分享链接获取视频详情（支持同时获取初始评论）。"""
    from .urls import API_DETAIL, API_COMMENTS
    from .comments import scroll_and_extract_comments, Comment
    import time
    
    logger.info("通过分享链接获取详情: %s", share_url)
    
    result = {"video_detail": None, "comments": []}
    
    # 决定监听单 API 还是多 API
    if target_comments > 0:
        api_data = page.listen_apis(
            url_patterns=[API_DETAIL, API_COMMENTS],
            navigate_url=share_url,
            timeout=20.0,
            new_tab=True
        )
        detail_data = api_data.get(API_DETAIL)
        initial_comments_data = api_data.get(API_COMMENTS)
    else:
        detail_data = page.listen_api(
            url_pattern=API_DETAIL,
            navigate_url=share_url,
            timeout=20.0,
            new_tab=True
        )
        initial_comments_data = None

    if detail_data and isinstance(detail_data, dict):
        item = detail_data.get("aweme_detail") or detail_data
        if isinstance(item, dict):
            detail = VideoDetail.from_api(item)
            logger.info("提取详情成功: %s", detail.desc[:30])
            result["video_detail"] = detail.to_dict()
            
            # 处理并发监听拿到的初始评论
            initial_comments = []
            if initial_comments_data and isinstance(initial_comments_data, dict):
                items = initial_comments_data.get("comments") or []
                for c in items:
                    try:
                        initial_comments.append(Comment.from_api(c))
                    except Exception as e:
                        logger.warning("解析初始评论失败: %s", e)
                logger.info("✅ 成功在页面加载时并发捕获到 %d 条初始评论", len(initial_comments))
            
            # 如果需要更多评论，继续后续逻辑
            if target_comments > 0:
                logger.info("等待页面加载稳定准备侧边栏滚动...")
                page.wait_dom_stable()
                time.sleep(2.0)
                # 将捕获到的首批初始评论传入供滚动去重逻辑使用
                final_comments = scroll_and_extract_comments(page, target_comments, initial_comments)
                result["comments"] = [c.to_dict() for c in final_comments]
                
    if not result["video_detail"]:
        logger.warning("未能通过链接捕获到视频详情 API 数据")
        
    return result


def close_video(page: BridgePage) -> None:
    """关闭当前视频播放。"""
    page.evaluate("window.history.back()")
    random_delay(1.5, 2.5)
