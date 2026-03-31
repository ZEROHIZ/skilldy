"""抖音自动化异常体系。"""

class DYError(Exception):
    """抖音自动化基础异常。"""

class NoFeedsError(DYError):
    """没有捕获到 feeds 数据。"""
    def __init__(self) -> None:
        super().__init__("没有捕获到 feeds 数据")

class NoVideoDetailError(DYError):
    """没有捕获到视频详情数据。"""
    def __init__(self) -> None:
        super().__init__("没有捕获到视频详情数据")

class NotLoggedInError(DYError):
    """未登录。"""
    def __init__(self) -> None:
        super().__init__("未登录，请先登录抖音")

class PageNotAccessibleError(DYError):
    """页面不可访问。"""
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"页面不可访问: {reason}")

class PublishError(DYError):
    """发布失败。"""

class CDPError(DYError):
    """CDP 通信异常。"""

class ElementNotFoundError(DYError):
    """页面元素未找到。"""
    def __init__(self, selector: str) -> None:
        self.selector = selector
        super().__init__(f"未找到元素: {selector}")
