# campus-lost-found
a demo app used to help students find what they lost

校园失物招领演示项目：**前后端分离**的 5 个独立页面（首页 / 搜索 / 详情 / 发布 / 发布成功）
配一个 FastAPI + SQLite 的后端。前端只负责发请求和渲染，筛选、搜索、排序、状态变更、
脱敏、编号生成全部在服务端完成。

## 技术栈

| 层 | 用了什么 | 说明 |
| --- | --- | --- |
| 前端 | 5 个独立 `.html` + 每页一个 `.js` | **不做单页应用**，不用 Node 构建；主题样式只有 `frontend/css/visual-theme.css` 一份 |
| 后端 | Python 3.14 + FastAPI | 纯 `uvicorn`，不用 `uvicorn[standard]`（后者要编译二进制依赖） |
| 存储 | 单个 SQLite 文件 + stdlib `sqlite3` | 不用 ORM；每请求一个连接，开启 WAL |
| 测试 | pytest（unit / integration / contract 三层）+ ruff | CI 见 `.github/workflows/ci.yml` |

页面仍从外部 CDN 加载 Tailwind 运行时与 Iconify 图标，**离线环境下页面样式与图标不显示**。

## 目录结构

```
campus-lost-found/
├── frontend/                  展示层：5 个页面平铺，各自独立
│   ├── index.html             首页（兼作站点入口）
│   ├── search.html  detail.html  publish.html  success.html
│   ├── css/visual-theme.css   全站唯一一份主题
│   └── js/                    api.js + common.js + 每页一个 js
├── backend/                   服务层
│   ├── main.py                路由与装配（不写 SQL）
│   ├── db.py                  连接、建表、路径解析
│   ├── schemas.py             请求/响应模型
│   ├── serialize.py           行 → 响应对象（纯函数）
│   ├── uploads.py             图片校验与落盘（纯函数）
│   ├── seed.py                演示数据（幂等）
│   └── __main__.py            启动入口：python -m backend
├── tests/                     测试层：unit / integration / contract
├── docs/                      PRD、系统设计、开发计划、代码规范
├── build_exe.py               打包成单文件 exe
├── db.sqlite3                 运行时生成，不入库
└── uploads/                   上传的图片，运行时生成，不入库
```

## 运行

```bash
cd "F:/vibe coding/campus-lost-found"
python -m venv .venv
source .venv/Scripts/activate          # Git Bash；PowerShell 用 .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt    # 只跑服务的话用 requirements.txt 即可
python -m backend.seed                 # 建表 + 写入 8 条演示数据（可重复执行，不会重复）
uvicorn backend.main:app --reload --port 8000
```

也可以一步启动（会自动建库、播种、开浏览器，`--no-browser` 可关掉）：

```bash
python -m backend                # 默认 127.0.0.1:8000，可用 --host / --port 改
```

| 地址 | 内容 |
| --- | --- |
| `http://127.0.0.1:8000/` | 首页（`/index.html` 等价） |
| `http://127.0.0.1:8000/docs` | 接口交互文档（OpenAPI） |

**必须通过 http 访问**。直接双击 HTML 文件用 `file://` 打开时，浏览器的同源策略会拦掉
所有接口请求，页面会停在空列表上。

## 测试

```bash
python -m pytest -q                     # 全部（约 300 项）
python -m pytest tests/unit -q          # 单元：纯函数与校验规则
python -m pytest tests/integration -q   # 集成：6 个接口的端到端行为
python -m pytest tests/contract -q      # 契约：接口字段 ↔ 前端渲染所需字段
ruff check .                            # 代码风格检查
```

用 `python -m pytest` 而不是裸 `pytest`，是为了把工作目录加进 `sys.path`、让测试能
`import backend`。测试一律使用**临时数据库与临时上传目录**，不会碰仓库里的
`db.sqlite3` 和 `uploads/`。

手工验收清单（页面的视觉与交互，自动化覆盖不到）见《系统设计文档》第 12 节。

## 打包成 exe

```bash
.venv/Scripts/python.exe build_exe.py    # 产物是仓库根目录的 campus-lost-found.exe
```

双击即启动服务并用 Chrome 打开首页。`db.sqlite3` 与 `uploads/` 都落在 exe 同级目录，
首次运行自动创建；**改动 `frontend/` 下的文件不需要重新打包**（exe 优先使用同级的
`frontend/`），只有后端 Python 代码变了才要重建。详见《系统设计文档》11.1 节。

## 文档

| 文档 | 内容 |
| --- | --- |
| [docs/PRD.md](docs/PRD.md) | 产品需求：逐页功能、字段与校验文案、验收标准、变更记录 |
| [docs/system-design.md](docs/system-design.md) | 系统设计：架构、数据库、接口、时序图、部署、验收清单 |
| [docs/development-plan.md](docs/development-plan.md) | 开发计划：阶段划分、任务清单、里程碑、风险 |
| [docs/coding-standards.md](docs/coding-standards.md) | 代码规范：分层职责、注释与测试要求、提交规范 |
| [docs/openapi.json](docs/openapi.json) | 由代码导出的 OpenAPI 3.1 文档（有测试盯着它与代码一致） |

## 已知限制

无用户体系与鉴权（发布者昵称固定，任何人都能标记任意条目为已解决，且该变更全局生效）；
无分页；图片仅支持**一张**且不解码、不做 EXIF 旋转校正；上传接口无鉴权、上传成功但发布
失败会留下孤儿图片；依赖外部 CDN。完整列表见《系统设计文档》第 13 节。
