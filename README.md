# Douyin Skills (dyskill)

抖音自动化助手，提供基于 Chrome 扩展和 Bridge Server 的自动化操作能力。

## 🌟 功能

- [x] 登录状态检查
- [x] 视频搜索与分类筛选
- [x] 视频详情获取（点赞数、评论数等）
- [x] 评论列表获取
- [x] 作者主页视频列表获取
- [x] 自动点赞与收藏
- [ ] 自动发评论（暂未开放）
- [ ] 自动发布视频（暂未开放）
- [ ] 推荐流获取（暂未开放）

## 🛠️ 安装步骤

### 1. 克隆仓库
```bash
git clone https://github.com/ZEROHIZ/dyskill.git
cd dyskill
```

### 2. 创建虚拟环境并安装依赖
```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境 (Windows)
.\venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

### 3. 配置浏览器扩展
1. 打开 Chrome 浏览器，进入 `chrome://extensions/`。
2. 开启右上角的“开发者模式”。
3. 点击“加载已解压的扩展程序”，选择项目中的 `extension` 目录。
4. 确保在抖音网页版已登录你的账号。

## 🚀 快速开始

### 1. 启动 Bridge Server
在第一个终端运行：
```bash
python scripts/bridge_server.py
```

### 2. 使用 CLI 工具
在第二个终端（记得并激活虚拟环境）运行：
```bash
# 检查登录状态
python scripts/cli.py check-login

# 搜索视频
python scripts/cli.py search-videos --keyword "猫咪"

# 获取指定视频评论
python scripts/cli.py get-comments --video-id "7408..."
```

## ⚠️ 注意事项
- 本工具依赖于已运行的 Chrome 浏览器及安装好的扩展程序。
- 部分写操作（点赞/评论等）建议先通过 `check-login` 确认后再执行。
- 严禁用于任何违法违规用途。
