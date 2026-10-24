"""认证相关接口封装（对应被测系统 app/api/v1/auth.py）"""
from common.api_client import ApiClient


class AuthApi:
    def __init__(self, client: ApiClient):
        self.client = client

    def login(self, username: str, password: str):
        """管理员登录：POST /auth/login"""
        return self.client.post("/auth/login", json={"username": username, "password": password})

    def logout(self):
        """退出登录：POST /auth/logout（服务端会把当前 token 拉黑）"""
        return self.client.post("/auth/logout")

    def me(self):
        """当前登录用户：GET /auth/me"""
        return self.client.get("/auth/me")

    def update_me(self, data: dict):
        """修改个人信息：PUT /auth/me"""
        return self.client.put("/auth/me", json=data)
