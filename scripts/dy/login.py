"""检查登录状态。"""

import logging
from .bridge import BridgePage
from .urls import HOME_URL

logger = logging.getLogger(__name__)

def check_login(page: BridgePage) -> bool:
    """检查抖音是否登录。"""
    current_url = page.get_url()
    if "douyin.com" not in current_url:
        page.navigate(HOME_URL)
        page.wait_for_load(timeout=20.0)
    
    # 扩展提供了一个 get_cookies 方法（需要修改 extension 获取特定 domain 的 cookies）
    # 但我们目前使用的是短连接 bridge，没有专门的 get_cookies API 封装，
    # 我们通过执行 document.cookie 来检查（仅针对非 HttpOnly），或者通过 DOM 检测是否有登录提示
    
    # 获取登录弹出框是否可见，如果可见，就是没登录
    # 另一种更通用的方法是读取 localstorage 或全局对象
    has_login_modal = page.has_element("#login-pannel")
    if has_login_modal:
        logger.info("检测到登录弹窗，未登录。")
        return False
        
    js_check = """
    (() => {
        let isLogin = false;
        // 尝试通过全局变量拿登录状态，比如 router_data，通常都有 user 信息
        if (window._ROUTER_DATA && window._ROUTER_DATA.app && window._ROUTER_DATA.app.user) {
            isLogin = window._ROUTER_DATA.app.user.isLogin;
        }
        return isLogin;
    })()
    """
    is_login = page.evaluate(js_check)
    if is_login:
        return True
        
    # fallback
    cookies = page.evaluate("document.cookie")
    if "sessionid=" in cookies or "passport_csrf_token" in cookies:
        return True
        
    return False
