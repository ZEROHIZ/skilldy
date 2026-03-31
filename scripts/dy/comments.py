"""视频评论列表 - 人类化交互模式。

前置条件：用户已在视频播放页面。
流程：点击评论图标 → 监听评论 API → 滚动加载更多评论。
"""

import logging
import time

from .bridge import BridgePage
from .human import random_delay, human_click, random_scroll
from .selectors import COMMENT_ICON, COMMENT_LIST
from .types import Comment
from .urls import (
    API_COMMENTS, 
    COMMENT_SVG_PATH, 
    COMMENT_SIDEBAR_CONTAINER, 
    COMMENT_SIDEBAR_BUTTON_PATH
)

logger = logging.getLogger(__name__)


def get_comments(page: BridgePage, video_id: str, scroll_times: int = 0) -> list[Comment]:
    """获取视频的评论列表（针对特定 video_id 的容器进行点击）。"""
    logger.info("获取评论列表: video_id=%s", video_id)
    random_delay(1.0, 2.0)

    # 1. 探测容器
    check_js = f"""
    (() => {{
        const container = document.querySelector('[data-e2e-vid="{video_id}"]');
        if (!container) return "ERR_CONTAINER_NOT_FOUND";
        const icon = container.querySelector('{COMMENT_ICON}');
        if (!icon) return "ERR_ICON_NOT_FOUND";
        return "READY";
    }})()
    """
    status = page.evaluate(check_js)
    if status != "READY":
        logger.error("❌ 探测失败: %s", status)
        return []

    # 2. 点击并监听
    scoped_selector = f'[data-e2e-vid="{video_id}"] {COMMENT_ICON}'
    logger.info("✅ 正在点击并触发 API 监听 (包含二次点击 semiTabcomment)...")
    
    trigger_js = f"""
    (() => {{
        const icon = document.querySelector('{scoped_selector}');
        if (icon) {{
            icon.click();
            // 延时等待评论侧边栏 DOM 挂载后，再去点击 '全部评论'/semiTabcomment Tab
            setTimeout(() => {{
                const tab = document.querySelector('[data-tabkey="semiTabcomment"]');
                if (tab) tab.click();
            }}, 800);
        }}
    }})()
    """
    
    api_data = page.listen_api(
        url_pattern=API_COMMENTS,
        trigger_expression=trigger_js, 
        timeout=15.0,
    )

    # 使用字典进行去重，Key 为 comment_id
    unique_comments: dict[str, Comment] = {}

    if api_data and isinstance(api_data, dict):
        comments_list = api_data.get("comments") or []
        for c_raw in comments_list:
            c = Comment.from_api(c_raw)
            unique_comments[c.comment_id] = c
        logger.info("API 监听成功，初始获取到 %d 条独立评论", len(unique_comments))

        # 3. 评论面板打开后，继续下拉
        if scroll_times > 0:
            scroll_results = scroll_more_comments(page, video_id=video_id, scroll_times=scroll_times)
            for c in scroll_results:
                unique_comments[c.comment_id] = c

    # 返回去重后的列表
    return list(unique_comments.values())


def scroll_more_comments(page: BridgePage, video_id: str, scroll_times: int = 2) -> list[Comment]:
    """在评论面板内模拟下拉并捕获新的评论，返回新捕获的所有评论。"""
    all_captured: dict[str, Comment] = {}
    
    # 增加探测逻辑
    debug_js = f"""
    (() => {{
        const scoped = document.querySelector('[data-e2e-vid="{video_id}"]');
        const list = document.querySelector('{COMMENT_LIST}');
        const scoped_list = scoped ? scoped.querySelector('{COMMENT_LIST}') : null;
        
        // 打印出当前页面所有带 data-e2e 的元素，帮我们分析结构
        const allE2E = Array.from(document.querySelectorAll('[data-e2e]')).map(el => el.getAttribute('data-e2e'));
        
        return {{
            "hasScoped": !!scoped,
            "hasGlobalList": !!list,
            "hasScopedList": !!scoped_list,
            "allE2E": allE2E.slice(0, 20) // 只取前20个防止日志太长
        }};
    }})()
    """
    debug_info = page.evaluate(debug_js)
    logger.info("滚动前容器探测结果: %s", debug_info)

    try:
        # 尝试使用更宽松的定位方式
        if debug_info.get("hasScopedList"):
            target_list_selector = f'[data-e2e-vid="{video_id}"] {COMMENT_LIST}'
        elif debug_info.get("hasGlobalList"):
            logger.info("⚠️ 没在视频容器内找到列表，但在全局找到了，尝试直接使用全局列表")
            target_list_selector = COMMENT_LIST
        else:
            logger.warning("❌ 未发现 ID 为 %s 的视频评论列表容器 (选择器: %s)", video_id, COMMENT_LIST)
            return []

        for i in range(scroll_times):
            logger.info("正在执行评论面板滚动 [%d/%d]...", i + 1, scroll_times)
            
            trigger_js = f"""
            (() => {{
                const el = document.querySelector('{target_list_selector}');
                if (el) {{
                    const old = el.scrollTop;
                    el.scrollTop = el.scrollHeight;
                    // 回拨一点点触发事件
                    setTimeout(() => {{ el.scrollTop -= 5; }}, 30);
                    return {{"before": old, "after": el.scrollTop, "max": el.scrollHeight}};
                }}
                return null;
            }})()
            """
            
            api_data = page.listen_api(
                url_pattern=API_COMMENTS,
                trigger_expression=trigger_js,
                timeout=12.0
            )

            if api_data and isinstance(api_data, dict):
                comments_list = api_data.get("comments") or []
                new_batch_count = 0
                for c_raw in comments_list:
                    c = Comment.from_api(c_raw)
                    if c.comment_id not in all_captured:
                        all_captured[c.comment_id] = c
                        new_batch_count += 1
                logger.info("滚动加载成功: 本次新增 %d 条独立评论 (当前累计捕获 %d 条)", new_batch_count, len(all_captured))
                random_delay(1.5, 2.5) # 给 API 冷却时间
            else:
                logger.warning("第 %d 次滚动未监听到 API 响应", i + 1)
                # 兜底：即使监听不到，也滚一下
                page.evaluate(trigger_js)
                random_delay(0.5, 1.0)
                
    except Exception as e:
        logger.error("评论面板滚动异常: %s", e)
        
    return list(all_captured.values())



def scroll_and_extract_comments(page: BridgePage, target_count: int, initial_comments: list[Comment] = None) -> list[Comment]:
    """通过侧边栏滚动提取多页评论数据，基于 comment_id 去重。
    
    Args:
        page: 已连接的 BridgePage 对象
        target_count: 目标爬取的评论数量（将根据独立的 unique comment_id 计数）
        initial_comments: 可选的在进入页面时已并发捕获的首批评论列表
    
    Returns:
        完整的、已去重的 Comment 对象列表
    """
    logger.info(f"开始侧边栏评论提取: 目标数量={target_count}")
    
    # 明确使用字典去重：Key 为 comment_id
    unique_comments: dict[str, Comment] = {}
    
    # 将初始传入的评论纳入去重池
    if initial_comments:
        for c in initial_comments:
            if c.comment_id and c.comment_id not in unique_comments:
                unique_comments[c.comment_id] = c
        logger.info(f"已装载初始评论 {len(unique_comments)} 条")
    
    # 1. 初始等待与状态记录
    max_retries = 3
    retry_count = 0
    last_count = len(unique_comments)
    
    # 2. 侧边栏评论通常在详情页加载时自动出现，如果不显示则无法滚动
    # 我们直接尝试开始滚动提取并监听 API_COMMENTS
    while len(unique_comments) < target_count:
        logger.info(f"正在滚动提取评论... (当前已获唯一评论: {len(unique_comments)}/{target_count})")
        
        # 触发滚动的 JS：严格遵循 urls.py 中的选择器
        trigger_js = f"""
        (() => {{
            const el = document.querySelector('{COMMENT_SIDEBAR_CONTAINER}');
            if (el) {{
                const oldTop = el.scrollTop;
                // 使用 scrollBy 模拟下拉行为，并派发事件
                el.scrollBy(0, 1000); 
                el.dispatchEvent(new Event('scroll', {{ bubbles: true }}));
                return oldTop !== el.scrollTop ? "SCROLLED" : "STAYED";
            }}
            return "NOT_FOUND";
        }})()
        """
        
        # 仅监听 API_COMMENTS，确保不混入详情页的其他 API 数据
        api_data = page.listen_api(
            url_pattern=API_COMMENTS,
            trigger_expression=trigger_js,
            timeout=10.0
        )

        if api_data and isinstance(api_data, dict):
            # 明确提取 'comments' 字段
            comments_list = api_data.get("comments") or []
            new_in_batch = 0
            for c_raw in comments_list:
                c = Comment.from_api(c_raw)
                if c.comment_id and c.comment_id not in unique_comments:
                    unique_comments[c.comment_id] = c
                    new_in_batch += 1
            
            logger.info(f"本轮捕获到 {len(comments_list)} 条数据，其中新评论 {new_in_batch} 条")
            
            # 判断是否有有效新数据增加
            if len(unique_comments) > last_count:
                retry_count = 0 
                last_count = len(unique_comments)
            else:
                retry_count += 1
        else:
            logger.warning("本轮滚动未监听到 API 响应")
            # 兜底滚动
            page.evaluate(trigger_js)
            retry_count += 1
            random_delay(1.5, 2.5)

        if retry_count >= max_retries:
            logger.warning(f"连续 {max_retries} 次未发现新评论，停止提取")
            break
            
        random_delay(1.0, 2.0)

    logger.info(f"提取任务结束: 目标 {target_count}, 实际获取唯一评论 {len(unique_comments)}")
    return list(unique_comments.values())
