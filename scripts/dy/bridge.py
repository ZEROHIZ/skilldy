"""BridgePage - 通过浏览器扩展 Bridge 实现与 CDP Page 相同的接口。

CLI 命令通过 WebSocket 发送到 bridge_server.py，
bridge_server 转发给浏览器扩展执行，结果原路返回。
"""

from __future__ import annotations

import base64
import json
import logging
import os
from typing import Any

import websockets.sync.client as ws_client

from .errors import CDPError, ElementNotFoundError

BRIDGE_URL = "ws://127.0.0.1:9334"

logger = logging.getLogger(__name__)

class BridgePage:
    """与 CDP Page 接口兼容的 Extension Bridge 实现。"""

    def __init__(self, bridge_url: str = BRIDGE_URL) -> None:
        self._bridge_url = bridge_url

    # ─── 内部通信 ───────────────────────────────────────────────

    def _call(self, method: str, params: dict | None = None) -> Any:
        msg: dict[str, Any] = {"role": "cli", "method": method}
        if params:
            msg["params"] = params
        try:
            with ws_client.connect(self._bridge_url, max_size=50 * 1024 * 1024) as ws:
                ws.send(json.dumps(msg, ensure_ascii=False))
                raw = ws.recv(timeout=90)
        except OSError as e:
            raise CDPError(f"无法连接到 bridge server（ws://127.0.0.1:9334）: {e}") from e

        resp = json.loads(raw)
        if "error" in resp and resp["error"]:
            raise CDPError(f"Bridge 错误: {resp['error']}")
        return resp.get("result")

    # ─── 导航 ───────────────────────────────────────────────────

    def navigate(self, url: str, new_tab: bool = False) -> None:
        self._call("navigate", {"url": url, "newTab": new_tab})

    def get_url(self) -> str:
        """获取当前页面 URL。"""
        return str(self._call("get_url") or "")

    def wait_for_load(self, timeout: float = 60.0) -> None:
        self._call("wait_for_load", {"timeout": int(timeout * 1000)})

    def wait_dom_stable(self, timeout: float = 10.0, interval: float = 0.5) -> None:
        self._call("wait_dom_stable", {
            "timeout": int(timeout * 1000),
            "interval": int(interval * 1000),
        })

    # ─── JavaScript 执行 ────────────────────────────────────────

    def evaluate(self, expression: str, timeout: float = 30.0) -> Any:
        return self._call("evaluate", {"expression": expression})

    def evaluate_function(self, function_body: str, *args: Any) -> Any:
        return self._call("evaluate", {"expression": f"({function_body})()"})

    # ─── 元素查询 ────────────────────────────────────────────────

    def query_selector(self, selector: str) -> str | None:
        found = self._call("has_element", {"selector": selector})
        return "found" if found else None

    def query_selector_all(self, selector: str) -> list[str]:
        count = self.get_elements_count(selector)
        return ["found"] * count

    def has_element(self, selector: str) -> bool:
        return bool(self._call("has_element", {"selector": selector}))

    def wait_for_element(self, selector: str, timeout: float = 30.0) -> str:
        found = self._call("wait_for_selector", {
            "selector": selector,
            "timeout": int(timeout * 1000),
        })
        if not found:
            raise ElementNotFoundError(selector)
        return "found"

    # ─── 元素操作 ────────────────────────────────────────────────

    def click_element(self, selector: str) -> None:
        self._call("click_element", {"selector": selector})

    def click_at(self, selector: str, svg_path_data: str | None = None) -> dict[str, int] | None:
        """在目标元素中心模拟坐标点击。"""
        params = {"selector": selector}
        if svg_path_data:
            params["svgPathData"] = svg_path_data
        return self._call("click_at", params)

    def input_text(self, selector: str, text: str) -> None:
        self._call("input_text", {"selector": selector, "text": text})

    def input_content_editable(self, selector: str, text: str) -> None:
        self._call("input_content_editable", {"selector": selector, "text": text})

    def get_element_text(self, selector: str) -> str | None:
        return self._call("get_element_text", {"selector": selector})

    def get_element_attribute(self, selector: str, attr: str) -> str | None:
        return self._call("get_element_attribute", {"selector": selector, "attr": attr})

    def get_elements_count(self, selector: str) -> int:
        result = self._call("get_elements_count", {"selector": selector})
        return int(result) if result is not None else 0

    def remove_element(self, selector: str) -> None:
        self._call("remove_element", {"selector": selector})

    def hover_element(self, selector: str) -> None:
        self._call("hover_element", {"selector": selector})

    def select_all_text(self, selector: str) -> None:
        self._call("select_all_text", {"selector": selector})

    # ─── 滚动 ────────────────────────────────────────────────────

    def scroll_by(self, x: int, y: int) -> None:
        self._call("scroll_by", {"x": x, "y": y})

    def scroll_to(self, x: int, y: int) -> None:
        self._call("scroll_to", {"x": x, "y": y})

    def scroll_to_bottom(self) -> None:
        self._call("scroll_to_bottom")

    def scroll_element_into_view(self, selector: str) -> None:
        self._call("scroll_element_into_view", {"selector": selector})

    def scroll_nth_element_into_view(self, selector: str, index: int) -> None:
        self._call("scroll_nth_element_into_view", {"selector": selector, "index": index})

    def get_scroll_top(self) -> int:
        result = self._call("get_scroll_top")
        return int(result) if result is not None else 0

    def get_viewport_height(self) -> int:
        result = self._call("get_viewport_height")
        return int(result) if result is not None else 768

    # ─── 输入事件 ────────────────────────────────────────────────

    def press_key(self, key: str) -> None:
        self._call("press_key", {"key": key})

    def type_text(self, text: str, delay_ms: int = 50) -> None:
        self._call("type_text", {"text": text, "delayMs": delay_ms})

    def mouse_move(self, x: float, y: float) -> None:
        self._call("mouse_move", {"x": x, "y": y})

    def mouse_click(self, x: float, y: float, button: str = "left") -> None:
        self._call("mouse_click", {"x": x, "y": y, "button": button})

    def dispatch_wheel_event(self, delta_y: float) -> None:
        self._call("dispatch_wheel_event", {"deltaY": delta_y})

    # ─── 文件上传 ────────────────────────────────────────────────

    def set_file_input(self, selector: str, files: list[str]) -> None:
        abs_paths = [os.path.abspath(path) for path in files]
        self._call("set_file_input", {"selector": selector, "files": abs_paths})

    # ─── API 被动监听 ────────────────────────────────────────────

    def listen_api(
        self,
        url_pattern: str,
        navigate_url: str | None = None,
        click_selector: str | None = None,
        trigger_expression: str | None = None,
        timeout: float = 30.0,
        new_tab: bool = False,
    ) -> dict | None:
        """被动监听匹配 urlPattern 的 API 响应，返回 JSON 数据。

        Args:
            url_pattern: API URL 中需要匹配的关键字段
            navigate_url: 可选，导航到此 URL 以触发 API 请求
            click_selector: 可选，点击此选择器以触发 API 请求
            trigger_expression: 可选，在监听器就绪后执行的 JS 表达式（用于输入文字+按回车等复合触发）
            timeout: 超时时间（秒）
        """
        params: dict = {
            "urlPattern": url_pattern,
            "timeout": int(timeout * 1000),
        }
        if navigate_url:
            params["navigateUrl"] = navigate_url
        if click_selector:
            params["clickSelector"] = click_selector
        if trigger_expression:
            params["triggerExpression"] = trigger_expression
        if new_tab:
            params["newTab"] = True
        res = self._call("listen_api", params)
        if isinstance(res, dict) and res.get("__hook_timeout__"):
            logger.warning("======== [DEBUG] API 监听超时，未抓取到指定模式: %s ========", url_pattern)
            seen = res.get("seen_urls", [])
            if seen:
                logger.info("在此期间，浏览器共捕获到以下 %d 条请求 (可对照查看是否 URL 发生了变动):", len(seen))
                for item in seen:
                    logger.info("  [时差 %dms] %s", item.get('timeOffset', 0), item.get('url'))
            else:
                logger.warning("在此期间，浏览器未通过 Hook 捕获到任何符合条件的请求，请确认扩展是否正常工作（stealth.js 是否载入）。")
            return None
        return res

    def listen_apis(
        self,
        url_patterns: list[str],
        navigate_url: str | None = None,
        click_selector: str | None = None,
        trigger_expression: str | None = None,
        timeout: float = 30.0,
        new_tab: bool = False,
    ) -> dict[str, dict | None]:
        """被动同时监听匹配 url_patterns 列表的多个 API 响应，返回每个 pattern 对应的 JSON 数据。

        Args:
            url_patterns: API URL 中需要匹配的关键字段列表
            navigate_url: 可选，导航到此 URL 以触发 API 请求
            click_selector: 可选，点击此选择器以触发 API 请求
            trigger_expression: 可选，在监听器就绪后执行的 JS 表达式
            timeout: 超时时间（秒）
        """
        params: dict = {
            "urlPatterns": url_patterns,
            "timeout": int(timeout * 1000),
        }
        if navigate_url:
            params["navigateUrl"] = navigate_url
        if click_selector:
            params["clickSelector"] = click_selector
        if trigger_expression:
            params["triggerExpression"] = trigger_expression
        if new_tab:
            params["newTab"] = True
        
        result = self._call("listen_api", params)
        if isinstance(result, dict) and result.get("__hook_timeout__"):
            logger.warning("======== [DEBUG] 组合 API 监听超时，未抓取到指定模式: %s ========", url_patterns)
            seen = result.get("seen_urls", [])
            for item in seen:
                logger.info("  [时差 %dms] %s", item.get('timeOffset', 0), item.get('url'))
            return {p: None for p in url_patterns}
            
        # 如果超时等原因返回了 None，或者部分缺失，我们整理成一个完整的 dict 提供给上层
        if result is None:
            return {p: None for p in url_patterns}
        return {p: result.get(p) for p in url_patterns}

    # ─── 截图 ────────────────────────────────────────────────────

    def screenshot_element(self, selector: str, padding: int = 0) -> bytes:
        result = self._call("screenshot_element", {"selector": selector, "padding": padding})
        if result and result.get("data"):
            return base64.b64decode(result["data"])
        return b""

    # ─── 兼容性辅助方法 ──────────────────────────────────────────

    def is_server_running(self) -> bool:
        try:
            with ws_client.connect(self._bridge_url, open_timeout=3) as ws:
                ws.send(json.dumps({"role": "cli", "method": "ping_server"}))
                raw = ws.recv(timeout=5)
            resp = json.loads(raw)
            return "result" in resp
        except Exception:
            return False

    def is_extension_connected(self) -> bool:
        try:
            with ws_client.connect(self._bridge_url, open_timeout=3) as ws:
                ws.send(json.dumps({"role": "cli", "method": "ping_server"}))
                raw = ws.recv(timeout=5)
            resp = json.loads(raw)
            return bool(resp.get("result", {}).get("extension_connected"))
        except Exception:
            return False

    @property
    def target_id(self) -> str:
        return "extension-bridge"
