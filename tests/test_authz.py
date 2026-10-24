"""越权与异常场景 —— 安全背景在测开上的落地用例

设计视角：把自己当成"没登录的攻击者"，逐个检查管理员接口的
门是否真的锁了。这类用例的通用断言模式：
    未认证访问受保护资源 → 401，code=401，data 为空
"""
import allure
import pytest

from apis.post_api import PostApi


@allure.feature("安全越权")
@pytest.mark.security
class TestAnonymousAccess:
    """未认证访问受保护接口，必须全部被 401 拦截"""

    def test_me_without_token(self, bare_client):
        resp = bare_client.get("/auth/me")
        assert resp.status_code == 401
        assert resp.json()["code"] == 401
        assert not resp.json()["data"]

    def test_admin_list_without_token(self, bare_client):
        resp = PostApi(bare_client).list_admin()
        assert resp.status_code == 401

    def test_get_post_by_id_without_token(self, bare_client):
        """按 ID 查文章是后台接口（含草稿正文），匿名必须 401"""
        resp = PostApi(bare_client).get_by_id(1)
        assert resp.status_code == 401

    def test_create_post_without_token(self, bare_client):
        """匿名写操作是最危险的一类，单独成用例"""
        resp = PostApi(bare_client).create({"title": "匿名写入测试", "content": "x"})
        assert resp.status_code == 401

    def test_cache_info_without_token(self, bare_client):
        """Redis 缓存状态接口暴露基础设施信息，匿名必须 401"""
        resp = bare_client.get("/cache/info")
        assert resp.status_code == 401


@allure.feature("安全越权")
@pytest.mark.security
class TestTokenForgery:
    """伪造 token 必须被拒绝 —— 服务端校验签名，而不是仅看 header 存在"""

    def test_forged_token_rejected(self, bare_client):
        client = bare_client
        client.set_token("eyJhbGciOiJIUzI1NiJ9.forged.signature")
        try:
            resp = client.get("/auth/me")
            assert resp.status_code == 401, "伪造 token 竟然通过校验！"
        finally:
            client.set_token(None)  # 还原客户端为匿名态，避免污染同 session 的其他用例


@allure.feature("安全越权")
@pytest.mark.security
class TestDraftConfidentiality:
    """草稿保密性：草稿对前台必须完全不可见（列表、详情两个入口都要查）"""

    def test_draft_hidden_in_public_list(self, admin_client, bare_client, draft_post_factory):
        post = draft_post_factory()
        resp = PostApi(bare_client).list_public({"keyword": post["payload"]["title"], "page_size": 100})
        body = resp.json()
        assert body["code"] == 0
        ids = [item["id"] for item in body["data"]["list"]]
        assert post["id"] not in ids, "草稿出现在前台列表 —— 越权泄露！"

    def test_draft_hidden_in_public_detail(self, admin_client, bare_client, draft_post_factory):
        post = draft_post_factory()
        slug = post["data"]["slug"]
        resp = PostApi(bare_client).detail_by_slug(slug)
        assert resp.status_code == 404, "前台能访问草稿详情 —— 越权泄露！"
