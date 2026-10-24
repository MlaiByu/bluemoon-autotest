"""认证用例：登录成功 / 失败 / 登出后 token 失效

覆盖思路：正向 1 条 + 异常 2 条 + 安全闭环 1 条。
重点用例是 test_logout_invalidates_token —— 它验证的不是
"登出返回 200"，而是"登出之后旧 token 真的不能用"。
测试有效性永远体现在"验证行为结果"，不是"验证接口返回 200"。
"""
import allure
import pytest

from apis.auth_api import AuthApi
from common.api_client import ApiClient


@allure.feature("认证")
@pytest.mark.smoke
class TestLogin:
    def test_login_success(self, bare_client, admin_credentials):
        """正向：正确账号密码 → code=0，返回 access_token 和用户信息"""
        resp = AuthApi(bare_client).login(
            admin_credentials["username"], admin_credentials["password"]
        )
        body = resp.json()
        assert resp.status_code == 200
        assert body["code"] == 0, f"登录失败：{body}"
        data = body["data"]
        # 断言关键字段而非全量字段：token 非空、用户名回显正确
        assert data["access_token"], "access_token 不应为空"
        assert data["token_type"].lower() == "bearer"
        assert data["user"]["username"] == admin_credentials["username"]

    def test_login_wrong_password(self, bare_client, admin_credentials):
        """异常：密码错误 → 401，且响应体不能泄露"用户存在"这类信息"""
        resp = AuthApi(bare_client).login(admin_credentials["username"], "wrong-password-x")
        assert resp.status_code == 401
        body = resp.json()
        assert body["code"] == 401
        assert not body["data"], "登录失败不应返回任何 data"

    def test_login_missing_password(self, bare_client, admin_credentials):
        """异常：缺密码字段 → 422 参数校验（统一封装下 code=422）"""
        resp = bare_client.post("/auth/login", json={"username": admin_credentials["username"]})
        assert resp.status_code == 422
        assert resp.json()["code"] == 422


@allure.feature("认证")
class TestLogoutAndBlacklist:
    def test_logout_invalidates_token(self, config, admin_credentials):
        """安全闭环：登出后旧 token 必须立即失效（服务端黑名单机制）

        用独立的客户端完成完整链路：登录 → 登出 → 复用旧 token 被拒。
        不复用 session 级 admin_client —— 那会把全局登录态登出。
        """
        login_resp = AuthApi(ApiClient(config["base_url"], config["api_prefix"], config["timeout"])).login(
            admin_credentials["username"], admin_credentials["password"]
        )
        token = login_resp.json()["data"]["access_token"]

        client = ApiClient(config["base_url"], config["api_prefix"], config["timeout"])
        client.set_token(token)
        assert client.post("/auth/logout").json()["code"] == 0

        # 关键断言：同一个 token，登出后再访问受保护接口 → 401
        resp = client.get("/auth/me")
        assert resp.status_code == 401, "登出后旧 token 仍可访问 —— 黑名单失效！"
        assert resp.json()["code"] == 401
