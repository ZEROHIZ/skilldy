"""搜索视频 - 人类化交互模式。

流程：点击搜索框 → 输入关键词 → 点击搜索按钮 → 监听 API 获取结果 → 可选筛选 → 可选下拉加载更多。
"""

import json
import logging

from .bridge import BridgePage
from .human import random_delay, human_click
from .types import VideoItem
# 全部从 urls.py 导入，方便用户集中修改
from .urls import (
    HOME_URL,
    API_SEARCH,
    FILTER_SVG_PATH,
    SEARCH_FILTERS,
    SEARCH_INPUT_SELECTOR,
    SEARCH_BUTTON_SELECTOR,
    API_AUTHOR_POSTS
)
# 注意：避免循环导入，我们在这里延迟导入或直接实现解析

# ─── 筛选关键字映射 ───
FILTER_KEYWORD_MAP = {
    "最新发布": "最新发布", "latest": "最新发布",
    "最多点赞": "最多点赞", "点赞最多": "最多点赞", "like": "最多点赞",
    "一天内": "一天内", "24小时": "一天内", "1d": "一天内",
    "一周内": "一周内", "7天": "一周内", "1w": "一周内",
    "半年内": "半年内", "6个月": "半年内", "6m": "半年内",
    "一分钟以下": "一分钟以下", "短视频": "一分钟以下", "<1min": "一分钟以下",
    "1-5分钟": "1-5分钟", "中等长度": "1-5分钟", "1-5min": "1-5分钟",
    "5分钟以上": "5分钟以上", "长视频": "5分钟以上", ">5min": "5分钟以上",
    "关注的人": "关注的人", "关注": "关注的人", "following": "关注的人",
    "最近看过": "最近看过", "看过": "最近看过", "seen": "最近看过",
    "还未看过": "还未看过", "未看": "还未看过", "not_seen": "还未看过",
    "图文": "图文", "图片": "图文", "note": "图文",
    "视频": "视频", "video": "视频",
}

logger = logging.getLogger(__name__)


def search_videos(page: BridgePage, keyword: str,
                  scroll_times: int = 0,
                  filter_type: str | None = None) -> list[VideoItem]:
    """搜索视频列表（人类化操作 + API 监听）。"""
    logger.info("搜索关键词: %s", keyword)

    _ensure_search_input_ready(page)
    human_click(page, SEARCH_INPUT_SELECTOR, pre_delay=(0.3, 0.8), post_delay=(0.3, 0.6))

    # 弃用 CDP 键盘操作，全部改由纯 JS 事件注入，避免产生调试器指纹
    random_delay(0.2, 0.5)

    logger.info("启动 API 监听 + 原生模拟输入 + 点击搜索...")
    trigger_js = f"""
    (async () => {{
        const input = document.querySelector('{SEARCH_INPUT_SELECTOR}');
        if (!input) return;
        
        input.focus();
        const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
        
        // 1. 清空原内容
        if (setter) {{ setter.call(input, ''); }} else {{ input.value = ''; }}
        input.dispatchEvent(new Event('input', {{ bubbles: true }}));
        await new Promise(r => setTimeout(r, 100));

        // 2. 模拟逐字敲击
        const keyword = '{keyword}';
        for (let i = 0; i < keyword.length; i++) {{
            const char = keyword[i];
            
            input.dispatchEvent(new KeyboardEvent('keydown', {{ key: char, bubbles: true }}));
            input.dispatchEvent(new KeyboardEvent('keypress', {{ key: char, bubbles: true }}));
            
            if (setter) {{ setter.call(input, input.value + char); }} else {{ input.value += char; }}
            input.dispatchEvent(new Event('input', {{ bubbles: true }}));
            
            input.dispatchEvent(new KeyboardEvent('keyup', {{ key: char, bubbles: true }}));
            
            await new Promise(r => setTimeout(r, 50 + Math.random() * 100));
        }}
        
        await new Promise(r => setTimeout(r, 300));
        
        // 3. 触发搜索
        input.dispatchEvent(new KeyboardEvent('keydown', {{ key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true }}));
        input.dispatchEvent(new KeyboardEvent('keyup', {{ key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true }}));
        
        await new Promise(r => setTimeout(r, 200));
        const btn = document.querySelector('{SEARCH_BUTTON_SELECTOR}');
        if (btn) {{ btn.click(); }}
    }})()
    """
    api_data = page.listen_api(url_pattern=API_SEARCH, trigger_expression=trigger_js, timeout=25.0)

    all_results = []
    if api_data and isinstance(api_data, dict):
        all_results = VideoItem.parse_api_list(api_data)
        if all_results:
            logger.info("搜索环节获取到 %d 条视频结果", len(all_results))

    if filter_type:
        filtered = filter_current_videos(page, filter_type)
        if filtered:
            all_results = filtered

    if scroll_times > 0:
        logger.info("开始下拉加载更多，共 %d 次", scroll_times)
        more = scroll_more_videos(page, scroll_times)
        all_results.extend(more)
        logger.info("下拉加载完成，总共 %d 条结果", len(all_results))

    return all_results


def filter_current_videos(page: BridgePage, filter_types: str) -> list[VideoItem]:
    """在当前已打开的搜索结果页应用一个或多个筛选条件 (逗号分隔)。"""
    type_list = [t.strip() for t in filter_types.split(",") if t.strip()]
    logger.info("开始按顺序执行多重筛选: %s", type_list)
    
    final_results = []
    
    for i, filter_type in enumerate(type_list):
        standard_text = FILTER_KEYWORD_MAP.get(filter_type, filter_type)
        logger.info("应用筛选条件 [%d/%d]: %s (映射后: %s)", i + 1, len(type_list), filter_type, standard_text)
        
        # 每次点击前确保菜单展开（因为点击一个后菜单通常会关闭）
        _expand_filter_menu(page)
        random_delay(1.0, 1.5)

        click_option_js = f"""
        (() => {{
            const target = '{standard_text}';
            const allEls = Array.from(document.querySelectorAll('span, div, li, a, button, p'));
            const targetEl = allEls.find(el => el.innerText.trim() === target);
            if (targetEl) {{
                targetEl.scrollIntoView({{ block: 'center' }});
                ['mousedown', 'mouseup', 'click'].forEach(name => {{
                    const event = new MouseEvent(name, {{ view: window, bubbles: true, cancelable: true, buttons: 1 }});
                    targetEl.dispatchEvent(event);
                }});
                return "SUCCESS";
            }}
            return "NOT_FOUND";
        }})()
        """
        logger.info("执行筛选点击并监听 API...")
        api_data = page.listen_api(url_pattern=API_SEARCH, trigger_expression=click_option_js, timeout=20.0)

        if api_data and isinstance(api_data, dict):
            final_results = VideoItem.parse_api_list(api_data)
            logger.info("筛选 [%s] 成功，当前结果数: %d", filter_type, len(final_results))
        else:
            logger.warning("筛选 [%s] 未捕获到新 API 数据", filter_type)
            # 如果中间某个点失败了，我们继续尝试下一个，或者直接返回
            
    return final_results


def visit_author(page: BridgePage, sec_uid: str) -> None:
    """直接通过 sec_uid 导航到博主主页。"""
    url = f"https://www.douyin.com/user/{sec_uid}"
    logger.info("直接导航到博主主页: %s", url)
    page.navigate(url)
    page.wait_for_load()


def click_author(page: BridgePage, index: int = 1) -> list[VideoItem]:
    """通过第 N 个视频的作者名进入主页，并自动监听抓取作品。"""
    logger.info("模拟进入第 %d 个视频的作者主页并抓取作品...", index)
    
    # 提取 UID 逻辑
    js_get_uid = f"""
    (() => {{
        const index = {index - 1};
        const cards = Array.from(document.querySelectorAll('div[data-e2e="search_card"], .SearchVideoCard-container, div[class*="Card"]'));
        let targetLink = (cards.length > index) ? cards[index].querySelector('a[href*="/user/"]') : null;
        
        if (!targetLink) {{
             // 放弃对 innerText 的过滤，有些版本作者名在 span 里
             const allUserLinks = Array.from(document.querySelectorAll('a[href*="/user/"]:not([href*="self"])'));
             targetLink = allUserLinks[index];
        }}

        if (targetLink) {{
            const href = targetLink.getAttribute('href') || '';
            const sec_uid = href.split('/user/')[1]?.split('?')[0];
            if (sec_uid && sec_uid !== 'self') return sec_uid;
        }}
        return null;
    }})()
    """
    sec_uid = page.evaluate(js_get_uid)
    if not sec_uid:
        logger.warning("未能在当前页面找到第 %d 个视频的博主 sec_uid", index)
        return []

    # 直接使用 listen_api 配合直接导航，实现“进入+抓取”
    profile_url = f"https://www.douyin.com/user/{sec_uid}"
    logger.info("提取到博主 %s，正在执行监听并跳转...", sec_uid)

    api_data = page.listen_api(
        url_pattern=API_AUTHOR_POSTS,
        navigate_url=profile_url,
        timeout=20.0,
        new_tab=True # 开启新标签页跳转
    )

    if api_data and isinstance(api_data, dict):
        # 使用统一解析函数
        results = VideoItem.parse_api_list(api_data)
        if results:
            logger.info("进入主页成功，自动捕获到 %d 条作品", len(results))
            return results
    
    logger.warning("进入主页后未捕获到作品 API 数据")
    return []




def _ensure_search_input_ready(page: BridgePage):
    """确保处于搜索页且搜索框可见。"""
    if "douyin.com" not in page.get_url():
        page.navigate("https://www.douyin.com")
        page.wait_for_load()
    
    try:
        page.wait_for_element(SEARCH_INPUT_SELECTOR, timeout=5.0)
    except:
        page.navigate("https://www.douyin.com")
        page.wait_for_load()
        page.wait_for_element(SEARCH_INPUT_SELECTOR, timeout=5.0)


def _expand_filter_menu(page: BridgePage) -> None:
    """悬停展开搜索筛选菜单。"""
    js_hover_filter = f"""
    (() => {{
        const targetPath = "{FILTER_SVG_PATH}";
        const svgs = document.querySelectorAll('svg');
        for (const svg of svgs) {{
            const path = svg.querySelector('path');
            if (path) {{
                const d = path.getAttribute('d') || '';
                if (d === targetPath || d.includes("10.5a.75.75")) {{
                    let playable = svg.parentElement;
                    while (playable && playable.tagName !== 'DIV' && playable.tagName !== 'BUTTON') {{
                        playable = playable.parentElement;
                    }}
                    if (playable) {{
                        const events = ['mouseenter', 'mouseover', 'mousemove'];
                        events.forEach(name => {{
                            const event = new MouseEvent(name, {{ view: window, bubbles: true, cancelable: true }});
                            playable.dispatchEvent(event);
                        }});
                        return true;
                    }}
                }}
            }}
        }}
        return false;
    }})()
    """
    page.evaluate(js_hover_filter)


def scroll_more_videos(page: BridgePage, scroll_times: int, container_selector: str = ".child-route-container.route-scroll-container") -> list[VideoItem]:
    """在搜索结果页下拉加载更多视频。"""
    more_results = []
    
    logger.info("开始执行下拉操作，目标容器: %s，计划下拉 %d 次", container_selector, scroll_times)
    
    for i in range(scroll_times):
        random_delay(1.5, 3.0)
        logger.info(">>>>>>>>>> 正在准备第 [%d/%d] 次下拉...", i + 1, scroll_times)
        
        trigger_js = f"""
        (async () => {{
            const sel = '{container_selector}';
            let container = document.querySelector(sel);
            
            // 兜底方案：如果没找到指定容器，寻找备用的滚动条div
            if (!container) {{
                const scrollables = Array.from(document.querySelectorAll('div')).filter(el => {{
                    const style = window.getComputedStyle(el);
                    return style.overflowY === 'scroll' || style.overflowY === 'auto';
                }});
                // 优先选取内容较高的
                if (scrollables.length > 0) {{
                    container = scrollables.sort((a, b) => b.scrollHeight - a.scrollHeight)[0];
                }}
            }}
            
            if (!container) {{
                return {{"error": "没有找到可滚动的容器！无法下拉"}};
            }}
            
            const beforeScroll = container.scrollTop;
            const scrollStep = 500 + Math.random() * 500;
            container.scrollBy({{ top: scrollStep, behavior: 'smooth' }});
            
            await new Promise(r => setTimeout(r, 600)); // 等待平滑滚动完成
            const afterScroll = container.scrollTop;
            
            return {{
                "success": true, 
                "before": beforeScroll, 
                "after": afterScroll, 
                "step": scrollStep,
                "scrollHeight": container.scrollHeight
            }};
        }})()
        """
        
        logger.info("触发原生页面下拉动作并等待新 API 数据...")
        api_data = page.listen_api(url_pattern=API_SEARCH, trigger_expression=trigger_js, timeout=12.0)
        
        if api_data and isinstance(api_data, dict):
            items = VideoItem.parse_api_list(api_data)
            if items:
                more_results.extend(items)
                logger.info("下拉 [%d/%d] 成功，抓取并解析到 %d 条新视频。", i + 1, scroll_times, len(items))
            else:
                logger.warning("下拉 [%d/%d] 拦截到了 API，但未解析出有效视频项目。可能到达底部或发生变动。", i + 1, scroll_times)
                # 可以选择 continue 或 break，为了激进一点我们这里 break
                break
        else:
            logger.warning("下拉 [%d/%d] 未捕获到匹配的 API 响应 (可能页面没发生网络请求或超时)。", i + 1, scroll_times)
            break
            
    logger.info("下拉加载全部完成，总计额外新增 %d 条", len(more_results))
    return more_results
