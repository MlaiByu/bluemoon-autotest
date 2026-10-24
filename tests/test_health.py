"""冒烟用例：服务可达性 —— 任何更深层的测试之前，先确认被测系统活着"""
import allure
import pytest

from apis.auth_api import AuthApi


@allure.feature("系统健康")
@pytest.mark.smoke
class TestHealth:
    def test_health_returns_ok_envelope(self, bare_client):
        """健康检查返回统一封装，状态为 ok 或 degraded（Redis 挂了算降级不算挂）"""
        resp = bare_client.get("/health")
        assert resp.status_code == 200, f"健康检查 HTTP {resp.status_code}"
        body = resp.json()
        # 统一响应封装：业务层一切响应都是 {code, msg, data}
        assert body["code"] == 0
        # 只断言结构和取值范围，不断言具体版本号 —— 断言越贴近"契约"，用例越稳定
        assert body["data"]["status"] in ("ok", "degraded")
        assert "app" in body["data"] and "version" in body["data"]

    def test_health_mysql_up(self, bare_client):
        """本地开发环境 MySQL 必须在线；Redis 允许降级"""
        resp = bare_client.get("/health")
        data = resp.json()["data"]
        assert data["mysql"] == "up", f"MySQL 未在线：{data}"
