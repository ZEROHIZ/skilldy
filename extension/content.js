/**
 * DY Bridge - Content Script（隔离 world）
 *
 * 目前大部分 DOM 操作都放在 background.js 中在 MAIN world 执行，
 * content.js 只作为备用和消息传递通道的占位符。
 */

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  // 不处理业务，仅做接收响应
  sendResponse({ result: null });
  return true;
});

// 监听由于 stealth.js 中注入的 Hook 截获的 API 数据
window.addEventListener("message", (event) => {
  if (event.source !== window) return;
  if (event.data && event.data.type === "DY_API_CAPTURED") {
    console.log("[DY Content] 收到 Hook 数据，准备转发给 background:", event.data.url);
    // 将数据转发给 background.js
    chrome.runtime.sendMessage({
      type: "FORWARD_DY_API_CAPTURED",
      url: event.data.url,
      data: event.data.data
    });
  }
});

function sleep(ms) {

  return new Promise((r) => setTimeout(r, ms));
}
