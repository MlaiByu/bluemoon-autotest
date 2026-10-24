"""文章相关接口封装（对应被测系统 app/api/v1/posts.py）"""
from common.api_client import ApiClient


class PostApi:
    def __init__(self, client: ApiClient):
        self.client = client

    # ---------- 公开接口（无需登录） ----------
    def list_public(self, params: dict | None = None):
        """文章列表（前台视角，仅返回已发布）：GET /posts"""
        return self.client.get("/posts", params=params or {})

    def detail_by_slug(self, slug: str):
        """文章详情（按 slug，前台视角，草稿返回 404）：GET /posts/detail/{slug}"""
        return self.client.get(f"/posts/detail/{slug}")

    # ---------- 管理员接口（需登录） ----------
    def list_admin(self, params: dict | None = None):
        """后台文章列表（含草稿）：GET /posts/admin"""
        return self.client.get("/posts/admin", params=params or {})

    def get_by_id(self, post_id: int):
        """按 ID 查文章（后台）：GET /posts/{post_id}"""
        return self.client.get(f"/posts/{post_id}")

    def create(self, payload: dict):
        """新建文章：POST /posts（status: 0=草稿 1=发布）"""
        return self.client.post("/posts", json=payload)

    def update(self, post_id: int, payload: dict):
        """更新文章：PUT /posts/{post_id}"""
        return self.client.put(f"/posts/{post_id}", json=payload)

    def delete(self, post_id: int):
        """删除文章：DELETE /posts/{post_id}"""
        return self.client.delete(f"/posts/{post_id}")
