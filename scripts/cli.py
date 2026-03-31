"""统一 CLI 工具入口。"""

import argparse
import json
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dy.bridge import BridgePage
from dy.errors import DYError, NotLoggedInError
from dy.login import check_login
from dy.feeds import list_feeds
from dy.search import search_videos, filter_current_videos, visit_author, click_author, scroll_more_videos
from dy.video_detail import get_video_detail, get_video_detail_by_url, close_video
from dy.interact import like_video, favorite_video, post_comment
from dy.publish import publish_video
from dy.author_posts import get_author_posts
from dy.comments import get_comments, scroll_more_comments
from dy.share import share_video

# 配置根日志（仅输出 ERROR 以上），避免污染 stdout
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("dy-cli")

def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="抖音自动化 CLI 工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # 1. 查询类
    subparsers.add_parser("check-login", help="检查登录状态")
    subparsers.add_parser("list-feeds", help="[未开放] 获取推荐流视频")
    p_search = subparsers.add_parser("search-videos", help="搜索视频")
    p_search.add_argument("--keyword", required=True, help="搜索关键词")
    p_search.add_argument("--scroll-times", type=int, default=0, help="搜索后下拉加载更多结果的次数（默认 0 不下拉）")
    p_search.add_argument("--filter", dest="filter_type", help="筛选条件文本，如 '最多点赞' '最新发布' '一天内'等")
    p_detail = subparsers.add_parser("get-video-detail", help="获取视频详情")
    p_detail.add_argument("--video-id", required=True, help="视频 ID（用于精准定位）")

    # 2. 互动类
    p_like = subparsers.add_parser("like-video", help="点赞视频")
    p_like.add_argument("--video-id", required=True, help="视频 ID")
    p_fav = subparsers.add_parser("favorite-video", help="收藏视频")
    p_fav.add_argument("--video-id", required=True, help="视频 ID")
    p_cmnt = subparsers.add_parser("post-comment", help="[未开放] 发表评论")
    p_cmnt.add_argument("--video-id", required=True, help="视频 ID")
    p_cmnt.add_argument("--content", required=True, help="评论内容")

    # 3. 发布类
    p_pub = subparsers.add_parser("publish-video", help="[未开放] 发布视频")
    p_pub.add_argument("--video-file", required=True, help="本地视频文件路径")
    p_pub.add_argument("--title", required=True, help="视频标题")
    p_pub.add_argument("--tags", nargs="*", help="标签列表（可选）")

    # 4. 筛选与跳转类
    p_filter = subparsers.add_parser("filter-videos", help="在当前搜索结果页应用筛选")
    p_filter.add_argument("--type", required=True, help="筛选条件文本 (如: '最多点赞', '一周内')")
    
    p_scroll = subparsers.add_parser("scroll-videos", help="在当前页面继续下拉获取更多视频")
    p_scroll.add_argument("--scroll-times", type=int, default=1, help="下拉次数 (默认 1)")

    p_visit = subparsers.add_parser("visit-author", help="直接进入博主主页")
    p_visit.add_argument("--sec-uid", required=True, help="博主 sec_uid")

    p_click_auth = subparsers.add_parser("click-author", help="点击搜索结果中的作者名进入主页")
    p_click_auth.add_argument("--index", type=int, default=1, help="第几个视频的作者 (1-based)")

    # 5. 数据获取类
    p_author = subparsers.add_parser("get-author-posts", help="获取博主视频列表")
    p_author.add_argument("--sec-uid", help="博主 sec_uid")
    p_author.add_argument("--url", help="直接指定博主主页 URL")
    p_cmnt_list = subparsers.add_parser("get-comments", help="获取视频评论列表")
    p_cmnt_list.add_argument("--video-id", required=True, help="视频 ID")
    p_cmnt_list.add_argument("--scroll-times", type=int, default=0, help="获取评论时自动下拉的次数（默认 0）")

    p_share = subparsers.add_parser("share-video", help="点击分享按钮并获取短链接")
    p_share.add_argument("--video-id", required=True, help="视频 ID（用于精确定位视频容器）")

    p_scroll_cmnt = subparsers.add_parser("scroll-comments", help="在当前已打开的评论面板继续下拉获取更多评论")
    p_scroll_cmnt.add_argument("--video-id", required=True, help="视频 ID")
    p_scroll_cmnt.add_argument("--scroll-times", type=int, default=1, help="下拉次数 (默认 1)")

    p_share_url = subparsers.add_parser("open-share-url", help="通过分享链接获取视频详情")
    p_share_url.add_argument("--share-url", required=True, help="视频分享链接")
    p_share_url.add_argument("--comments", type=int, default=0, help="获取评论的数量")

    # 6. 页面控制类
    subparsers.add_parser("close-video", help="关闭当前视频播放，返回搜索结果页")

    # 统一追加 --format 和 -o 参数到所有子命令
    for name, subp in subparsers.choices.items():
        subp.add_argument("--format", choices=["json", "text"], default="json", help="输出格式（默认json）")
        subp.add_argument("-o", "--output", help="输出到指定JSON文件")

    return parser

def main() -> None:
    # 强制 stdout 输出 utf-8
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = create_parser()
    args = parser.parse_args()

    page = BridgePage()

    # 先检查服务是否可达
    if not page.is_server_running():
        print(json.dumps({"error": "本地 bridge server 未启动，请先运行 python scripts/bridge_server.py"}))
        sys.exit(2)
        
    if not page.is_extension_connected():
        print(json.dumps({"error": "Chrome 扩展未连接到 bridge server"}))
        sys.exit(2)

    try:
        result_data = None
        
        if args.command == "check-login":
            result_data = {"logged_in": check_login(page)}

        elif args.command == "list-feeds":
            result_data = {"error": "推荐流功能尚未开放"}

        elif args.command == "search-videos":
            videos = search_videos(page, args.keyword,
                                   scroll_times=args.scroll_times,
                                   filter_type=args.filter_type)
            result_data = [v.to_dict() for v in videos]

        elif args.command == "filter-videos":
            videos = filter_current_videos(page, args.type)
            result_data = [v.to_dict() for v in videos]
            
        elif args.command == "scroll-videos":
            videos = scroll_more_videos(page, args.scroll_times)
            result_data = [v.to_dict() for v in videos]

        elif args.command == "visit-author":
            visit_author(page, args.sec_uid)
            result_data = {"success": True, "message": f"已导航到博主 {args.sec_uid}"}
            print(f"OK: 已导航到博主 {args.sec_uid}")

        elif args.command == "click-author":
            videos = click_author(page, args.index)
            if videos:
                result_data = [v.to_dict() for v in videos]
            else:
                result_data = {"error": "未能获取博主作品数据"}

        elif args.command == "get-video-detail":
            detail = get_video_detail(page, video_id=args.video_id)
            result_data = detail.to_dict()

        elif args.command == "open-share-url":
            result_data = get_video_detail_by_url(page, args.share_url, target_comments=args.comments)

        elif args.command == "like-video":
            result_data = {"success": like_video(page, args.video_id)}

        elif args.command == "favorite-video":
            result_data = {"success": favorite_video(page, args.video_id)}

        elif args.command == "post-comment":
            result_data = {"error": "发评论功能尚未开放"}

        elif args.command == "publish-video":
            result_data = {"error": "发布功能尚未开放"}

        elif args.command == "get-author-posts":
            if not args.sec_uid and not args.url:
                result_data = {"error": "必须提供 --sec-uid 或 --url 中的一个"}
                print(json.dumps(result_data))
                sys.exit(2)
            posts = get_author_posts(page, sec_uid=args.sec_uid, url=args.url)
            if isinstance(posts, dict):
                result_data = posts # 直接使用原始元数据
            elif isinstance(posts, list):
                result_data = [p.to_dict() if hasattr(p, 'to_dict') else p for p in posts]
            else:
                result_data = posts

        elif args.command == "get-comments":
            cms = get_comments(page, video_id=args.video_id, scroll_times=args.scroll_times)
            result_data = [c.to_dict() for c in cms]

        elif args.command == "share-video":
            result_data = share_video(page, args.video_id)

        elif args.command == "scroll-comments":
            comments = scroll_more_comments(page, video_id=args.video_id, scroll_times=args.scroll_times)
            result_data = [c.to_dict() for c in comments]

        elif args.command == "close-video":
            close_video(page)
            result_data = {"success": True}

        if result_data is not None:
            # 标准输出依然打印给父进程（不带 indent，便于父进程解析）
            print(json.dumps(result_data, ensure_ascii=False))
            # 如果指定了 --output 则格式化写入文件供调试
            if getattr(args, "output", None):
                with open(args.output, "w", encoding="utf-8") as f:
                    json.dump(result_data, f, ensure_ascii=False, indent=4)
                logger.info(f"结果已成功写入文件: {args.output}")

        sys.exit(0)

    except NotLoggedInError as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)
    except DYError as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(2)
    except Exception as e:
        print(json.dumps({"error": f"未知异常: {e}"}))
        sys.exit(2)

if __name__ == "__main__":
    main()
