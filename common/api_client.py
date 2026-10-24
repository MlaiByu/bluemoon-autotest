"""API 客户端：requests.Session 的薄封装

分层设计中「公共层」的核心。设计要点（面试被问到框架时照着讲）：

1. 统一拼 base_url + api_prefix —— 用例层只写相对路径，
   换环境只改配置文件，不改任何用例代码。
2. Token 统一注入 Authorization 头 —— 认证细节对用例透明，
   用例里看不到任何 header 拼接。
3. 每次请求打一行日志（方法/URL/状态码/耗时）—— 用例失败时
   有完整的请求轨迹可查，而不是只看到一个 assert 报错。
4. 超时是必填的默认值 —— 没有超时的请求是 CI 流水线挂死的
   第一大原因，必须在框架层强制。
"""
import logging
import time

import requests

logger = logging.getLogger("autotest")


class ApiClient:
    """单个"虚拟用户"：持有一个 Session（自动管理 cookie/连接池）"""

    def __init__(self, base_url: str, api_prefix: str = "/api/v1", timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.api_prefix = api_prefix
        self.timeout = timeout
        self.session = requests.Session()

    # ---------- 认证态管理 ----------
    def set_token(self, token: str | None) -> None:
        """登录后注入 Token；传 None 清除登录态（用于匿名场景用例）"""
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"
        else:
            self.session.headers.pop("Authorization", None)

    # ---------- 请求入口 ----------
    def request(self, method: str, path: str, **kwargs) -> requests.Response:
        url = f"{self.base_url}{self.api_prefix}{path}"
        kwargs.setdefault("timeout", self.timeout)
        start = time.perf_counter()
        resp = self.session.request(method, url, **kwargs)
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info("%-6s %s -> %s (%.1fms)", method, url, resp.status_code, elapsed_ms)
        return resp

    def get(self, path: str, **kwargs) -> requests.Response:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs) -> requests.Response:
        return self.request("POST", path, **kwargs)

    def put(self, path: str, **kwargs) -> requests.Response:
        return self.request("PUT", path, **kwargs)

    def delete(self, path: str, **kwargs) -> requests.Response:
        return self.request("DELETE", path, **kwargs)
