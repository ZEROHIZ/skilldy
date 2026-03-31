"""抖音数据类型定义。"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AuthorInfo:
    """博主/作者信息。"""
    sec_uid: str
    nickname: str
    uid: str = ""
    avatar_url: str = ""
    follower_count: int = 0
    following_count: int = 0
    total_favorited: int = 0
    signature: str = ""

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "AuthorInfo":
        avatar = ""
        thumb = data.get("avatar_thumb") or {}
        urls = thumb.get("url_list") or []
        if urls:
            avatar = urls[0]
        
        # 统计数据可能在 statistics 嵌套对象中
        stats = data.get("statistics") or {}
        
        return cls(
            sec_uid=data.get("sec_uid", ""),
            nickname=data.get("nickname", ""),
            uid=str(data.get("uid", "")),
            avatar_url=avatar,
            follower_count=int(data.get("follower_count") or stats.get("follower_count") or 0),
            following_count=int(data.get("following_count") or stats.get("following_count") or 0),
            total_favorited=int(data.get("total_favorited") or stats.get("total_favorited") or 0),
            signature=data.get("signature", ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "follower_count": self.follower_count,
        }


def _extract_play_url(url_list: list[str]) -> str:
    """从地址列表中优先提取包含 www.douyin.com 的 URL。"""
    if not url_list:
        return ""
    # 优先寻找包含 douyin.com 的链接
    for url in url_list:
        if "www.douyin.com" in url:
            return url
    # 兜底：返回第一个
    return url_list[0]


@dataclass
class VideoItem:
    """视频列表项（搜索结果/博主主页/推荐流）。"""
    video_id: str
    desc: str
    author_name: str
    author_id: str
    # 扩展字段
    play_url: str = ""
    duration: int = 0
    create_time: int = 0
    digg_count: int = 0
    comment_count: int = 0
    collect_count: int = 0
    share_count: int = 0

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "VideoItem":
        """从真实 API 响应解析（搜索/博主主页的 aweme_info）。"""
        author = data.get("author") or {}
        video_obj = data.get("video") or {}
            
        # 播放地址
        play_url = ""
        play_addr = video_obj.get("play_addr") or {}
        play_urls = play_addr.get("url_list") or []
        play_url = _extract_play_url(play_urls)
            
        # 时长
        duration = int(video_obj.get("duration") or data.get("duration") or 0)
        
        # 统计数据通常在 statistics 嵌套对象中
        stats = data.get("statistics") or {}

        return cls(
            video_id=data.get("aweme_id", ""),
            desc=data.get("desc", ""),
            author_name=author.get("nickname", ""),
            author_id=author.get("sec_uid", ""),
            play_url=play_url,
            duration=duration,
            create_time=int(data.get("create_time") or 0),
            digg_count=int(stats.get("digg_count") or data.get("digg_count") or 0),
            comment_count=int(stats.get("comment_count") or data.get("comment_count") or 0),
            collect_count=int(stats.get("collect_count") or data.get("collect_count") or 0),
            share_count=int(stats.get("share_count") or data.get("share_count") or 0),
        )

    @classmethod
    def parse_api_list(cls, data: dict[str, Any]) -> list["VideoItem"]:
        """统一解析 API 返回的视频列表数据（支持 search 和 author_posts）。"""
        # 兼容不同层级的 data/aweme_list
        items = data.get("data", []) or data.get("aweme_list", [])
        results = []
        if items:
            for item in items:
                # 兼容嵌套 aweme_info 或直接是 aweme 对象的结构
                aweme = item.get("aweme_info") if isinstance(item, dict) and "aweme_info" in item else item
                if aweme and isinstance(aweme, dict):
                    results.append(cls.from_api(aweme))
        return results

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VideoItem":
        """兼容旧版 DOM 数据结构的降级解析。"""
        return cls(
            video_id=data.get("aweme_id") or data.get("id", ""),
            desc=data.get("desc", ""),
            author_name=data.get("author", {}).get("nickname", ""),
            author_id=data.get("author", {}).get("sec_uid", ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "video_id": self.video_id,
            "desc": self.desc,
            "author_name": self.author_name,
            "author_id": self.author_id,
            "play_url": self.play_url,
            "duration": self.duration,
            "create_time": self.create_time,
            "digg_count": self.digg_count,
            "comment_count": self.comment_count,
            "collect_count": self.collect_count,
            "share_count": self.share_count,
        }


@dataclass
class VideoDetail:
    """视频详情（完整统计 + 播放地址）。"""
    video_id: str
    desc: str
    author_name: str
    sec_uid: str = ""
    follower_count: int = 0
    like_count: int = 0
    comment_count: int = 0
    collect_count: int = 0
    share_count: int = 0
    play_url: str = ""
    create_time: int = 0
    tags: list[str] = field(default_factory=list)

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "VideoDetail":
        """从 aweme/v1/web/aweme/detail API 解析。"""
        author_data = data.get("author") or {}
        author = AuthorInfo.from_api(author_data)

        # 播放地址
        video_obj = data.get("video") or {}
        play_addr = video_obj.get("play_addr") or {}
        play_urls = play_addr.get("url_list") or []
        play_url = _extract_play_url(play_urls)

        # 标签
        tags = []
        text_extra = data.get("text_extra") or []
        for te in text_extra:
            hn = te.get("hashtag_name", "")
            if hn:
                tags.append(hn)
        
        # 统计数据通常在 statistics 嵌套对象中
        stats = data.get("statistics") or {}

        return cls(
            video_id=data.get("aweme_id", ""),
            desc=data.get("desc", ""),
            author_name=author.nickname,
            sec_uid=author.sec_uid,
            follower_count=author.follower_count,
            like_count=int(stats.get("digg_count") or data.get("digg_count") or 0),
            comment_count=int(stats.get("comment_count") or data.get("comment_count") or 0),
            collect_count=int(stats.get("collect_count") or data.get("collect_count") or 0),
            share_count=int(stats.get("share_count") or data.get("share_count") or 0),
            play_url=play_url,
            create_time=int(data.get("create_time") or 0),
            tags=tags,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "video_id": self.video_id,
            "desc": self.desc,
            "author_name": self.author_name,
            "sec_uid": self.sec_uid,
            "follower_count": self.follower_count,
            "like_count": self.like_count,
            "comment_count": self.comment_count,
            "collect_count": self.collect_count,
            "share_count": self.share_count,
            "play_url": self.play_url,
            "create_time": self.create_time,
            "tags": self.tags,
        }


@dataclass
class Comment:
    """视频评论。"""
    comment_id: str
    content: str
    author: str
    like_count: int
    reply_count: int = 0
    create_time: int = 0
    author_avatar: str = ""
    sec_uid: str = ""
    ip_label: str = ""

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "Comment":
        """从 aweme/v1/web/comment/list API 解析。"""
        user = data.get("user") or {}
        avatar = ""
        thumb = user.get("avatar_thumb") or {}
        urls = thumb.get("url_list") or []
        if urls:
            avatar = urls[0]
        return cls(
            comment_id=str(data.get("cid", "")),
            content=data.get("text", ""),
            author=user.get("nickname", ""),
            like_count=int(data.get("digg_count") or 0),
            reply_count=int(data.get("reply_comment_total") or 0),
            create_time=int(data.get("create_time") or 0),
            author_avatar=avatar,
            sec_uid=user.get("sec_uid", ""),
            ip_label=data.get("ip_label", ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "comment_id": self.comment_id,
            "content": self.content,
            "author": self.author,
            "like_count": self.like_count,
            "reply_count": self.reply_count,
            "create_time": self.create_time,
            "sec_uid": self.sec_uid,
            "ip_label": self.ip_label,
        }
