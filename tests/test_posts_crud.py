"""文章 CRUD 用例：以草稿为载体，增删改查全链路 + 边界值

数据安全设计：所有测试文章 status=0（草稿）+ [autotest] 标题标记，
teardown 统一删除 —— 对前台用户和真实博客数据零影响。

边界值分析落地：被测系统 title 限制 max_length=200（见 PostIn schema），
那么 200 是合法边界、201 是非法边界 —— 每个都要测，这是教科书式的
边界值分析在真实项目里的用法。
"""
import allure
import pytest

from apis.post_api import PostApi


@allure.feature("文章管理")
@pytest.mark.crud
class TestPostCRUD:
    def test_create_draft_then_get_by_id(self, admin_client, draft_post_factory):
        """正向：创建草稿 → 按 ID 查回 → 关键字段与提交一致"""
        post = draft_post_factory()
        resp = PostApi(admin_client).get_by_id(post["id"])
        body = resp.json()
        assert body["code"] == 0
        data = body["data"]
        assert data["id"] == post["id"]
        assert data["title"] == post["payload"]["title"]
        assert data["status"] == 0, "测试文章必须是草稿态"
        assert data["content"] == post["payload"]["content"]

    def test_update_draft(self, admin_client, draft_post_factory):
        """正向：更新草稿标题与正文 → 查回验证生效"""
        post = draft_post_factory()
        new_payload = {**post["payload"], "title": post["payload"]["title"] + "-已更新",
                       "content": "更新后的内容"}
        resp = PostApi(admin_client).update(post["id"], new_payload)
        assert resp.json()["code"] == 0, resp.text
        data = PostApi(admin_client).get_by_id(post["id"]).json()["data"]
        assert data["title"] == new_payload["title"]
        assert data["content"] == new_payload["content"]

    def test_delete_draft(self, admin_client, draft_post_factory):
        """正向：删除草稿 → 再查返回 404"""
        post = draft_post_factory()
        assert PostApi(admin_client).delete(post["id"]).json()["code"] == 0
        resp = PostApi(admin_client).get_by_id(post["id"])
        assert resp.status_code == 404
        assert resp.json()["code"] == 404

    def test_admin_list_finds_draft(self, admin_client, draft_post_factory, config):
        """后台列表：按标记关键词能搜到刚创建的草稿"""
        post = draft_post_factory()
        resp = PostApi(admin_client).list_admin({"keyword": config["test_marker"], "page_size": 100})
        body = resp.json()
        assert body["code"] == 0
        ids = [item["id"] for item in body["data"]["list"]]
        assert post["id"] in ids, "后台列表应包含刚创建的草稿"


@allure.feature("文章管理")
class TestPostValidation:
    """参数校验：用例写的是"服务端契约"，不写实现细节"""

    def test_create_without_title(self, admin_client):
        """缺必填字段 title → 422"""
        resp = PostApi(admin_client).create({"content": "没有标题"})
        assert resp.status_code == 422
        assert resp.json()["code"] == 422

    def test_title_max_length_boundary(self, admin_client, draft_post_factory):
        """边界值：title 恰好 200 字应被接受（契约 max_length=200）"""
        title_200 = "边" * 200
        post = draft_post_factory(title=title_200)
        assert post["data"]["title"] == title_200

    def test_title_over_max_length(self, admin_client):
        """边界值：title 201 字应被拒绝 → 422"""
        resp = PostApi(admin_client).create({"title": "边" * 201, "content": "x"})
        assert resp.status_code == 422
        assert resp.json()["code"] == 422

    def test_create_with_invalid_status(self, admin_client):
        """异常值：status 只允许 0/1（契约 ge=0 le=1），传 2 → 422"""
        resp = PostApi(admin_client).create({"title": "x", "status": 2})
        assert resp.status_code == 422
