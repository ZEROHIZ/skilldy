import logging
import sys
import os
import json

# 添加 scripts 目录到 path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dy.bridge import BridgePage
from dy.search import search_videos
from dy.video_detail import get_video_detail, close_video
from dy.comments import get_comments

# 配置日志
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("test-loop")

def test_loop(keyword="美食", repeat_count=4):
    page = BridgePage()
    
    if not page.is_server_running():
        logger.error("Bridge server is not running!")
        return

    try:
        # 1. 搜索
        logger.info(f"开始搜索关键词: {keyword}")
        videos = search_videos(page, keyword, scroll_times=1)
        if not videos:
            logger.error("搜不到视频，停止测试")
            return
        
        logger.info(f"搜索完成，获取到 {len(videos)} 个视频对象")
        
        # 2. 循环处理前 N 个视频
        for i in range(min(repeat_count, len(videos))):
            video = videos[i]
            logger.info(f"--- 正在处理第 {i+1}/{repeat_count} 个视频: {video.video_id} ---")
            
            try:
                # 点击进入详情，通过视频描述文本定位
                detail = get_video_detail(page, desc=video.desc)
                logger.info(f"进入视频详情成功: {detail.video_id}")
                
                # 获取评论
                comments = get_comments(page, video.video_id, scroll_times=1)
                logger.info(f"获取到 {len(comments)} 条评论")
                
                # 关闭视频
                logger.info("正在关闭视频...")
                close_video(page)
                
                logger.info(f"第 {i+1} 个视频处理完成")
                
            except Exception as e:
                logger.error(f"处理第 {i+1} 个视频时出错: {e}")
                # 尝试强制关闭/返回，以免影响下一个
                try:
                    close_video(page)
                except:
                    pass
                    
        logger.info("测试流程全部结束")

    except Exception as e:
        logger.error(f"自动化流程异常: {e}")

if __name__ == "__main__":
    test_loop()
