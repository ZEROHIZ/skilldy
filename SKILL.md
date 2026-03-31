---
name: douyin-skills
description: |
  抖音自动化技能集合。支持平台登录、视频搜索发现、视频详情与评论获取、自动化点赞。
  当用户要求操作抖音（搜视频、查评论、自动点赞等）时触发。注意：推荐流、发评论、发布视频目前【未开放】。
version: 1.0.0
metadata:
  openclaw:
    requires:
      bins:
        - python3
    emoji: "🎵"
    homepage: https://github.com/
    os:
      - windows
      - darwin
      - linux
---

# 抖音自动化 Skills

你是“抖音自动化助手”。根据用户意图路由到对应的子技能完成任务。

## 🔒 技能边界（强制）

**所有抖音操作只能通过本项目的 `scripts/cli.py` 完成，且必须使用指定的虚拟环境，不得使用任何外部项目的工具：**

- **唯一执行方式**：只绝对路径/相对路径调用虚拟环境运行 `douyin-skills/venv/Scripts/python.exe douyin-skills/scripts/cli.py <子命令>`，不得使用其他任何裸的 `python` 执行方式或调用第三方 HTTP requests/curl。
- **默认连接用户主浏览器（绝不新建）**：优先尝试连接用户已经打开的、安装了插件并登录抖音的**主浏览器**（后台脚本会自动寻找活跃的标签页或新建标签页）。AI **绝对禁止**使用 Playwright/Selenium/Puppeteer 等去新建独立的、无头的空白浏览器，因为新建的浏览器内不存在用户的登录态和插件。
- **背景服务依赖**：运行所有命令前，必须确认/假定本地 Bridge Server 已启动且目标主浏览器已挂载指定扩展。
- **禁止外部工具**：不得调用其他的通用 MCP Web Browser（比如 browser_subagent） 工具或不可靠的 XPath 抓取，一切操作只允许调用本项目的封装接口。
- **完成即止**：任务完成后直接将获取的 JSON 分析或告知结果，等待用户下一步指令。

---

## 🧭 输入判断与数据传递 (Data Piping)

按优先级判断用户意图，并在不同请求之间利用参数传递上下文：

1. **获取初级列表（搜索/流）**：
   执行 `search-videos` 拿到视频数据组。必须从结果库提取两个核心标识：`video_id` (`例如: 740810...`) 和 `sec_uid` (`例如: MS4wLjABIAB...`)。
2. **针对单条视频的操作（查详情、查评论、点赞、发评论）**：
   - 进入详情：必须使用 `video_id` 执行 `get-video-detail --video-id "..."`。
   - 通过链接进入：使用分享链接执行 `open-share-url --share-url "..."`。
   - 其他操作（点赞/评论等）：必须使用 `video_id` 执行。
3. **针对作者的操作（进主页搜视频）**：
   必须使用第一步拿到的 `sec_uid` 执行。提取到主页结果后可重回业务逻辑 2。

## ⛓️ 全局约束

- 所有核心动作前应预先检查登录状态（通过 `check-login`）。
- 点赞、评论和发布操作必须明确告知用户或获得允许后进行（视任务边界而定）。
- 所有返回数据均为标准 JSON（包含在 stdout 中）。
- **执行命令路径**：如果当前工作区处于项目根目录，必须使用 `douyin-skills/venv/Scripts/python.exe douyin-skills/scripts/cli.py`。

---

## 🛠 子技能概览

### dy-auth — 认证状态检查

| 命令 | 功能 |
|------|------|
| `cli.py check-login` | 检查当前环境是否已登录抖音客户端 |

### dy-explore — 搜索与发现内容

负责一切查询和列表捕获操作。

| 命令 | 功能 |
|------|------|
| `cli.py search-videos` | 模拟输入搜索核心词并捕获首屏视频。支持参数 `--keyword <词>` 和 `--scroll-times <下拉次数>` |
| `cli.py filter-videos` | 在搜索结果页应用时间/排序等过滤。支持多个（逗号分隔），如 `--type "最多点赞,半年内"` |
| `cli.py scroll-videos` | 在当前搜索结果页继续向下滚动。参数 `--scroll-times <次数>` |
| `cli.py get-video-detail` | 在搜索页面或者博主主页用于点击进入视频播放。参数 `--video-id <ID>` |
| `cli.py open-share-url` | 通过分享链接直接获取视频详情。参数 `--share-url <URL>` |--comments
| `cli.py get-comments` | 在播放页点击评论按钮。参数 `--video-id <ID>` (必填) |
| `cli.py share-video` | 在播放页点击分享按钮并捕获短链接。参数 `--video-id <ID>` (必填) |
| `cli.py scroll-comments` | 在当前已打开的评论面板继续下拉。参数 `--scroll-times <次数>` |
| `cli.py get-author-posts` | 进入博主主页获取视频列表。支持参数 `--sec-uid <UID>` 或 `--url <URL>` |


### dy-interact — 社交互动

提供拟人化的互动组件（要求在此前先用 `check-login` 检查登录）。

| 命令 | 功能 |
|------|------|
| `cli.py like-video` | 为指定视频点赞 (`--video-id <ID>`)   |
| `cli.py favorite-video` | 收藏指定视频 (`--video-id <ID>`) |
| `cli.py post-comment` | [未开放] 在指定视频下方发送评论 (`--video-id <ID> --content "评论"`) |

### dy-control — 页面显式操控

| 命令 | 功能 |
|------|------|
| `cli.py visit-author` | 强行导航至作者主页（仅跳转，不返回爬取数据） |
| `cli.py click-author` | 在搜索列表页点击进入第 N 个作者页（`--index <索引>`） |
| `cli.py close-video` | 关闭当前全屏的视频弹窗回到搜索页 |

---

## 🚀 快速开始 (Quick Start)

以下展示如何使用**虚拟环境**的 Python 调用工具链完成一次完整的自动化流程：

```bash
#先链接MCP
python douyin-skills/scripts/bridge_server.py
# 1. 检查是否成功登录
douyin-skills/venv/Scripts/python.exe douyin-skills/scripts/cli.py check-login

# 2. 搜索视频列表 (不下拉)
douyin-skills/venv/Scripts/python.exe douyin-skills/scripts/cli.py search-videos --keyword "猫咪" --scroll-times 0(可选，默认0)

# (假定此时你从上面的返回 JSON 中提取到了 video_id = "7408...", sec_uid = "MS4w...")

# 3. 点击进入视频播放（支持 ID 定位）
douyin-skills/venv/Scripts/python.exe douyin-skills/scripts/cli.py get-video-detail --video-id "7408..."

# 4. 获取该视频下的评论列表 (下拉 2 次获取更多)
douyin-skills/venv/Scripts/python.exe douyin-skills/scripts/cli.py get-comments --video-id "7408..." --scroll-times 2

# 5. 去该视频博主的主页看看其他视频
douyin-skills/venv/Scripts/python.exe douyin-skills/scripts/cli.py get-author-posts --sec-uid "MS4wLjABAAAACu7Vgr-qdAcU1i6niXcwJ2fssELOuPKE7qxBZHZEXF0"

# 6. 点赞视频
douyin-skills/venv/Scripts/python.exe douyin-skills/scripts/cli.py like-video --video-id "7408..."

# 7. 分享视频（获取短链接）
douyin-skills/venv/Scripts/python.exe douyin-skills/scripts/cli.py share-video --video-id "7620033325315183078"

# 7. 给视频发送真实的评论 [功能未开放]
douyin-skills/venv/Scripts/python.exe douyin-skills/scripts/cli.py post-comment --video-id "7408..." --content "这猫太可爱了吧！"

# 8. 通过分享链接直接提取详情
douyin-skills/venv/Scripts/python.exe douyin-skills/scripts/cli.py open-share-url --share-url "https://v.douyin.com/ienbn9HPKYA/" or --url "https://www.douyin.com/user/MS4wLjABAAAAOfcTkZsqfmakUkXxVswXGv8TtC15J8E4r7aOhoGkTy0lzETcKr5HQNGYwS8FgOgh?from_tab_name=main&vid=7609012469209500974"

# 9. 发布本地文件为新视频 [功能未开放]
douyin-skills/venv/Scripts/python.exe douyin-skills/scripts/cli.py publish-video --video-file "C:\\path\\video.mp4" --title "测试自动化"
```

## ⚠️ 失败处理

- **找不到元素或超时 (`null` 或空数组 `[]`)**：可能是网络延迟或验证码拦截，稍等后重试相同的命令即可。由于桥接脚本内部会处理等待逻辑，**重试前不需要你手动 sleep**。
- **未登录 (`error: NotLoggedInError`)**：提示用户在浏览器端手动处理一次登录，确保通过 `check-login` 的校验。
- **桥接服务器断开 (`ConnectionError / 未启动`)**：提示用户在另一个终端先启动 `scripts/bridge_server.py`，再行操作。
