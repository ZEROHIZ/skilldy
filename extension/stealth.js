/**
 * stealth.js - 隐藏自动化痕迹 & 静默拦截 API
 * 在页面脚本执行前注入（document_start, MAIN world）
 */
(function () {
  "use strict";

  // 1. 完善反检测特征
  // 彻底隐藏 webdriver 标识 (包括 getter 和 toString)
  let webdriverGetter = Object.getOwnPropertyDescriptor(Navigator.prototype, "webdriver")?.get;
  if(webdriverGetter) {
      Object.defineProperty(navigator, "webdriver", {
        get: new Proxy(webdriverGetter, {
          apply: (target, thisArg, argArray) => undefined
        })
      });
  } else {
      Object.defineProperty(navigator, "webdriver", { get: () => undefined });
  }

  // 隐藏自动化属性
  const autoProps = [
    "__selenium_unwrapped", "__webdriver_evaluate", "__driver_evaluate",
    "__webdriver_unwrapped", "__driver_unwrapped", "__selenium_evaluate",
    "_selenium", "callSelenium", "_Selenium_IDE_Recorder",
    "callPhantom", "__nightmare", "domAutomation", "domAutomationController",
  ];
  for (const prop of autoProps) {
    try { delete window[prop]; } catch {}
  }

  // 伪装 window.chrome
  if (!window.chrome) window.chrome = {};
  if (!window.chrome.runtime) window.chrome.runtime = {};
  if (!window.chrome.csi) window.chrome.csi = function() {};
  if (!window.chrome.app) window.chrome.app = {};
  if (!window.chrome.loadTimes) window.chrome.loadTimes = function() {};

  // 伪装硬件和语言指纹
  if (!navigator.plugins || navigator.plugins.length === 0) {
    Object.defineProperty(navigator, "plugins", { get: () => [1, 2, 3, 4, 5] });
  }
  if (!navigator.languages || navigator.languages.length === 0) {
    Object.defineProperty(navigator, "languages", { get: () => ["zh-CN", "zh", "en-US", "en"] });
  }
  Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
  Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });
  
  // 伪装 WebGL Vendor / Renderer
  const getParameterProxyHandler = {
    apply: function (target, thisArg, argumentsList) {
      const param = argumentsList[0];
      if (param === 37445) { // UNMASKED_VENDOR_WEBGL
        return 'Intel Inc.';
      }
      if (param === 37446) { // UNMASKED_RENDERER_WEBGL
        return 'Intel Iris OpenGL Engine';
      }
      return Reflect.apply(target, thisArg, argumentsList);
    }
  };
  if(typeof WebGLRenderingContext !== 'undefined') {
      WebGLRenderingContext.prototype.getParameter = new Proxy(WebGLRenderingContext.prototype.getParameter, getParameterProxyHandler);
  }
  if(typeof WebGL2RenderingContext !== 'undefined') {
      WebGL2RenderingContext.prototype.getParameter = new Proxy(WebGL2RenderingContext.prototype.getParameter, getParameterProxyHandler);
  }

  // 通知权限绕过
  const origQuery = window.Permissions?.prototype?.query;
  if (origQuery) {
    window.Permissions.prototype.query = function (params) {
      if (params?.name === "notifications") {
        return Promise.resolve({ state: Notification.permission });
      }
      return origQuery.call(this, params);
    };
  }

  // 2. 静默注入 API 拦截钩子 (Mirror Proxy 版)
  function dispatchCapturedData(url, data) {
    if (!url || !data) return;
    
    let fullUrl = url;
    try {
        fullUrl = new URL(url, window.location.href).href;
    } catch(e) {}

    // 宽泛匹配抖音相关 API
    if (!fullUrl.includes("aweme/v1/")) return;
    
    // 发送给 Content Script
    window.postMessage({
      type: "DY_API_CAPTURED",
      url: fullUrl,
      data: data
    }, "*");
  }

  // A. Hook XMLHttpRequest (使用构造函数代理，防止原型链绕过)
  const OriginalXHR = window.XMLHttpRequest;
  function MyXHR() {
    const xhr = new OriginalXHR();
    const oldOpen = xhr.open;
    xhr.open = function(method, url) {
      this._dyUrl = url;
      return oldOpen.apply(this, arguments);
    };

    const oldSend = xhr.send;
    xhr.send = function() {
      if (this._dyUrl && this._dyUrl.includes("aweme/v1/")) {
        // 1. 劫持 readystatechange
        const self = this;
        const oldOnReady = self.onreadystatechange;
        self.onreadystatechange = function() {
          if (self.readyState === 4 && self.status === 200) {
            handleXhrResponse(self);
          }
          if (oldOnReady) return oldOnReady.apply(this, arguments);
        };

        // 2. 劫持 load 作为兜底
        self.addEventListener('load', () => {
           if (self.status === 200) handleXhrResponse(self);
        });
      }
      return oldSend.apply(this, arguments);
    };

    async function handleXhrResponse(xhrObj) {
        if (xhrObj._dyDone) return; 
        xhrObj._dyDone = true;
        try {
            let data = "";
            if (xhrObj.responseType === 'json') {
                data = JSON.stringify(xhrObj.response);
            } else if (xhrObj.responseType === '' || xhrObj.responseType === 'text') {
                data = xhrObj.responseText;
            } else if (xhrObj.response) {
                data = (typeof xhrObj.response === 'string') ? xhrObj.response : JSON.stringify(xhrObj.response);
            }
            if (data) dispatchCapturedData(xhrObj._dyUrl, data);
        } catch (e) {}
    }
    return xhr;
  }
  // 保持原型链完整性
  MyXHR.prototype = OriginalXHR.prototype;
  window.XMLHttpRequest = MyXHR;



  // Hook fetch (支持流式读取，不破坏原功能)
  const origFetch = window.fetch;
  window.fetch = async function(...args) {
    const rawUrl = typeof args[0] === 'string' ? args[0] : args[0]?.url || "";
    
    // 【修复】补全并判断
    let reqUrl = rawUrl;
    try {
        reqUrl = new URL(rawUrl, window.location.href).href;
    } catch(e) {}
    
    const isTarget = reqUrl.includes("aweme/v1/");
    
    const response = await origFetch.apply(this, args);
    
    if (isTarget && response.clone) {
      const clonedResponse = response.clone();
      clonedResponse.text().then(text => {
         dispatchCapturedData(reqUrl, text);
      }).catch(e => {
         // 静默失败
      });
    }
    return response;
  };

})();

