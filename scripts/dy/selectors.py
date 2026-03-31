from .urls import (
    SEARCH_INPUT_SELECTOR,
    SEARCH_BUTTON_SELECTOR,
    COMMENT_ICON_SELECTOR,
    COMMENT_LIST_SELECTOR,
    LIKE_BUTTON_SELECTOR,
    COLLECT_BUTTON_SELECTOR,
    SHARE_ICON_SELECTOR
)

# ========== 登录相关 ==========
LOGIN_CONTAINER = "#login-pannel"  # 登录面板
LOGIN_AVATAR = ".d2gZIfU_"  # 登录后的用户头像容器

# ========== Feed 列表 ==========
FEED_ITEM = ".xgplayer-playing, .slider-video, [data-e2e='feed-active-video']"

# ========== 搜索 ==========
SEARCH_INPUT = SEARCH_INPUT_SELECTOR
SEARCH_BUTTON = SEARCH_BUTTON_SELECTOR
# SEARCH_VIDEO_TITLE = "div.BjLsdJMi"  # 搜索结果中视频标题（点击进入播放）

# ========== 博主主页 ==========
# AUTHOR_VIDEO_TITLE = "p.eJFBAbdI"  # 博主作品列表中视频标题

# ========== 评论 ==========
COMMENT_ICON = COMMENT_ICON_SELECTOR  # 评论图标（取第一个）
COMMENT_LIST = COMMENT_LIST_SELECTOR  # 评论列表容器（用于滚动）
COMMENT_ITEM = '[data-e2e="comment-item"]'  # 单条评论

# ========== 视频关闭 ==========
# 关闭按钮的 class 会变，唯一不变的是内部 svg 的 xmlns 和 X 形的 path
# 选择器匹配：包含关闭 svg 图标的父 div
VIDEO_CLOSE_BUTTON = 'div.pGZF8lyn svg[xmlns="http://www.w3.org/2000/svg"]'


# ========== 视频详情 ==========
VIDEO_TITLE = ".video-info-detail h1"
AUTHOR_NAME = ".account-name"
LIKE_COUNT = "[data-e2e='feed-active-video'] [data-e2e='video-player-like'] .like-text, .player-toolbar-container .like-text"
COMMENT_COUNT = "[data-e2e='feed-active-video'] [data-e2e='video-player-comment'] .comment-text, .player-toolbar-container .comment-text"
COLLECT_COUNT = "[data-e2e='feed-active-video'] [data-e2e='video-player-collect'] .collect-text, .player-toolbar-container .collect-text"

# ========== 互动操作 ==========
LIKE_BUTTON = LIKE_BUTTON_SELECTOR
COLLECT_BUTTON = COLLECT_BUTTON_SELECTOR
COMMENT_TRIGGER = COMMENT_ICON  # 复用评论图标
COMMENT_INPUT = "div[contenteditable='true'][role='textbox'], .comment-input-area"
COMMENT_SUBMIT = "[data-e2e='comment-submit'], .comment-submit-btn"
SHARE_ICON = SHARE_ICON_SELECTOR  # 分享图标

# ========== 搜索筛选 ==========
FILTER_TRIGGER = "div.jjU9T0dQ"  # 筛选按钮
FILTER_OPTION = "span.eXMmo3JR"  # 筛选选项

# ========== 发布页 (创作者中心) ==========
UPLOAD_DRAG_AREA = ".upload-drag-area, .upload-container"
FILE_INPUT = "input[type='file']"
PUBLISH_TITLE_INPUT = ".title-input-container input, [data-e2e='publish-video-title']"
PUBLISH_SUBMIT_BUTTON = ".publish-btn, [data-e2e='publish-video-submit']"
