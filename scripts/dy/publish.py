"""抖音发布：发布视频。"""

import logging
import time
import os
from .bridge import BridgePage
from .selectors import FILE_INPUT, PUBLISH_TITLE_INPUT, PUBLISH_SUBMIT_BUTTON
from .errors import DYError, ElementNotFoundError

logger = logging.getLogger(__name__)

PUBLISH_URL = "https://creator.douyin.com/creator-video/publish"

def publish_video(page: BridgePage, video_file: str, title: str, tags: list[str] = None) -> bool:
    """在创作者中心发布视频。"""
    if not os.path.exists(video_file):
        raise FileNotFoundError(f"视频文件不存在: {video_file}")
    
    logger.info(f"开启发布流程，视频文件: {video_file}")
    page.navigate(PUBLISH_URL)
    page.wait_for_load(timeout=30.0)
    page.wait_dom_stable()
    
    # 检测是否在登录页副本（创作者中心独立登录）
    if "login" in page.evaluate("window.location.href"):
        raise DYError("创作者中心未登录，请先在浏览器手动登录创作者中心")

    # 1. 触发文件上传
    # 抖音发布页通常有一个隐藏的 input[type='file']
    # 如果找不到，尝试等待一段时间或刷新缓存
    try:
        page.wait_for_element(FILE_INPUT, timeout=15)
    except ElementNotFoundError:
        # 如果找不到，输出当前页面状态辅助调试
        logger.error("未找到文件上传输入框，请确认是否处于发布页面且已加载。")
        raise
        
    page.set_file_input(FILE_INPUT, [video_file])
    logger.info("已提交视频文件上传")
    
    # 2. 等待页面转换（上传中 -> 填写信息）
    # 通常标题输入框出现代表上传已开始且可以填写信息
    page.wait_for_element(PUBLISH_TITLE_INPUT, timeout=60)
    time.sleep(2)
    
    # 3. 填写标题和标签
    full_title = title
    if tags:
        full_title += " " + " ".join([f"#{t}" for t in tags])
    
    page.click_element(PUBLISH_TITLE_INPUT)
    page.select_all_text(PUBLISH_TITLE_INPUT)
    page.press_key("Backspace")
    page.type_text(full_title)
    logger.info(f"已填写标题：{full_title}")
    
    # 4. 点击发布
    # 注意：可能需要等待上传进度 100% 按钮才可用，或者抖音会自动处理
    # 我们可以尝试点击发布，如果报错，多等一会
    time.sleep(5) # 基础等待
    page.wait_for_element(PUBLISH_SUBMIT_BUTTON, timeout=20)
    page.click_element(PUBLISH_SUBMIT_BUTTON)
    
    logger.info("已点击发布按钮")
    return True
