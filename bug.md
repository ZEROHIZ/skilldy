# Bug Log: 缺失选择器变量

## 问题描述
在 `scripts/dy/urls.py` 中，虽然定义了搜索框和搜索按钮的选择器，但缺少评论区按钮（COMMENT_ICON）等关键交互元素的变量。

## 影响
虽然 `selectors.py` 中有定义，但 `urls.py` 作为主要的配置入口，变量不全会导致：
1. 配置分散，用户难以在统一位置修改所有常用的 CSS 选择器。
2. 代码一致性差（搜索在 `urls.py`，评论只在 `selectors.py`）。

## 修复步骤
1. 在 `urls.py` 中增加 `COMMENT_ICON_SELECTOR`, `LIKE_BUTTON_SELECTOR`, `COLLECT_BUTTON_SELECTOR`。
2. 修改 `selectors.py` 使其引用 `urls.py` 中的变量以免重复定义。

---

# Bug Log: API 拦截匹配失效（相对路径问题）

## 问题描述
在执行博主作品列表抓取时，`stealth.js` 的 Hook 捕获到了请求，但由于请求 URL 是相对路径（如 `post/`），而拦截规则检查的是 `url.includes("aweme/v1/")`，导致匹配失败，数据未能上报给 Python 端，最终触发超时。

## 影响
1. `get-author-posts` 命令由于等不到 API 响应而频繁超时。
2. 虽然 DevTools 网络面板能过滤出请求，但脚本逻辑层识别不到。

## 修复步骤
1. **URL 补全**：在 `stealth.js` 的 XHR 和 Fetch Hook 中，利用 `new URL(url, window.location.href).href` 将所有捕获到的原始 URL 转化为绝对路径。
2. **统一分发**：在 `dispatchCapturedData` 中同样执行一次强制补全，确保最终上报给 `background.js` 的 URL 是标准一致的。

# Bug Log: 抖音反检测（Robot Control）验证与下拉加载失效

## 问题描述
1. **反爬识别**：采用 `chrome.debugger` (Network.enable) 进行网络拦截会触发抖音机器人的严重防爬对抗（出现点选验证码）。
2. **滚动失效**：在搜索页执行 `window.scrollBy` 无法触发加载更多，原因是抖音现在大量采用深层的局部 CSS 容器（如 `.child-route-container.route-scroll-container`）来处理滚动。
3. **读取崩溃**：底层 JS Hook 在代理 `XMLHttpRequest` 时，如果直接读取 `this.responseText`，遇到 `responseType` 被配置为 `json` 或 `arraybuffer` 的请求时会直接报错，导致监听中断。
4. **注入时差**：`content.js` 若设在 `document_idle` 时刻注入，打开新页面时会由于时机太晚，漏掉最开始的初始 API 拦截消息。

## 修复步骤
1. **去调试器化**：废弃依赖 `chrome.debugger`，改为在 `stealth.js` (`document_start` 环境) 中重写 `fetch` 与 `XMLHttpRequest` 进行静默抓包。
2. **重定向滚动**：将下拉滚动的动作目标精准投给 `document.querySelector('.child-route-container.route-scroll-container')` 或同类替代容器，同时用随机步长平滑缓动。
3. **完善类型兼容**：在 `stealth.js` 中加入了对 `this.responseType` 的判断逻辑，以对应不同的方式（如 `JSON.stringify` 或 `TextDecoder`）安全读取。
4. **统一注入时机**：修改 `manifest.json` 将 `content.js` 的装载时机提前到 `document_start` 以完美承接所有的 `window.postMessage`。

---

# Bug Log: XHR 监听在特定页面失效 (博主主页 Hook 绕过)

## 问题描述
在博主个人主页等复杂业务场景下，原有的 `XMLHttpRequest.prototype.send` 原型链拦截方案失效。表现为：控制台能监测到 `send` 被调用，但 `load` 或 `readystatechange` 回调永远不触发，导致数据抓取不到；而 F12 网络面板显示请求是成功的。

## 影响
由于网页侧可能使用了特殊的 XHR 封装或重写了实例属性，导致常规的 `addEventListener` 被绕过，使得 `get-author-posts` 等命令持续超时。

## 修复步骤
1. **架构升级 (Mirror Proxy)**：不再仅仅 Hook 原型方法，而是直接重写全局的 `window.XMLHttpRequest` 构造函数。
2. **实例代理**：在自定义构造函数内部实例化原始 XHR，并对其 `open`、`send` 以及 `onreadystatechange` 属性进行强制代理。
3. **闭包捕获**：这种“镜像”方式确保了无论网页脚本如何修改实例属性，始终会经过我们的代理逻辑。

---

# Bug Log: 搜索 API 分块响应处理不当

## 问题描述
抖音搜索 API 返回数据时采用分块传输，一个 URL 响应中包含多个独立的 JSON 对象。早期分块可能包含缓存或过时数据。响应流中会出现 `{"ack":-1}` 作为有效数据的起始标记（通常是第 2 个对象）。

## 影响
如果不进行过滤，合并所有分块会导致获取到重复或不稳定的搜索结果。

## 修复步骤
1. **分块过滤**：在 `background.js` 的 `mergeJsonResults` 中增加 `ack` 检测逻辑。
2. **排除首部**：一旦发现 `{"ack":-1}`，排除其及之前的所有字典块，仅处理后续的业务数据块。
