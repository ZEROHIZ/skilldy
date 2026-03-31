/**
 * DY Bridge - Background Service Worker
 *
 * 连接 Python bridge server（ws://localhost:9334），接收命令并执行：
 * - navigate / wait_for_load: chrome.tabs.update + onUpdated
 * - evaluate / has_element 等: chrome.scripting.executeScript (MAIN world)
 * - click / input 等 DOM 操作: chrome.tabs.sendMessage → content.js
 * - screenshot: chrome.tabs.captureVisibleTab
 * - get_cookies: chrome.cookies.getAll
 */

const BRIDGE_URL = "ws://localhost:9334";
let ws = null;

// 日志工具：输出调用位置方便调试，现在改为不打日志或极简日志
function log(location, ...args) {
  // console.log(`[DY Bridge][${new Date().toLocaleTimeString()}][${location}]`, ...args);
}

// 保持 service worker 存活
chrome.alarms.create("keepAlive", { periodInMinutes: 0.4 });
chrome.alarms.onAlarm.addListener(() => {
  if (!ws || ws.readyState !== WebSocket.OPEN) connect();
});

// 全局存储从 content.js 接收到的 API 拦截数据
// key: url -> value: { timestamp, data }
const capturedApiData = [];

// 监听 content.js 转发来的拦截数据
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "FORWARD_DY_API_CAPTURED") {
    console.log("[DY Background] 收到捕获数据:", msg.url);
    capturedApiData.push({
      url: msg.url,
      data: msg.data,
      timestamp: Date.now()
    });
    // 只保留最近的 50 条记录防止内存泄漏
    if (capturedApiData.length > 50) capturedApiData.shift();
  }
});

// ───────────────────────── WebSocket ─────────────────────────

function connect() {
  if (ws && (ws.readyState === WebSocket.CONNECTING || ws.readyState === WebSocket.OPEN)) return;

  ws = new WebSocket(BRIDGE_URL);

  ws.onopen = () => {
    console.log("[DY Bridge] 已连接到 bridge server");
    ws.send(JSON.stringify({ role: "extension" }));
  };

  ws.onmessage = async (event) => {
    let msg;
    try {
      msg = JSON.parse(event.data);
    } catch {
      return;
    }
    try {
      const result = await handleCommand(msg);
      ws.send(JSON.stringify({ id: msg.id, result: result ?? null }));
    } catch (err) {
      ws.send(JSON.stringify({ id: msg.id, error: String(err.message || err) }));
    }
  };

  ws.onclose = () => {
    console.log("[DY Bridge] 连接断开，3s 后重连...");
    setTimeout(connect, 3000);
  };

  ws.onerror = (e) => {
    console.error("[DY Bridge] WS 错误", e);
  };
}

// ───────────────────────── 命令路由 ─────────────────────────

async function handleCommand(msg) {
  const { method, params = {} } = msg;
  log("handleCommand", "收到命令:", method);

  switch (method) {
    // ── 导航 ──
    case "navigate":
      return await cmdNavigate(params);

    case "wait_for_load":
      return await cmdWaitForLoad(params);

    // ── 截图 ──
    case "screenshot_element":
      return await cmdScreenshot(params);

    case "set_file_input":
      return await cmdSetFileInputViaDebugger(params);

    case "click_at":
      return await cmdClickAtCoordinates(params);

    // ── Cookies ──
    case "get_cookies":
      return await cmdGetCookies(params);

    // ── API 被动监听 ──
    case "listen_api":
      return await cmdListenAPI(params);

    // ── 在页面主 world 执行 JS ──
    case "evaluate":
    case "wait_dom_stable":
    case "wait_for_selector":
    case "has_element":
    case "get_elements_count":
    case "get_element_text":
    case "get_element_attribute":
    case "get_scroll_top":
    case "get_viewport_height":
    case "get_url":
      return await cmdEvaluateInMainWorld(method, params);

    // ── DOM 操作 ──
    default:
      return await cmdDomInMainWorld(method, params);
  }
}

// ───────────────────────── 导航 ─────────────────────────

async function cmdNavigate({ url, newTab = false }) {
  let tab;
  if (newTab) {
    tab = await chrome.tabs.create({ url, active: true });
    await chrome.windows.update(tab.windowId, { focused: true });
  } else {
    tab = await getOrOpenDYTab();
    // 如果 URL 已一致，只需确保激活即可，无需重新导航
    if (tab.url === url) {
      await chrome.tabs.update(tab.id, { active: true });
      await chrome.windows.update(tab.windowId, { focused: true });
      return null;
    }
    await chrome.tabs.update(tab.id, { url, active: true });
    await chrome.windows.update(tab.windowId, { focused: true });
  }

  await waitForTabComplete(tab.id, url, 60000);
  return null;
}

async function cmdWaitForLoad({ timeout = 60000 }) {
  const tab = await getOrOpenDYTab();
  await waitForTabComplete(tab.id, null, timeout);
  return null;
}

async function waitForTabComplete(tabId, expectedUrlPrefix, timeout) {
  return new Promise((resolve, reject) => {
    const deadline = Date.now() + timeout;

    function listener(id, info, updatedTab) {
      if (id !== tabId) return;
      if (info.status !== "complete") return;
      if (expectedUrlPrefix && !updatedTab.url?.startsWith(expectedUrlPrefix.slice(0, 20))) return;
      chrome.tabs.onUpdated.removeListener(listener);
      resolve();
    }

    chrome.tabs.onUpdated.addListener(listener);

    const poll = async () => {
      if (Date.now() > deadline) {
        chrome.tabs.onUpdated.removeListener(listener);
        reject(new Error("页面加载超时"));
        return;
      }
      const tab = await chrome.tabs.get(tabId).catch(() => null);
      if (tab && tab.status === "complete") {
        chrome.tabs.onUpdated.removeListener(listener);
        resolve();
        return;
      }
      setTimeout(poll, 400);
    };
    setTimeout(poll, 600);
  });
}

// ───────────────────────── 截图 ─────────────────────────

async function cmdScreenshot() {
  const tab = await getOrOpenDYTab();
  const dataUrl = await chrome.tabs.captureVisibleTab(tab.windowId, { format: "png" });
  return { data: dataUrl.split(",")[1] };
}

// ───────────────────────── Cookies ─────────────────────────

async function cmdGetCookies({ domain = "douyin.com" }) {
  return await chrome.cookies.getAll({ domain });
}

// ───────────────────────── API 拦截监听 (非 Debugger 机制) ───────

async function cmdListenAPI({ urlPattern, urlPatterns, timeout = 30000, navigateUrl, clickSelector, triggerExpression, newTab = false }) {
  let tab;
  
  // 记录监听开始的时间，并允许一点点“回视”缓冲区（防止导航开始得比 startTime 稍早）
  const startTime = Date.now();
  const lookbackTime = startTime - 5000; // 5秒缓冲区

  if (newTab && navigateUrl) {
    // 将创建标签页和启动监听几乎同步进行
    tab = await chrome.tabs.create({ url: navigateUrl, active: true });
    await chrome.windows.update(tab.windowId, { focused: true });
  } else {
    tab = await getOrOpenDYTab();
  }

  const patternsToMatch = urlPatterns ? [...urlPatterns] : (urlPattern ? [urlPattern] : []);
  if (patternsToMatch.length === 0) {
    throw new Error("cmdListenAPI 必须提供 urlPattern 或 urlPatterns");
  }

  const pendingPatterns = new Set(patternsToMatch);
  const gatheredResults = {};

  return new Promise((resolve) => {
    // 定时检查 capturedApiData 
    const checkInterval = setInterval(() => {
        // 遍历所有未匹配的 pattern
        for (const pattern of Array.from(pendingPatterns)) {
          // 找发生在开始监听时间之前一点点（lookbackTime）之后，且 url 包含 pattern 的记录
          const matchIdx = capturedApiData.findIndex(item => item.timestamp >= lookbackTime && item.url.includes(pattern));
          
          if (matchIdx !== -1) {
             const match = capturedApiData[matchIdx];
             const cleanData = cleanJson(match.data);
             gatheredResults[pattern] = cleanData;
             pendingPatterns.delete(pattern);
          }
        }

        if (pendingPatterns.size === 0) {
            cleanup();
            resolve(urlPatterns ? gatheredResults : (gatheredResults[urlPattern] || null));
        }
    }, 200);

    const timer = setTimeout(() => {
      cleanup();
      
      const allSeen = capturedApiData
        .filter(item => item.timestamp >= startTime)
        .map(item => ({ url: item.url, timeOffset: item.timestamp - startTime }));

      // 如果发生了超时，且没有任何匹配，则返回调试信息包
      if (pendingPatterns.size === patternsToMatch.length) {
         resolve({
             "__hook_timeout__": true,
             "__hook_debug__": true,
             "seen_urls": allSeen,
             "patterns": patternsToMatch
         });
      } else {
         resolve(urlPatterns ? gatheredResults : (gatheredResults[urlPattern] || null));
      }
    }, timeout);

    function cleanup() {
      clearInterval(checkInterval);
      clearTimeout(timer);
    }

    // 触发动作
    if (navigateUrl && !newTab) {
      chrome.tabs.update(tab.id, { url: navigateUrl, active: true });
    }
    if (clickSelector) {
      setTimeout(() => {
        chrome.scripting.executeScript({
          target: { tabId: tab.id },
          world: "MAIN",
          func: (sel) => {
            const el = document.querySelector(sel);
            if (el) { el.scrollIntoView({ block: "center" }); el.click(); }
          },
          args: [clickSelector],
        }).catch(() => {});
      }, 300);
    }
    if (triggerExpression) {
      setTimeout(() => {
        chrome.scripting.executeScript({
          target: { tabId: tab.id },
          world: "MAIN",
          func: (expr) => {
            return Function(`"use strict"; return (${expr})`)();
          },
          args: [triggerExpression],
        }).catch(() => {});
      }, 300);
    }

    function cleanup() {
      clearTimeout(timer);
      clearInterval(checkInterval);
    }
  });
}

/**
 * 尝试清洗并解析 JSON，处理分块传输带来的干扰字符
 * 如: 12355{"status_code":0...}0
 */
function cleanJson(text) {
  if (!text || typeof text !== "string") return text;
  
  const trimmed = text.trim();
  if (!trimmed) return null;

  // 1. 尝试直接解析（标准情况）
  try {
    return JSON.parse(trimmed);
  } catch (e) {
    // 2. 处理分块传输或拼接的 JSON (Concatenated JSON)
    // 使用“平衡括号”算法提取所有顶级 JSON 对象
    log("cleanJson", "检测到非标拼接格式，尝试括号计数提取...");
    const results = [];
    let i = 0;
    while (i < trimmed.length) {
      if (trimmed[i] === '{' || trimmed[i] === '[') {
        const startChar = trimmed[i];
        const endChar = (startChar === '{') ? '}' : ']';
        let depth = 0;
        let startIdx = i;
        let found = false;

        // 寻找匹配的闭括号
        for (let j = i; j < trimmed.length; j++) {
          if (trimmed[j] === startChar) depth++;
          else if (trimmed[j] === endChar) {
            depth--;
            if (depth === 0) {
              const jsonStr = trimmed.substring(startIdx, j + 1);
              try {
                results.push(JSON.parse(jsonStr));
                found = true;
              } catch (parseErr) {
                // 如果片段内括号不匹配导致解析失败，忽略
              }
              i = j;
              break;
            }
          }
        }
        if (!found) i++; // 没找到则继续找下一个起始符
      } else {
        i++;
      }
    }

    if (results.length > 0) {
      log("cleanJson", `提取到 ${results.length} 个顶级 JSON 对象`);
      return mergeJsonResults(results);
    }
    
    return text;
  }

  // 合并多个块中的业务数据
  function mergeJsonResults(objects) {
    let base = null;
    let allData = [];
    let listKey = "";

    for (const obj of objects) {
      // 识别列表键名：data (搜索), aweme_list (视频列表), comments (评论列表)
      const currentKey = obj.data ? "data" : (obj.aweme_list ? "aweme_list" : (obj.comments ? "comments" : ""));
      
      if (currentKey) {
        if (!base) {
            base = obj;
            listKey = currentKey;
        }
        const items = obj[currentKey];
        if (Array.isArray(items)) allData = allData.concat(items);
      } else if (!base && obj.status_code === 0) {
        base = obj;
      }
    }

    if (base && listKey) {
      base[listKey] = allData;
      return base;
    }
    return objects[0]; // 实在没匹配到业务字段，返回第一个对象
  }
}

// ───────────────────────── MAIN world JS 执行 ─────────────────────────

async function cmdEvaluateInMainWorld(method, params) {
  const tab = await getOrOpenDYTab();
  const results = await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    world: "MAIN",
    func: mainWorldExecutor,
    args: [method, params],
  });
  const r = results?.[0]?.result;
  if (r && typeof r === "object" && "__dy_error" in r) {
    throw new Error(r.__dy_error);
  }
  return r;
}

function mainWorldExecutor(method, params) {
  function poll(check, interval, timeout) {
    return new Promise((resolve, reject) => {
      const start = Date.now();
      (function tick() {
        const result = check();
        if (result !== false && result !== null && result !== undefined) {
          resolve(result);
          return;
        }
        if (Date.now() - start >= timeout) {
          reject(new Error("超时"));
          return;
        }
        setTimeout(tick, interval);
      })();
    });
  }

  switch (method) {
    case "evaluate": {
      try {
        return Function(`"use strict"; return (${params.expression})`)();
      } catch (e) {
        return { __dy_error: `JS执行错误: ${e.message}` };
      }
    }

    case "has_element":
      return document.querySelector(params.selector) !== null;

    case "get_elements_count":
      return document.querySelectorAll(params.selector).length;

    case "get_element_text": {
      const el = document.querySelector(params.selector);
      return el ? el.textContent : null;
    }

    case "get_element_attribute": {
      const el = document.querySelector(params.selector);
      return el ? el.getAttribute(params.attr) : null;
    }

    case "get_scroll_top":
      return window.pageYOffset || document.documentElement.scrollTop || 0;

    case "get_viewport_height":
      return window.innerHeight;

    case "get_url":
      return window.location.href;

    case "wait_dom_stable": {
      const timeout = params.timeout || 10000;
      const interval = params.interval || 500;
      return new Promise((resolve) => {
        let last = -1;
        const start = Date.now();
        (function tick() {
          const size = document.body ? document.body.innerHTML.length : 0;
          if (size === last && size > 0) { resolve(null); return; }
          last = size;
          if (Date.now() - start >= timeout) { resolve(null); return; }
          setTimeout(tick, interval);
        })();
      });
    }

    case "wait_for_selector": {
      const timeout = params.timeout || 30000;
      return poll(
        () => document.querySelector(params.selector) ? true : false,
        200,
        timeout,
      ).catch(() => { throw new Error(`等待元素超时: ${params.selector}`); });
    }

    case "get_element_coords": {
      let el = document.querySelector(params.selector);
      if (params.svgPathData && el) {
        const paths = el.querySelectorAll('path');
        let found = false;
        for (const p of paths) {
          if (p.getAttribute('d') === params.svgPathData) {
            el = p.closest('svg') || p;
            found = true;
            break;
          }
        }
        if (!found) return null;
      }
      if (el) {
        const rect = el.getBoundingClientRect();
        return {
          x: Math.round(rect.left + rect.width / 2),
          y: Math.round(rect.top + rect.height / 2)
        };
      }
      return null;
    }

    default:
      return { __dy_error: `未知 MAIN world 方法: ${method}` };
  }
}

// ───────────────────────── 文件上传（chrome.debugger + CDP） ─────────

async function cmdSetFileInputViaDebugger({ selector, files }) {
  // 注意：在无调试方案下，上传视频仍需利用 Debugger 绕开 input[type="file"] 限制。
  // 但是这是上传才会触发，普通浏览不会检测。
  const tab = await getOrOpenDYTab();
  const target = { tabId: tab.id };

  await chrome.debugger.attach(target, "1.3");
  try {
    const { root } = await chrome.debugger.sendCommand(target, "DOM.getDocument", { depth: 0 });
    const { nodeId } = await chrome.debugger.sendCommand(target, "DOM.querySelector", {
      nodeId: root.nodeId,
      selector,
    });
    if (!nodeId) throw new Error(`文件输入框不存在: ${selector}`);
    await chrome.debugger.sendCommand(target, "DOM.setFileInputFiles", {
      nodeId,
      files,
    });
  } finally {
    await chrome.debugger.detach(target).catch(() => { });
  }
  return null;
}

// ───────────────────────── DOM 操作（MAIN world） ────────────────────

async function cmdDomInMainWorld(method, params) {
  const tab = await getOrOpenDYTab();
  const results = await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    world: "MAIN",
    func: domExecutor,
    args: [method, params],
  });
  const r = results?.[0]?.result;
  if (r && typeof r === "object" && "__dy_error" in r) {
    throw new Error(r.__dy_error);
  }
  return r ?? null;
}

async function cmdClickAtCoordinates(params) {
  // 注意：此方法用于坐标点击，原本也依赖 Debugger。
  // 我们暂时保留，因为上传文件和发布可能需要，但通过搜索和互动不调用即可。
  const tab = await getOrOpenDYTab();
  const target = { tabId: tab.id };
  
  // 1. 获取坐标
  const coords = await cmdEvaluateInMainWorld("get_element_coords", params);
  if (!coords) throw new Error("无法定位目标元素坐标");
  
  const { x, y } = coords;

  // 2. 使用 Debugger 模拟点击
  try {
    await chrome.debugger.attach(target, "1.3").catch(() => {});
    
    // 模拟移动鼠标到目标位置
    await chrome.debugger.sendCommand(target, "Input.dispatchMouseEvent", {
      type: "mouseMoved",
      x, y
    });
    
    // 稍作停顿，模拟人类反应
    await new Promise(r => setTimeout(r, 100));

    // 模拟鼠标左键按下和释放
    await chrome.debugger.sendCommand(target, "Input.dispatchMouseEvent", {
      type: "mousePressed",
      x, y,
      button: "left",
      clickCount: 1
    });
    await chrome.debugger.sendCommand(target, "Input.dispatchMouseEvent", {
      type: "mouseReleased",
      x, y,
      button: "left",
      clickCount: 1
    });
  } finally {
    // 延迟一会再关闭，给浏览器处理时间
    setTimeout(() => {
      chrome.debugger.detach(target).catch(() => {});
    }, 200);
  }
  return { x, y };
}

function domExecutor(method, params) {
  function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

  function requireEl(selector) {
    const el = document.querySelector(selector);
    if (!el) return { __dy_error: `元素不存在: ${selector}` };
    return el;
  }

  switch (method) {
    case "click_element": {
      const el = requireEl(params.selector);
      if (el.__dy_error) return el;
      el.scrollIntoView({ block: "center" });
      el.focus();
      el.click();
      return null;
    }

    case "input_text": {
      const el = requireEl(params.selector);
      if (el.__dy_error) return el;
      el.focus();
      el.value = params.text;
      el.dispatchEvent(new Event("input", { bubbles: true }));
      el.dispatchEvent(new Event("change", { bubbles: true }));
      return null;
    }

    case "input_content_editable": {
      return new Promise(async (resolve) => {
        const el = document.querySelector(params.selector);
        if (!el) { resolve({ __dy_error: `元素不存在: ${params.selector}` }); return; }
        el.focus();
        document.execCommand("selectAll", false, null);
        document.execCommand("delete", false, null);
        await sleep(80);
        const lines = params.text.split("\n");
        for (let i = 0; i < lines.length; i++) {
          if (lines[i]) document.execCommand("insertText", false, lines[i]);
          if (i < lines.length - 1) {
            document.execCommand("insertParagraph", false, null);
            await sleep(30);
          }
        }
        resolve(null);
      });
    }

    case "scroll_by":
      window.scrollBy(params.x || 0, params.y || 0); return null;
    case "scroll_to":
      window.scrollTo(params.x || 0, params.y || 0); return null;
    case "scroll_to_bottom":
      window.scrollTo(0, document.body.scrollHeight); return null;

    case "scroll_element_into_view": {
      const el = document.querySelector(params.selector);
      if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
      return null;
    }
    case "scroll_nth_element_into_view": {
      const els = document.querySelectorAll(params.selector);
      if (els[params.index]) els[params.index].scrollIntoView({ behavior: "smooth", block: "center" });
      return null;
    }

    case "dispatch_wheel_event": {
      const target = document.querySelector(".xgplayer-playing") || document.documentElement;
      target.dispatchEvent(new WheelEvent("wheel", { deltaY: params.deltaY || 0, deltaMode: 0, bubbles: true, cancelable: true }));
      return null;
    }

    case "mouse_move":
      document.dispatchEvent(new MouseEvent("mousemove", { clientX: params.x, clientY: params.y, bubbles: true }));
      return null;

    case "mouse_click": {
      const el = document.elementFromPoint(params.x, params.y);
      if (el) {
        ["mousedown", "mouseup", "click"].forEach(t =>
          el.dispatchEvent(new MouseEvent(t, { clientX: params.x, clientY: params.y, bubbles: true }))
        );
      }
      return null;
    }

    case "press_key": {
      const active = document.activeElement || document.body;
      const inCE = active.isContentEditable;
      const keyStr = params.key || "";

      // 解析组合键，如 "Control+a" → modifiers: {ctrlKey:true}, mainKey: "a"
      const parts = keyStr.split("+");
      const mainKey = parts.pop();
      const mods = { ctrlKey: false, shiftKey: false, altKey: false, metaKey: false };
      for (const p of parts) {
        if (p === "Control" || p === "Ctrl") mods.ctrlKey = true;
        if (p === "Shift") mods.shiftKey = true;
        if (p === "Alt") mods.altKey = true;
        if (p === "Meta" || p === "Command") mods.metaKey = true;
      }

      // Control+a 全选
      if (mods.ctrlKey && mainKey.toLowerCase() === "a") {
        if (active.select) { active.select(); }
        else { document.execCommand("selectAll", false, null); }
        return null;
      }

      if (inCE && mainKey === "Enter") {
        document.execCommand("insertParagraph", false, null);
        return null;
      }
      if (inCE && mainKey === "ArrowDown") {
        const sel = window.getSelection();
        if (sel && active.childNodes.length) {
          sel.selectAllChildren(active);
          sel.collapseToEnd();
        }
        return null;
      }

      // Backspace 对 input/textarea 的实际处理
      if (mainKey === "Backspace" && (active.tagName === "INPUT" || active.tagName === "TEXTAREA")) {
        if (active.selectionStart !== active.selectionEnd) {
          // 有选中文本，删除选中部分
          const start = active.selectionStart;
          const end = active.selectionEnd;
          active.value = active.value.slice(0, start) + active.value.slice(end);
          active.selectionStart = active.selectionEnd = start;
        } else if (active.selectionStart > 0) {
          // 删除光标前一个字符
          const pos = active.selectionStart - 1;
          active.value = active.value.slice(0, pos) + active.value.slice(pos + 1);
          active.selectionStart = active.selectionEnd = pos;
        }
        active.dispatchEvent(new Event("input", { bubbles: true }));
        return null;
      }

      const keyMap = {
        Enter: { key: "Enter", code: "Enter", keyCode: 13 },
        ArrowDown: { key: "ArrowDown", code: "ArrowDown", keyCode: 40 },
        Tab: { key: "Tab", code: "Tab", keyCode: 9 },
        Backspace: { key: "Backspace", code: "Backspace", keyCode: 8 },
      };
      const info = keyMap[mainKey] || { key: mainKey, code: mainKey, keyCode: 0 };
      active.dispatchEvent(new KeyboardEvent("keydown", { ...info, ...mods, bubbles: true }));
      active.dispatchEvent(new KeyboardEvent("keyup", { ...info, ...mods, bubbles: true }));
      return null;
    }

    case "type_text": {
      return new Promise(async (resolve) => {
        const active = document.activeElement || document.body;
        const inCE = active.isContentEditable;
        const isInput = (active.tagName === "INPUT" || active.tagName === "TEXTAREA");
        for (const char of params.text) {
          if (inCE) {
            document.execCommand("insertText", false, char);
          } else if (isInput) {
            // 对 input/textarea 逐字拼接 value 并触发 input 事件
            const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
              window.HTMLInputElement.prototype, 'value'
            )?.set || Object.getOwnPropertyDescriptor(
              window.HTMLTextAreaElement.prototype, 'value'
            )?.set;
            if (nativeInputValueSetter) {
              nativeInputValueSetter.call(active, active.value + char);
            } else {
              active.value += char;
            }
            active.dispatchEvent(new Event("input", { bubbles: true }));
          } else {
            active.dispatchEvent(new KeyboardEvent("keydown", { key: char, bubbles: true }));
            active.dispatchEvent(new KeyboardEvent("keypress", { key: char, bubbles: true }));
            active.dispatchEvent(new KeyboardEvent("keyup", { key: char, bubbles: true }));
          }
          await sleep(params.delayMs || 50);
        }
        resolve(null);
      });
    }

    case "remove_element": {
      const el = document.querySelector(params.selector);
      if (el) el.remove();
      return null;
    }

    case "hover_element": {
      const el = document.querySelector(params.selector);
      if (el) {
        const rect = el.getBoundingClientRect();
        const x = rect.left + rect.width / 2, y = rect.top + rect.height / 2;
        el.dispatchEvent(new MouseEvent("mouseover", { clientX: x, clientY: y, bubbles: true }));
        el.dispatchEvent(new MouseEvent("mousemove", { clientX: x, clientY: y, bubbles: true }));
      }
      return null;
    }

    case "select_all_text": {
      const el = document.querySelector(params.selector);
      if (el) { el.focus(); if (el.select) el.select(); else document.execCommand("selectAll"); }
      return null;
    }

    default:
      return { __dy_error: `未知 DOM 命令: ${method}` };
  }
}

// ───────────────────────── Tab 管理 ─────────────────────────

async function getOrOpenDYTab() {
  // 1. 优先查当前激活的
  const activeTabs = await chrome.tabs.query({ active: true, currentWindow: true });
  if (activeTabs[0] && activeTabs[0].url?.includes("douyin.com")) {
    return activeTabs[0];
  }

  // 2. 查所有已打开的抖音相关
  const tabs = await chrome.tabs.query({
    url: [
      "*://www.douyin.com/*",
      "*://creator.douyin.com/*",
    ],
  });
  if (tabs.length > 0) {
    // 找到后激活并聚焦窗口
    const tab = tabs[0];
    await chrome.tabs.update(tab.id, { active: true });
    await chrome.windows.update(tab.windowId, { focused: true });
    return tab;
  }

  // 3. 实在没有才新建
  const tab = await chrome.tabs.create({ url: "https://www.douyin.com/", active: true });
  await chrome.windows.update(tab.windowId, { focused: true });
  await waitForTabComplete(tab.id, null, 30000);
  return tab;
}

// ───────────────────────── 启动 ─────────────────────────

connect();
