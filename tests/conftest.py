"""pytest 全局 fixture —— 测试的依赖注入中心

fixture 是 pytest 的核心机制：用例函数只要声明同名参数，
pytest 就会自动把准备好的资源传进来（依赖注入）。

作用域选择原则（面试常问）：
- session 级：整个测试会话只建一次 —— 登录态、配置（初始化贵、数据只读）
- function 级：每个用例独立一份 —— 会产生数据的资源（隔离性最好）

数据安全红线（本项目最重要的设计约束）：
被测的是真实博客，测试绝不能污染真实内容。对策三件套：
1. 测试文章一律 status=0（草稿），对前台完全不可见
2. 标题带 [autotest] 标记，可识别、可搜索
3. fixture teardown 统一删除，无论用例成功还是失败
"""
import os
import uuid
from pathlib import Path

import pytest
import yaml

from apis.auth_api import AuthApi
from apis.post_api import PostApi
from common.api_client import ApiClient

ROOT = Path(__file__).resolve().parent.parent


def load_config() -> dict:
    """配置加载：环境变量 > config.local.yaml > config.yaml。

    两层文件设计：config.yaml 是进 git 的模板（密码留空），
    config.local.yaml 存真实凭据（被 .gitignore 排除）。
    凭据与模板分离，仓库公开也不泄密。
    """
    with open(ROOT / "config" / "config.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    # 本地覆盖层：存在则深合并（字典按键合并，其余直接覆盖）
    local_path = ROOT / "config" / "config.local.yaml"
    if local_path.exists():
        with open(local_path, encoding="utf-8") as f:
            local = yaml.safe_load(f) or {}
        for key, value in local.items():
            if isinstance(value, dict) and isinstance(cfg.get(key), dict):
                cfg[key].update(value)
            else:
                cfg[key] = value

    # 环境变量最高优先级（CI 上不落任何凭据文件，用环境变量注入）
    cfg["base_url"] = os.getenv("BM_BASE_URL", cfg.get("base_url", "http://127.0.0.1:8000"))
    cfg["api_prefix"] = os.getenv("BM_API_PREFIX", cfg.get("api_prefix", "/api/v1"))
    cfg["timeout"] = float(os.getenv("BM_TIMEOUT", cfg.get("timeout", 10)))
    cfg.setdefault("admin", {})
    cfg["admin"]["username"] = os.getenv("BM_ADMIN_USERNAME", cfg["admin"].get("username", "admin"))
    cfg["admin"]["password"] = os.getenv("BM_ADMIN_PASSWORD", cfg["admin"].get("password", ""))
    cfg.setdefault("test_marker", "[autotest]")
    return cfg


@pytest.fixture(scope="session")
def config() -> dict:
    """全局配置（session 级：只读一次）"""
    return load_config()


@pytest.fixture(scope="session")
def bare_client(config) -> ApiClient:
    """匿名客户端：不携带任何登录态。

    用于公开接口用例 + 鉴权拦截用例（代表"未登录的攻击者"）。
    """
    return ApiClient(config["base_url"], config["api_prefix"], config["timeout"])


@pytest.fixture(scope="session")
def admin_credentials(config) -> dict:
    """管理员凭据守卫：密码未配置时，依赖登录态的用例统一 skip（而非报错）。

    skip 和 fail 语义必须分清：环境不满足 = skip（不是这次要测的问题）；
    断言不通过 = fail。把"没配密码"算成 fail 会污染测试报告的信号。
    """
    if not config["admin"]["password"]:
        pytest.skip("未配置 BM_ADMIN_PASSWORD，跳过需要登录态的用例")
    return config["admin"]


@pytest.fixture(scope="session")
def admin_client(config, admin_credentials, bare_client) -> ApiClient:
    """管理员客户端：session 级登录一次，全程复用。"""
    resp = AuthApi(bare_client).login(
        admin_credentials["username"], admin_credentials["password"]
    )
    body = resp.json()
    assert body["code"] == 0, f"管理员登录失败：HTTP {resp.status_code} {resp.text}"
    client = ApiClient(config["base_url"], config["api_prefix"], config["timeout"])
    client.set_token(body["data"]["access_token"])
    return client


@pytest.fixture()
def draft_post_factory(admin_client, config):
    """草稿文章工厂（function 级：每个用例独立、互不干扰）。

    用法：
        def test_xxx(draft_post_factory):
            post = draft_post_factory(title="自定义标题")
            post["id"]        # 创建后的文章 ID
            post["payload"]   # 实际提交的数据

    teardown 逻辑写在 yield 之后：无论用例成功、失败还是断言报错，
    都会执行 —— 这是"测试数据不残留"的机制保证，不靠人记得删。
    """
    created_ids: list[int] = []
    marker = config["test_marker"]

    def _make(**overrides) -> dict:
        payload = {
            "title": f"{marker} 测试文章 {uuid.uuid4().hex[:8]}",
            "content": "自动化测试草稿内容，可安全删除。",
            "status": 0,  # 0=草稿：对前台完全不可见
            **overrides,
        }
        resp = PostApi(admin_client).create(payload)
        body = resp.json()
        assert body["code"] == 0, f"创建测试草稿失败：HTTP {resp.status_code} {resp.text}"
        post_id = body["data"]["id"]
        created_ids.append(post_id)
        return {"id": post_id, "payload": payload, "data": body["data"]}

    yield _make

    # ---- teardown：逆序清理本用例创建的所有草稿 ----
    for pid in reversed(created_ids):
        resp = PostApi(admin_client).delete(pid)
        # 404 容忍：用例自己删过的，再删一次报 404 属正常
        assert resp.json()["code"] in (0, 404), f"清理测试文章 {pid} 失败：{resp.text}"
