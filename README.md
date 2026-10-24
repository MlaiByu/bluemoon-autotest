# bluemoon-autotest

针对 [BlueMoon 博客](https://github.com/MlaiByu/bluemoon) 后端（blog-api，FastAPI）的接口自动化测试框架。

> 定位：这不是"给项目补测试"，而是一个独立的**测试开发项目**——
> 用分层框架对一个真实运行的后端系统做接口回归 + 越权测试。

## 框架分层

```
tests/        用例层：只表达业务语义（登录成功/草稿不可见/匿名被拦截）
apis/         接口封装层：一个接口一个方法，URL/参数变动只改这里
common/       公共层：ApiClient（Session 封装、Token 注入、超时、日志）
config/       配置层：环境地址、账号、标记（密码走环境变量，不进库）
```

换环境只改配置、换接口只改封装、用例只写业务断言——这是分层的意义。

## 被测系统契约（测试依据）

- 统一响应封装：`{"code": 0, "msg": "...", "data": ...}`，业务成功 code=0
- 错误映射：401 未认证 / 403 无权限 / 404 不存在 / 422 参数校验 / 429 限流
- 认证：JWT Bearer；登出后 token 进入服务端黑名单立即失效
- 文章状态：0=草稿（前台不可见） 1=发布

## 用例清单（v1：22 条）

| 文件 | 用例 | 类型 |
|------|------|------|
| test_health | 健康检查封装正确 / MySQL 在线 | smoke |
| test_auth | 登录成功 / 密码错误 / 缺参数 / 登出后旧 token 失效 | smoke |
| test_posts_crud | 草稿增查改删 / 后台列表可搜 / 缺标题 / 标题 200 边界 / 201 越界 / 非法 status | crud |
| test_authz | 5 个管理员接口匿名拦截 / 伪造 token / 草稿对前台列表与详情不可见 | security |

## 快速开始

```bash
# 1. 创建虚拟环境（Python 3.12）
D:\python\python312\python.exe -m venv .venv
.venv\Scripts\activate

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置管理员密码（不进代码库）
set BM_ADMIN_PASSWORD=你的管理员密码

# 4. 启动被测系统（bluemoon/blog-api），然后运行
pytest
```

## 数据安全设计（重要）

被测的是真实博客，测试数据零污染三件套：

1. **草稿态**：测试文章一律 `status=0`，对前台完全不可见
2. **标记**：标题统一带 `[autotest]` 前缀，可识别可搜索
3. **自动清理**：fixture teardown 保证删除，用例失败也清理

## 已发现的被测系统缺陷（自动化测试产出）

### BUG-1 全文搜索不覆盖存量文章（已实测坐实，待修复）

- **现象**：keyword 搜索对 2026-10-24 之前创建的文章全部失效（前台列表 / 后台列表 / 详情搜索同源）
- **实证链**：`MATCH(title,summary,content) AGAINST('123')` 返回空，而 `LIKE '%123%'` 能命中 id=33；同一时刻新建文章（API 与 SQL 两种插入路径）均能立即被搜到 → 排除关键词形态与缓存因素，锁定索引未覆盖存量行
- **根因**：`posts` 表存量行不在 `ft_search` FULLTEXT 索引内（索引晚于数据创建且未重建）
- **影响**：老文章在站内搜索永远搜不到
- **修复建议**：`ALTER TABLE posts DROP INDEX ft_search, ADD FULLTEXT INDEX ft_search (title, summary, content) WITH PARSER ngram;`（重建索引即覆盖存量数据）

## Roadmap

- [ ] Allure 报告（allure-pytest 已接入依赖）
- [ ] GitHub Actions CI 门禁
- [ ] 文章列表分页参数边界用例
- [ ] 阅读上报去重（同 IP 5 分钟窗口）用例
- [ ] 分类接口用例
