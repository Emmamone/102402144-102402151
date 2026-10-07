# 校园失物招领 · 系统设计文档

## 1. 概述与目标

本文档描述"校园失物招领"从纯静态页面改造为前后端分离架构的技术方案。

**改造基线**：现行源码是 5 个静态页面 + 一套定稿的「校园档案」视觉主题（墨绿 `#173f37` / 暖纸白 `#f6f3eb` / 朱砂橙 `#e86143`）。该主题目前以**字节完全相同的内联 `<style>` 块复制在 5 个文件里**（各 127 行），另有一份未被引用的 `visual-theme.css`。本方案的"页面不变"，指的是**以这一版为基线**保持渲染结果不变。

**设计目标**：

1. **页面不变** —— 5 个页面（首页、搜索、详情、发布、成功）的视觉表现与操作流程保持现状。
2. **职责分离** —— 前端只负责发送 HTTP 请求与渲染响应；数据存储、筛选、搜索、排序、状态变更全部由后端完成。
3. **数据保真** —— 8 条演示数据的文字、顺序、配色与现状逐字一致。
4. **可解释** —— 技术选型与数据结构都能在文档里讲清楚，适合作业/答辩材料。

**技术选型**：

| 层次 | 选型 | 理由 |
| --- | --- | --- |
| 后端框架 | FastAPI | 自带交互式接口文档（`/docs`），Pydantic 校验开箱可用，样板代码少。 |
| 数据访问 | Python 标准库 `sqlite3` | 只有一张表、几条简单查询，引入 ORM 会为了演示项目增加不必要的抽象层；原始 SQL 也能直接抄进本文档。 |
| 数据库 | SQLite 单文件 | 零运维，一条命令建表播种，不需要额外安装数据库服务。 |
| 前端 | 原生 HTML + 原生 `fetch` | 页面必须保持不变，不引入任何构建工具与框架。 |
| 静态托管 | FastAPI `StaticFiles` | 与接口同源，彻底避免跨域配置。 |

### 1.1 当前实现进度

**阶段 0–4 全部完成**——五个接口落地、五个页面的读写改造全部完成、**没有任何页面再使用 localStorage**；只剩阶段 5（README、手工回归、重新打包 exe）：

| 部分 | 状态 |
| --- | --- |
| `frontend/` 5 个页面 + `css/visual-theme.css` + 7 个 js | **结构已就位**：一页一 html、一页一 js、主题单份；HTML 中无内联 `<style>` 与内联脚本 |
| `index.html` + `js/index.js` | **已实现**：列表由 `GET /api/items/home` 驱动 |
| `detail.html` + `js/detail.js` | **已实现**（读：阶段 3；写：阶段 4）：读走 `GET /api/items/{id}`（404 回落 1 号），标记已解决走 `POST /api/items/{id}/resolve`。内嵌演示数据、`?id=new`、`campusResolved` 全部删除 |
| `search.html` + `js/search.js` | **已实现**：数据来自 `GET /api/items/search`（阶段 3）。8 张硬编码卡片、前端关键词匹配、`insertLocalPost`、`applyResolved` 全部删除；卡片改由 `renderCard(item, 'search')` 渲染，条数与空状态由服务端 `count` 决定 |
| `publish.html` + `js/publish.js` | **已实现**（阶段 4）：提交走 `POST /api/items`，成功后带新 id 跳到成功页；删掉了本地暂存与前端算的发布时间 |
| `success.html` + `js/success.js` | **已实现**（阶段 4）：按 `?id` 从 `GET /api/items/{id}` 取摘要，「查看详情」按真实 id 动态设置；无 `?id` 或查询失败时用写死的兜底摘要 |
| 后端 `db.py` / `schemas.py` / `serialize.py` / `seed.py` / `main.py` | **已实现**：建表、播种、序列化、首页接口 |
| `GET /api/items/home`、`GET /api/items/search`、`GET /api/items/{id}` | **已实现**：三个读接口全部可用 |
| `POST /api/items`、`POST /api/items/{id}/resolve` | **已实现**（阶段 4 的后端部分）：五个接口全部落地，不再有占位路由 |
| `tests/unit` · `tests/integration` · `tests/contract` | **已实现**，三层齐备 |

改造前的 5 个页面源文件已全部迁入 `frontend/` 并删除，不再有"内容只存在于未跟踪文件里"的风险。

> **一处刻意的行为保留**：发布页的提示条原本是 2000ms，其余页是 1800ms。提取共用 `showToast` 时用一个可选时长参数保留了这一差异，避免"整理代码顺手改了行为"。

## 2. 总体架构

```
                        ┌─────────────────────────────────────┐
                        │            浏览器                   │
                        │  index.html / search.html /         │
                        │  detail.html / publish.html /       │
                        │  success.html  （各自独立页面）      │
                        │                                     │
                        │  css/visual-theme.css —— 唯一主题   │
                        │  js/api.js   —— 请求封装            │
                        │  js/common.js —— 共用渲染工具        │
                        │  js/<页面>.js —— 页面逻辑            │
                        └──────────┬──────────────────────────┘
                                   │
               ① 页面请求（HTML/JS）       ② 数据请求（fetch /api/...）
                                   │
                                   ▼
                        ┌─────────────────────────────────────┐
                        │           FastAPI 应用               │
                        │                                     │
                        │  /api/*  路由（先注册）              │
                        │    ├─ 列表 / 搜索 / 详情  （读）      │
                        │    └─ 发布 / 标记已解决   （写）      │
                        │                                     │
                        │  StaticFiles(frontend/) 挂载在 /     │
                        │                        （后注册）    │
                        └──────────┬──────────────────────────┘
                                   │  sqlite3
                                   ▼
                        ┌─────────────────────────────────────┐
                        │        SQLite: db.sqlite3            │
                        │           items 表                   │
                        └─────────────────────────────────────┘
```

**关键点**：

- **同源部署**：接口在 `/api/*`，页面在 `/`，因此浏览器发出的是同源请求，不需要 CORS 中间件、不产生预检请求。
- **路由注册顺序**：`StaticFiles` 挂载在 `/` 是一个兜底匹配，所以**所有 `/api` 路由必须先注册**，静态挂载放在最后。
- **无服务端渲染**：后端只返回 JSON，页面骨架由静态 HTML 提供，数据由前端 js 填入。

## 3. 目录结构

```
campus-lost-found/
├── frontend/                        前端（静态资源，一页一文件平铺）
│   ├── index.html                   首页（由 home.html 改名，兼作站点入口）
│   ├── search.html                  搜索结果页
│   ├── detail.html                  信息详情页
│   ├── publish.html                 发布信息页
│   ├── success.html                 发布成功页
│   ├── css/
│   │   └── visual-theme.css         唯一主题样式（由 5 份内联副本合并而成）
│   └── js/
│       ├── api.js                   共用：请求封装 + 5 个接口方法
│       ├── common.js                共用：showToast / setTabClass / 类型与状态文案
│       │                                  / 状态配色 / 卡片模板 / 联系方式脱敏
│       ├── index.js                 首页：filterList / goSearch
│       ├── search.js                搜索页：runSearch / setFilter / onSubmitSearch / quickSearch
│       ├── detail.js                详情页：loadItem / render / applyStatus / revealContact / markResolved
│       ├── publish.js               发布页：setType / setCat / clearError / submitForm
│       └── success.js               成功页：fillSummary
├── backend/                         后端
│   ├── __init__.py
│   ├── main.py                      FastAPI 应用、5 个路由、静态挂载
│   ├── db.py                        连接管理 + 建表 DDL + init_db()
│   ├── schemas.py                   Pydantic 请求模型与响应模型
│   ├── serialize.py                 行 → 响应对象；相对时间、脱敏、搜索索引、图标/状态映射
│   ├── seed.py                      幂等写入 8 条演示数据
│   └── __main__.py                  启动入口：确保数据库、起服务、开浏览器（python -m backend）
├── tests/                           测试层（与 frontend / backend / docs 平级）
│   ├── conftest.py                  公共 fixture：临时数据库、TestClient、演示数据、发布请求体
│   ├── unit/
│   │   ├── test_serialize.py        脱敏、时间推导、编号生成、搜索索引拼装
│   │   ├── test_schemas.py          请求模型校验
│   │   └── test_paths.py            数据库/前端资源路径（含"冻结成 exe 后"的分支）
│   ├── integration/
│   │   ├── test_seed.py             建表与播种的幂等性
│   │   ├── test_items_read.py       首页列表、搜索、详情
│   │   ├── test_static_serving.py   页面/主题/脚本能通过 HTTP 取到、旧地址跳转
│   │   └── test_items_write.py      发布、标记已解决（阶段 4）
│   └── contract/
│       ├── test_api_contract.py     接口字段与前端渲染的契约
│       ├── test_frontend_wiring.py  前端静态检查（内联块 / 资源存在 / 迁移进度）
│       └── test_openapi_document.py 接口文档必须与当前接口一致（防过期）
├── .github/
│   └── workflows/
│       └── ci.yml                   持续集成：风格检查 + 三层测试
├── docs/
│   ├── PRD.md                       产品需求文档
│   ├── system-design.md             本文档
│   ├── development-plan.md          开发计划
│   ├── coding-standards.md          代码规范（含测试与文档同步要求）
│   └── openapi.json                 OpenAPI 3.1 接口文档（由代码生成，勿手改）
├── run_server.py                    打包入口（PyInstaller 的起点，只做一层转接）
├── build_exe.py                     打包脚本：一条命令生成根目录的 exe
├── export_openapi.py                导出接口文档：生成 docs/openapi.json
├── campus-lost-found.exe            打包产物（运行时生成，不入库）
├── requirements.txt                 运行期依赖：fastapi、uvicorn
├── requirements-dev.txt             开发与测试依赖：pytest、httpx、ruff、pyinstaller
├── ruff.toml                        代码风格检查配置（PEP 8，规则集 E/F/W/I）
├── README.md                        运行说明
├── db.sqlite3                       运行时生成（已被 .gitignore 忽略）
└── .gitignore / LICENSE
```

**为什么 5 个 HTML 平铺而不建子目录**：页面之间用相对文件名互相跳转（`detail.html?id=N`、`index.html` 等），平铺在同一个静态根目录下，链接无需任何处理即可继续工作。

## 4. 数据库设计

### 4.1 表结构（`items`）

```sql
CREATE TABLE IF NOT EXISTS items (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  name         TEXT    NOT NULL,
  type         TEXT    NOT NULL CHECK (type IN ('seek','find')),
  status       TEXT    NOT NULL CHECK (status IN ('seeking','unclaimed','resolved')),
  category     TEXT    NOT NULL,
  icon         TEXT    NOT NULL,              -- Iconify 图标名，如 mdi:umbrella-outline
  card_desc    TEXT    NOT NULL,              -- 列表/搜索卡片上的短描述
  desc         TEXT    NOT NULL,              -- 详情页的完整描述
  happened_at  TEXT    NOT NULL,              -- 'YYYY-MM-DD HH:mm'，详情页「时间」行
  time_display TEXT,                          -- 卡片时间文案；NULL 时由 happened_at 推导
  place        TEXT    NOT NULL,
  published_at TEXT    NOT NULL,              -- 'YYYY-MM-DD HH:mm'，详情页「发布时间」行
  publisher    TEXT    NOT NULL,              -- 发布者昵称，如「张同学 · 计算机学院」
  avatar       TEXT    NOT NULL,              -- 发布者头像文字，如「张」
  masked       TEXT    NOT NULL,              -- 脱敏联系方式（默认展示）
  contact      TEXT    NOT NULL,              -- 完整联系方式（点击展开后展示）
  keywords     TEXT    NOT NULL,              -- 空格分隔的搜索索引文本
  source       TEXT    NOT NULL DEFAULT 'demo' CHECK (source IN ('demo','user')),
                                              -- 数据来源：演示数据 / 用户新发布
  home_order   INTEGER,                       -- 演示数据在首页的顺序 1~6；不在首页与用户新发布为 NULL
  search_order INTEGER,                       -- 演示数据在搜索页的顺序 1~8；用户新发布为 NULL
  created_at   TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_items_home   ON items(home_order);
CREATE INDEX IF NOT EXISTS idx_items_search ON items(search_order);
```

### 4.2 字段来源与推导规则

这是本设计的核心决策点。**四条数据一律存"字面量"而不是推导**，原因逐条说明：

| 字段 | 演示数据 | 用户新发布数据 | 为什么这样处理 |
| --- | --- | --- | --- |
| `card_desc` | 从 `home.html` / `search.html` 卡片里逐字抄录 | 等于 `desc` | **不可推导**。1 号物品卡片文案是"…昨天下午在图书馆自习时遗落在桌面。"，详情文案是"…昨天下午在图书馆二楼自习时还用过，离开时遗忘在桌面上。…"，二者不是前缀关系。另外已核实首页与搜索页的卡片描述**逐字相同**，所以一列同时服务两处。 |
| `time_display` | 从卡片抄录（`今天 08:20`、`昨天 18:05`、`09-25 12:10`） | `NULL`，读取时推导 | 演示数据的"今天"冻结在虚构的 2026-09-27，而真实日期是 2026-10-07 且会一直变化。若按 `now` 推导，"今天"会立刻变成"09-27"，破坏展示保真。**只有用户新发布的数据**才按当前日期推导，让新数据随时间自然变化。 |
| `keywords` | 从 `search.html` 的 `data-keywords` 抄录 | 按 name + category + place + desc + 类型同义词拼装 | 索引里含名称与描述中都不存在的同义词（如 1 号物品的"蓝色卡套"、4 号物品的"3号楼"），无法从其它字段生成。 |
| `masked` | 从 `detail.html` 抄录 | 由 `contact` 按脱敏规则计算 | **演示数据的脱敏串与联系方式不同源**：1 号物品 `masked = 138****6621`，但 `contact = 微信：zhang_cc2024`；对后者套脱敏规则得到的是 `微信****24`，不是前者。所以必须原值保存。 |

其余字段均为直接映射或简单推导：

| 字段 | 演示数据 | 用户新发布数据 |
| --- | --- | --- |
| `status` | 直接抄录 | 寻物 → `seeking`；招领 → `unclaimed` |
| `icon` | 直接抄录 | 寻物 → `mdi:help-circle-outline`；招领 → `mdi:hand-heart-outline`（与原前端合成逻辑一致） |
| `publisher` | 直接抄录，如"张同学 · 计算机学院" | 固定为"我（本机发布）" |
| `avatar` | 直接抄录，如"张" | 固定为"我" |
| `published_at` | 直接抄录 | 服务端当前时间 |
| `home_order` / `search_order` | 1~6 / 1~8 | `NULL`（排序时置顶） |
| `source` | `'demo'` | `'user'` |
| 物品编号 | 读取时生成，不落库 | 同左 |

> **为什么需要 `source`**：7、8 两条演示数据**只出现在搜索页与详情页，不在首页**（这是现状），
> 所以它们的 `home_order` 也是 `NULL` —— 与"用户新发布"的 `NULL` 语义撞车，
> 光靠 `home_order` 无法区分"不在首页的演示数据"和"新发布的数据"。
> 用一个显式的来源列把两者分开，排序规则才能写成一条没有歧义的 SQL。

### 4.3 排序策略

```sql
-- 首页列表
WHERE (:type = 'all' OR type = :type)
  AND (source = 'user' OR home_order IS NOT NULL)
ORDER BY (source = 'user') DESC, home_order ASC, id DESC

-- 搜索结果
WHERE (:type = 'all' OR type = :type)
  AND (:q = '' OR instr(lower(keywords), lower(:q)) > 0)
ORDER BY (source = 'user') DESC, search_order ASC, id DESC
```

- `AND (source = 'user' OR home_order IS NOT NULL)`（仅首页）：排除掉"不在首页的演示数据"（7、8 号），但保留用户新发布的数据。
- `(source = 'user') DESC`：把用户新发布的数据排到最前，满足"新发布信息可见"的需求。
- `home_order ASC` / `search_order ASC`：演示数据保持现有展示顺序（首页 1~6；搜索页 1、7、5、3、2、4、6、8）。
- `id DESC`：兜底排序。同一分钟内连续发布多条时，按 id 倒序保证顺序稳定且"最新的在最前"。

### 4.4 演示数据映射表

固定 id 1~8。`card_desc` / `desc` / `publisher` / `masked` / `contact` / `avatar` / `icon` 等长文本以源码为权威来源，不在此表中转抄以免出错：

- `card_desc`（1~6）来源 `home.html` 各卡片的 `line-clamp-2` 段落；`card_desc`（7、8）来源 `search.html`（两者对 1~6 已核实逐字相同）
- `desc` / `publisher` / `masked` / `contact` / `avatar` / `icon` / `status`：`detail.html` 的 `ITEMS` 对象
- `keywords`：`search.html` 各卡片的 `data-keywords`

结构性字段如下：

| id | name | type | status | category | icon | happened_at | time_display | place | published_at | avatar | home_order | search_order |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 校园卡 | seek | seeking | 证件卡片 | mdi:card-account-details-outline | 2026-09-27 08:20 | 今天 08:20 | 图书馆二楼自习区 | 2026-09-27 08:26 | 张 | 1 | 1 |
| 2 | 黑色雨伞 | find | unclaimed | 雨伞 | mdi:umbrella-outline | 2026-09-27 09:40 | 今天 09:40 | 教学楼A座 201 | 2026-09-27 09:52 | 李 | 2 | 5 |
| 3 | 白色保温杯 | find | unclaimed | 水杯 | mdi:cup-outline | 2026-09-26 18:05 | 昨天 18:05 | 第二食堂一楼 | 2026-09-26 18:20 | 王 | 3 | 4 |
| 4 | 无线耳机 | seek | resolved | 电子产品 | mdi:headphones | 2026-09-26 15:30 | 昨天 15:30 | 宿舍区 3 号楼 | 2026-09-26 15:48 | 陈 | 4 | 6 |
| 5 | 宿舍钥匙 | seek | seeking | 钥匙 | mdi:key-variant | 2026-09-25 12:10 | 09-25 12:10 | 体育馆篮球场 | 2026-09-25 12:35 | 刘 | 5 | 3 |
| 6 | 帆布笔袋 | find | unclaimed | 书籍文具 | mdi:bag-personal-outline | 2026-09-24 20:15 | 09-24 20:15 | 图书馆四楼阅览室 | 2026-09-24 20:31 | 赵 | 6 | 7 |
| 7 | 校园卡 | find | unclaimed | 证件卡片 | mdi:card-account-details-outline | 2026-09-27 10:15 | 今天 10:15 | 第三教学楼 B202 | 2026-09-27 10:22 | 李 | NULL | 2 |
| 8 | 学生证 | find | unclaimed | 证件卡片 | mdi:badge-account-horizontal-outline | 2026-09-23 16:40 | 09-23 16:40 | 大学生活动中心 | 2026-09-23 16:55 | 赵 | NULL | 8 |

> 注意 7、8 两条只出现在搜索页与详情页，不在首页「最新信息」里——这是现状。它们的 `home_order` 为 `NULL`、`search_order` 有值，首页查询靠 `home_order IS NOT NULL` 把它们排除（详见 4.3）。

### 4.5 读取时的派生字段

| 派生字段 | 规则 |
| --- | --- |
| `code`（物品编号） | `'LF-' + str(id).zfill(3)` → `LF-001` … `LF-009` |
| `timeLabel`（时间行标题） | 寻物 → `丢失时间`；招领 → `拾取时间` |
| 卡片时间 `time` | `time_display` 非空则直接用；否则由 `happened_at` 推导：当天 → `今天 HH:mm`，前一天 → `昨天 HH:mm`，其余 → `MM-DD HH:mm` |

## 5. 接口设计

所有接口统一前缀 `/api`，请求与响应均为 JSON。

### 5.0 接口文档（`docs/openapi.json`）

本节表格是**给人看的设计说明**；机器可读的权威版本是从代码生成的 OpenAPI 3.1 文档：

```bash
.venv/Scripts/python.exe export_openapi.py     # 重新生成 docs/openapi.json
```

- 服务运行时会挂在 **`/openapi.json`**，交互式页面在 **`/docs`**（FastAPI 自带）。
- `docs/openapi.json` 是**产物，不要手改**——接口说明取自代码里的 docstring，
  参数说明取自 `Query(...)` / `Path(...)`，模型取自 `schemas.py`。要改文档就改代码再导出。
- **防过期**：`tests/contract/test_openapi_document.py` 会把它与 `app.openapi()`
  现场生成的做全量比对，改了接口忘了导出，CI 直接失败。
- 每个业务接口都显式写了中文 `summary`——FastAPI 默认拿函数名当 summary，
  不写会得到 `List Home` 这种英文标签，夹在一堆中文说明里很突兀。

**响应对象**：

```
ListItem（列表项，用于首页与搜索）
{ id, name, type, status, icon, desc, time, place, keywords }

DetailItem（详情项，用于详情、发布返回、标记已解决返回）
{ id, code, name, type, status, icon, category, timeLabel, time, place,
  publish, desc, publisher, avatar, masked, contact }
```

### 5.1 首页列表

```
GET /api/items/home?type=all|seek|find        # type 默认 all
```

响应：

```json
{
  "count": 6,
  "items": [
    { "id": 1, "name": "校园卡", "type": "seek", "status": "seeking",
      "icon": "mdi:card-account-details-outline",
      "desc": "蓝色卡套，卡面右下角贴有姓名贴，昨天下午在图书馆自习时遗落在桌面。",
      "time": "今天 08:20", "place": "图书馆二楼自习区" }
  ]
}
```

- 首页只展示**演示数据中 `home_order` 非空的部分（6 条）**加上**全部用户新发布数据**。
- 排序按 4.3。
- `count` 为当前筛选条件下的真实条数，供页面显示"共 N 条"。

### 5.2 搜索

```
GET /api/items/search?q=<关键词>&type=all|seek|find    # q 默认空串，type 默认 all
```

匹配规则（复刻原前端语义）：

```sql
(:q = '' OR instr(lower(keywords), lower(:q)) > 0)
AND (:type = 'all' OR type = :type)
```

即对搜索索引文本做**不区分大小写的子串匹配**，与原来 `data-keywords.toLowerCase().indexOf(keyword) !== -1` 等价。

- 返回**演示数据中 `search_order` 非空的部分（8 条）**加上全部用户新发布数据，按 4.3 排序。
- 关键词为空时返回全部（对应原前端清空输入后展示 8 条的行为）。

### 5.3 详情

```
GET /api/items/{id}
```

- 200：返回 `DetailItem`。
- 404：id 不存在，返回 `{"code": "not_found", "message": "物品不存在"}`。前端收到 404 时回落到 id=1（沿用现状容错）。

### 5.4 发布

```
POST /api/items
Content-Type: application/json

{ "name": "…", "type": "seek|find", "category": "…",
  "time": "2026-10-07 14:30", "place": "…", "desc": "…", "contact": "…" }
```

- 201：返回完整 `DetailItem`（含新 id 与编号）。
- 422 / 400：字段校验失败（错误体形状见下方说明）。

后端在落库前补全前端没有提供的字段：

| 补全字段 | 规则 |
| --- | --- |
| `status` | 寻物 → `seeking`；招领 → `unclaimed` |
| `icon` | 寻物 → `mdi:help-circle-outline`；招领 → `mdi:hand-heart-outline` |
| `card_desc` | 取 `desc` |
| `time_display` | `NULL`（读取时推导） |
| `published_at` | 服务端当前时间 |
| `publisher` / `avatar` | `我（本机发布）` / `我` |
| `masked` | 按 5.6 的规则由 `contact` 计算 |
| `keywords` | `name + category + place + desc + ("寻物 丢了" | "招领 捡到")` |
| `source` | `'user'`——排序时据此把新发布的排在演示数据之前 |
| `home_order` / `search_order` | `NULL`（排序时置顶） |

> **关于 422**：字段校验失败返回的是 FastAPI/Pydantic 的**原生形状** `{"detail": [...]}`，
> 与业务错误（404 等）的 `{"code": ..., "message": ...}` 不是一套。这是有意的——前端本地
> 校验会先拦一道，真出现 422 说明有人在绕过前端直接调接口，那种报文给开发者看更合适。
> 契约测试 `test_错误体形状是_code_message` 只断言 404 那一类，不要顺手把 422 也塞进去。

### 5.5 标记已解决

```
POST /api/items/{id}/resolve
```

- 200：返回更新后的 `DetailItem`（`status` 为 `resolved`）。
- 404：id 不存在。
- 幂等：对已解决的物品重复调用不报错，仍返回 `resolved` 状态。

### 5.6 联系方式脱敏规则（服务端）

| 输入 | 输出 |
| --- | --- |
| 匹配 `^1\d{10}$` | 前 3 位 + `****` + 后 4 位 |
| 长度 > 4 | 前 2 位 + `****` + 后 2 位 |
| 长度 ≤ 4 或空 | 原样 / `—` |

### 5.7 接口总表

| # | 方法 | 路径 | 请求 | 成功响应 | 失败 |
| --- | --- | --- | --- | --- | --- |
| 1 | GET | `/api/items/home` | `type` | 200 `{count, items[]}` | — |
| 2 | GET | `/api/items/search` | `q`, `type` | 200 `{count, items[]}` | — |
| 3 | GET | `/api/items/{id}` | — | 200 `DetailItem` | 404 |
| 4 | POST | `/api/items` | 表单 JSON | 201 `DetailItem` | 422 / 400 |
| 5 | POST | `/api/items/{id}/resolve` | — | 200 `DetailItem` | 404 |

**实现注意**：接口 1、2 的路径段是字面量 `home`、`search`，必须注册在接口 3 的 `/{id}` 之前，否则会被 `{id}` 捕获并因整型转换失败而返回 422。

**旧地址兼容**：

```
GET /home.html  →  302  /index.html
```

该路由同样必须注册在静态挂载之前。

## 6. 关键流程时序

### 6.1 列表 / 搜索流程

```
浏览器           index.js / search.js        FastAPI              SQLite
  │                     │                       │                    │
  │ 打开页面             │                       │                    │
  ├────────────────────►│                       │                    │
  │                     │ GET /api/items/home   │                    │
  │                     ├──────────────────────►│                    │
  │                     │                       │ SELECT … ORDER BY  │
  │                     │                       ├───────────────────►│
  │                     │                       │◄───────────────────┤
  │                     │◄──────────────────────┤                    │
  │                     │ 200 {count, items[]}  │                    │
  │  渲染卡片 + 计数      │                       │                    │
  │◄────────────────────┤                       │                    │
  │                     │                       │                    │
  │ 点击「寻物」标签      │                       │                    │
  ├────────────────────►│                       │                    │
  │                     │ GET /api/items/home?type=seek              │
  │                     ├──────────────────────►│   （同上）          │
  │◄────────────────────┤                       │                    │
```

要点：分类切换**重新请求后端**，不再依赖 DOM 上的 `data-*` 属性做前端过滤。

### 6.2 发布流程

```
publish.html      publish.js          FastAPI             SQLite      success.html    success.js
     │                 │                  │                  │             │              │
     │ 点击「发布信息」 │                  │                  │             │              │
     ├────────────────►│                  │                  │             │              │
     │                 │ 本地校验（6 项非空）                  │             │              │
     │  校验失败 → 标红 + 提示 + 滚动回第一个错误字段           │             │              │
     │◄────────────────┤                  │                  │             │              │
     │                 │ POST /api/items  │                  │             │              │
     │                 ├─────────────────►│                  │             │              │
     │                 │                  │ 补全字段 + INSERT │             │              │
     │                 │                  ├─────────────────►│             │              │
     │                 │                  │◄─────────────────┤             │              │
     │                 │◄─────────────────┤ 201 DetailItem   │             │              │
     │                 │ 跳转 success.html?id=<新id>          │             │              │
     │                 ├──────────────────────────────────────────────────►│              │
     │                 │                  │                  │   GET /api/items/{id}      │
     │                 │                  │◄───────────────────────────────┤              │
     │                 │                  ├─────────────────►│             │              │
     │                 │                  │◄─────────────────┤             │              │
     │                 │                  ├───────────────────────────────►│ 渲染摘要      │
     │                 │                  │                  │  点击「查看详情」           │
     │                 │                  │                  │  跳转 detail.html?id=<新id>│
```

### 6.3 标记已解决流程

```
detail.html      detail.js          FastAPI             SQLite
     │                │                 │                  │
     │ 点击「标记为已找回」               │                  │
     ├───────────────►│                 │                  │
     │                │ POST /api/items/{id}/resolve       │
     │                ├────────────────►│                  │
     │                │                 │ UPDATE … SET status='resolved'
     │                │                 ├─────────────────►│
     │                │                 │◄─────────────────┤
     │                │◄────────────────┤ 200 DetailItem   │
     │ 重新渲染：标签变绿、按钮禁用、弹出提示                  │
     │◄───────────────┤                 │                  │
     │                │                 │                  │
     │ 刷新页面 → GET /api/items/{id} → 状态仍为已解决（持久化）│
     │ 换浏览器打开 → 同样是已解决（全局状态）                │
```

## 7. 前端改造说明

### 7.1 HTML / CSS / JS 分离方案

**要求**：每个页面保持独立 `.html`；主题样式收敛为**一份**共用文件；每页一个同名 js 文件；HTML 内不再有内联 `<style>` 主题块与内联脚本逻辑。

#### 7.1.1 主题样式抽取

现行版本把整套主题复制在 5 个文件的 `<style>` 块里（各约 127 行，字节相同），另有一份未被引用的 `visual-theme.css`。改造后：

- 主题样式合并为 `frontend/css/visual-theme.css`，**以各页内联版为准**（内联版是实际生效的那份）。
- 5 个文件删除内联 `<style>` 块，各加一行 `<link rel="stylesheet" href="css/visual-theme.css">`。
- 内联版开头那两行（旧的 `body{font-family}` 与响应式 `#phone-canvas` 尺寸）属于基础布局，一并并入主题文件，保持生效顺序不变。
- 两个 CDN 脚本（Tailwind 运行时、Iconify）保留在 `<head>`，**必须在主题文件之前或之后保持与今天相同的层叠关系**：主题里的 Tailwind 类覆盖规则依赖 Tailwind 基础类已存在，但因为是 `.bg-blue-600 { … }` 这类**覆盖**写法且带 `!important`，实际不依赖加载顺序。抽取后逐页截图比对确认。

**为什么值得做**：主题含 12 个 CSS 变量、约 25 组 Tailwind 类覆盖、卡片/按钮/输入框/hero 等组件规则；现在改一处配色要改五遍，且已经出现"内联版与 `visual-theme.css` 尺寸写法不一致"的分叉（`393px/852px` + `flex: 0 1 393px` vs `min(393px,100vw,…)` + `flex: 0 0 auto`）。

#### 7.1.2 脚本引入

```
每个页面底部（顺序固定，共用在前、页面自身在后）：
  <script src="js/api.js"></script>
  <script src="js/common.js"></script>
  <script src="js/<本页>.js"></script>
```

| 文件 | 职责 | 内容 |
| --- | --- | --- |
| `js/api.js` | **唯一**的 HTTP 出口 | `request()` 统一处理非 2xx 与错误信息；暴露 `API.home(type)`、`API.search(q, type)`、`API.detail(id)`、`API.create(payload)`、`API.resolve(id)` |
| `js/common.js` | 跨页共用的展示层工具 | `TAB_ON` / `TAB_OFF` / `setTabClass`、`showToast`、`TYPE_TEXT`（寻物/招领）、`STATUS_TEXT`（寻找中/待认领/已解决）、`STATUS_CLASS`（三态配色）、`renderCard`（列表卡片模板）、`maskContact`（仅成功页兜底用） |
| `js/<页面>.js` | 单页业务逻辑 | 见下表 |

**约束（重要）**：

- 页面中现有的行内事件属性（`onclick="filterList('all')"`、`onclick="setType('seek')"`、`onsubmit="return goSearch(event)"` 等）**保持不变**，因此各页 js 里的被调用函数必须是**全局函数声明**（`function foo() {}`），**不能**包进立即执行函数，也**不能**使用 `type="module"` —— 模块作用域下 `window.filterList` 不存在，所有行内事件会集体失效。
- 保留原有的两个 CDN `<script>`（Tailwind 运行时、Iconify 组件），它们是页面样式的来源。
- 原有 3 行 `<style>`（字体）与全部页面结构不动。
- 脚本标签位于 `</body>` 之前，与原内联脚本位置等价，DOM 此时已就绪。

### 7.2 逐页改造

> **阅读提示**：阶段 0 的机械拆分**已经完成**——四页的"删除内联 `<style>` / 删除整块内联 `<script>` / 提取共用代码"这几行现在都已是既成事实。下表保留它们是为了说明最终形态，**剩下要做的是逻辑替换**（把内嵌数据、localStorage、`?id=new` 换成接口调用），不是再次做结构拆分。



#### 首页 `index.html`（原 `home.html`）

| 动作 | 内容 |
| --- | --- |
| 删除 | `#list`（**181–329 行**）内 6 张静态卡片；`getResolvedIds`（379–385）、`applyResolved`（387–397）及其 `localStorage` 调用；**`insertLocalPost`（413–432）**——这是本版新增的"读 `localStorage` 往列表顶部插卡片"逻辑，必须删掉，否则同一件物品会出现两张卡片；`escapeHtml`（407–411，仅被 `insertLocalPost` 使用）；整块内联 `<script>`（约 344–439 行）与内联 `<style>`（10–136 行） |
| 改写 | `filterList(type)`（355–366）：设置标签样式 → 调 `API.home(type)` → 用 `renderCard` 渲染 → `#listCount` 取 `res.count`。函数名与 `onclick="filterList('all')"` 不变 |
| 保留 | `goSearch(e)`（368–377，跳转逻辑完全不变）、`setTabClass`（移到 common.js）、页面全部结构、DOM id（`#kw`、`#list`、`#listCount`、`#toast`）、按钮上的 `data-tab`、搜索表单与 `#toast`（151–157、341） |
| 新增 | `js/index.js`；`</body>` 前引入三个脚本；`<head>` 中引入主题样式文件 |

#### 搜索页 `search.html`

| 动作 | 内容 |
| --- | --- |
| 删除 | `#resultList` 内 8 张静态卡片（**170–352 行**）；`getResolvedIds`（388–394）、`applyResolved`（396–405）；**`insertLocalPost`（413–431）**与 `escapeHtml`（407–411）；整块内联 `<script>` 与内联 `<style>` |
| 改写 | `runSearch()`（433–451）：调 `API.search(kw, currentType)` → 渲染 → `#resultCount` 取 `res.count` → 按 `count === 0` 切换 `#resultList` / `#emptyState` |
| 保留 | `currentType`、`setFilter`（453–459）、`onSubmitSearch`（461–469）、`quickSearch`（471–474）的函数名与行为；`#kw` 的默认值 `校园卡`（149 行）；`#kwEcho` 仍由前端回显 `kw \|\| '全部物品'`；空状态与快捷标签结构（356–371） |
| 注意 | 本页**没有 toast 元素**（与首页不同），失败提示如需展示，沿用页面已有的空状态/计数变化，或不做视觉反馈（详细见 7.3 坑 3） |
| 明确不做 | 输入即时搜索（会改变现有交互） |

#### 详情页 `detail.html`

| 动作 | 内容 |
| --- | --- |
| 删除 | `ITEMS` 对象（**243–301 行**，8 条记录）、`buildNewItem`（335–353）、`getResolvedIds`（314–320） / `saveResolvedIds`（322–326）、本地 `maskContact`（328–333）、`loadItem` 里的 `id === 'new'` 分支（416–427）、整块内联 `<script>`（242–466）与内联 `<style>` |
| 改写 | `loadItem()`（411–438）：取 `?id` → `API.detail(id)`；404 或参数缺失时回落到 id=1。`markResolved()`（446–453）：`await API.resolve(currentId)` 后用返回数据重新渲染 |
| 保留 | `render(it)`（374–409）的全部 DOM 赋值、`applyStatus`（355–372）、`revealContact`（440–444，展开独立面板 + 隐藏按钮的行为）；`STATUS_TEXT` / `STATUS_STYLE`（303–308，详情页的状态标签是 `px-2 py-0.5 rounded-full` 变体，与卡片不同，需保留自己的模板）；全部 DOM id：`#dCode #dName #dType #dIcon #dIconBox #dPublish #dPublishRow #dCategory #dTimeLabel #dTime #dPlace #dDesc #dAvatar #dPublisher #dContactMask #dContactFull #dContactRevealed #dContactBtnWrap #dStatus #dResolveBtn #dResolveText #toast` |
| 变化 | `#dCode` 改用服务端返回的编号（原来在 402 行拼 `LF-NEW` / `'LF-00' + id`），不再有 `LF-NEW` 分支；`render` 每次加载都重置联系方式面板的展开状态（404–405），改造后保持这一行为 |

#### 发布页 `publish.html`

| 动作 | 内容 |
| --- | --- |
| 保留 | **全部校验逻辑逐字保留**：`submitForm`（295–343）里 6 字段去空格判空、6 条错误文案、`border-rose-400` / `border-slate-200` 边框切换、统一提示"请完善标红的必填项"（321 行）、`scrollIntoView({behavior:'smooth',block:'center'})`、`setType`（248–261） / `setCat`（约 263–271） / `clearError`（273–280）；页面结构与全部字段 id：`#fName #fCategory #fTime #fPlace #fDesc #fContact #catWrap #timeLabel #placeLabel #eName #eCategory #eTime #ePlace #eDesc #eContact #toast` |
| 改写 | `submitForm()` 的成功分支改为 `API.create(payload)` → 成功后跳 `success.html?id=<新id>`（原来在 342 行跳 `success.html`，无参数） |
| 删除 | `localStorage.setItem('campusNewItem', …)`（338 行）、`formatDateTime`（290–293，发布时间改由服务端生成）、"本地存储不可用"的 toast 分支（339–341）、整块内联 `<script>`（240–348）与内联 `<style>` |
| 新增 | 失败分支提示"发布失败，请稍后重试"（现行版本没有网络失败路径） |

#### 成功页 `success.html`

| 动作 | 内容 |
| --- | --- |
| 改写 | `fillSummary()`（219–249）：读 `?id` → `API.detail(id)` 渲染摘要（联系方式用服务端返回的脱敏值）；无参数或请求失败时使用现有固定兜底数据（227–234 行） |
| 改写 | "查看详情"链接（198 行，现为固定 `detail.html?id=new`）改为动态：`detail.html?id=<真实id>`（该元素加 `id="sDetailLink"`） |
| 保留 | 「返回首页」链接（201 行 → `home.html`）、`#sName #sType #sTimeLabel #sTime #sPlace #sContact #sPublish` 全部 id 与兜底值、`showToast` 之外的页面结构 |
| 删除 | 本地重复的 `maskContact`（212–217）、整块内联 `<script>`（211–252）与内联 `<style>` |

### 7.3 三个必须注意的坑

**坑 1：`data-*` 不能再作为筛选依据，但必须继续输出——它现在是主题样式的选择器钩子。**

主题 CSS 里的卡片规则是：

```css
#list > a, #resultList [data-result] { border-left: 3px solid #d9a75c; border-radius: 14px; background: #fffdf8; … }
```

也就是说，**搜索页卡片的左侧金线、圆角与纸白底色，是靠 `data-result` 属性选中的**。列表改为按数据渲染后：

- 筛选一律改为请求后端（前端不再读 `data-keywords` 做匹配），代码里**不能再保留基于这些属性的匹配逻辑**，否则会出现"标签切换了但列表没变"或重复渲染。
- 但渲染出来的卡片**必须原样带上** `data-id`、首页的 `data-card`、搜索页的 `data-keywords` / `data-result`。**漏掉 `data-result` 不会报错**，只会让搜索结果卡片悄悄失去主题样式（变白、失去左侧金线），属于最难排查的一类回归。

**坑 2：首页卡片必须仍是 `#list` 的**直接子 `<a>`**。**

主题用 `#list > a` 这个**子选择器**选中首页卡片。如果渲染时把卡片包进额外的 `<div>`（例如为了分组或做虚拟列表），选择器不再匹配，卡片样式同样静默失效。搜索页的容器结构（`#resultList` 内的 flex 列）保持现状即可。

**坑 3：隐藏的"动态样式占位" div 必须扩充。**

页面通过 CDN 的 Tailwind 运行时按源码生成样式类，而卡片样式类原本是靠静态卡片出现在源码里才被生成的。删掉静态卡片后这些类会从文件中消失，**必须在各页的隐藏占位 div 中补齐完整卡片模板的样式类**，尤其是 `opacity-80`（**当前全项目 5 个占位 div 里没有任何一个包含它**，而已解决卡片要靠它弱化）。

各页占位 div 的准确位置（新版行号）：

| 文件 | 行号 | 现有 class 列表 | 是否含 `opacity-80` |
| --- | --- | --- | --- |
| `index.html` | 343 | `bg-slate-100 text-slate-500 bg-orange-50 text-orange-600 bg-amber-50 text-amber-600 bg-emerald-50 text-emerald-600 bg-blue-50 text-blue-600` | ✗ 需补 |
| `search.html` | 376 | 同首页 | ✗ 需补 |
| `detail.html` | 240 | `bg-emerald-50 text-emerald-600 bg-amber-50 text-amber-600 bg-slate-100 text-slate-400 border-blue-200 border-slate-200` | — （无卡片模板，无需补） |
| `publish.html` | 238 | `border-blue-600 bg-blue-50 text-blue-600 border-slate-200 bg-white text-slate-600 border-rose-400` | — （同上） |
| `success.html` | 209 | `bg-emerald-50 text-emerald-600 bg-blue-50 text-blue-600` | — （同上） |

首页与搜索页还需要补上卡片模板自身的类（`rounded-2xl bg-white p-4 border border-slate-100 shadow-sm transition active:scale-[0.99] flex items-start gap-3 w-11 h-11 shrink-0 rounded-xl flex items-center justify-center text-[22px] text-blue-600 text-emerald-600 min-w-0 flex-1 truncate ml-auto mt-1.5 … line-clamp-2` 等），因为这些都是随静态卡片一起被删掉的。

### 7.4 卡片模板（`renderCard`）

卡片标记与现有静态卡片逐字一致：

```
<a class="rounded-2xl bg-white p-4 border border-slate-100 shadow-sm transition active:scale-[0.99]"
   data-id="{id}" data-card="{type}" href="detail.html?id={id}">
                                     ↑ 已解决时追加 opacity-80
  <div class="flex items-start gap-3">
    <div class="w-11 h-11 shrink-0 rounded-xl {bg-blue-50 | bg-emerald-50} flex items-center justify-center">
      <iconify-icon class="text-[22px] {text-blue-600 | text-emerald-600}" icon="{icon}"></iconify-icon>
    </div>
    <div class="min-w-0 flex-1">
      <div class="flex items-center gap-1.5">
        <h3 class="min-w-0 text-[15px] font-semibold text-slate-800 truncate">{name}</h3>
        <span class="shrink-0 px-1.5 py-0.5 rounded text-[10px] font-medium {类型配色}">{寻物|招领}</span>
        <span class="ml-auto shrink-0 px-1.5 py-0.5 rounded text-[10px] font-medium {状态配色}">{状态文案}</span>
      </div>
      <div class="mt-1.5 flex items-center gap-3 text-[11px] text-slate-400">
        <span class="shrink-0 flex items-center gap-0.5">
          <iconify-icon class="text-[13px]" icon="mdi:clock-outline"></iconify-icon>{time}</span>
        <span class="flex items-center gap-0.5 min-w-0">
          <iconify-icon class="text-[13px] shrink-0" icon="mdi:map-marker-outline"></iconify-icon>
          <span class="truncate">{place}</span></span>
      </div>
      <p class="mt-1.5 text-[12px] leading-relaxed text-slate-500 line-clamp-2">{desc}</p>
    </div>
  </div>
</a>
```

**模板必须按页面输出不同的属性**（这是 7.3 坑 1 的落地要求）：

| 页面 | 卡片必须带 | 容器要求 |
| --- | --- | --- |
| 首页 | `data-id`、`data-card`（值为 `seek`/`find`）、`href` | 卡片必须是 `#list` 的**直接子** `<a>` |
| 搜索页 | `data-id`、`data-result`（值为 `seek`/`find`）、`data-keywords`（索引文本）、`href` | 放在 `#resultList` 内的 flex 列里，与今天结构一致 |

`data-keywords` 的值由后端返回（每个列表项都带索引文本），前端只负责原样写出——它不再参与前端匹配，但保留它既维持 DOM 结构一致，也让主题之外任何基于该属性的行为不受影响。

**类名与最终颜色**：下表列出的是 Tailwind **类名**。主题文件会把它们**重映射**到「校园档案」配色（例如 `.bg-blue-600` → 朱砂橙 `#e86143`、`.bg-emerald-50` → 鼠尾草绿 `#e8f0e8`、`.bg-white` → `#fffdf8`），因此 HTML 里写的是蓝色系类名，渲染出来是墨绿 / 朱砂橙系。改造时**沿用现有类名即可**，不要"顺手改成"新配色的字面类名，否则主题的覆盖规则会失配。

配色映射（类名层面）：

| 元素 | 寻物 | 招领 |
| --- | --- | --- |
| 图标底色 / 颜色 | `bg-blue-50` / `text-blue-600` | `bg-emerald-50` / `text-emerald-600` |
| 类型标签 | `bg-blue-50 text-blue-600` | `bg-emerald-50 text-emerald-600` |

| 状态 | 文案 | 类型标签配色 |
| --- | --- | --- |
| `seeking` | 寻找中 | `bg-orange-50 text-orange-600` |
| `unclaimed` | 待认领 | `bg-amber-50 text-amber-600` |
| `resolved` | 已解决 | `bg-emerald-50 text-emerald-600`（卡片整体加 `opacity-80`） |

## 8. 数据流对比

| 环节 | 改造前 | 改造后 |
| --- | --- | --- |
| 列表数据来源 | HTML 里写死的 static 标签 | `GET /api/items/home` |
| 搜索 | 前端对 `data-keywords` 做子串匹配 | `GET /api/items/search`，服务端 `instr(lower(keywords), lower(q))` |
| 分类筛选 | 前端切 `hidden` 类 | 请求参数 `type`，服务端过滤 |
| 详情数据 | 页面内嵌 `ITEMS` 对象 | `GET /api/items/{id}` |
| 新发布信息 | 写入 `localStorage.campusNewItem` | `POST /api/items`，落库并返回 |
| 发布成功页数据 | 从 `localStorage` 读取 | `GET /api/items/{id}`（带 `?id`），失败时用固定兜底 |
| 状态（已解决） | `localStorage.campusResolved`（每浏览器一份） | `items.status` 字段（全局一份），`POST /api/items/{id}/resolve` 更新 |
| 联系方式脱敏 | 各页各自实现 `maskContact` | 服务端计算并随 `masked` 返回 |
| 物品编号 | 演示数据在前端拼 `LF-00N`，新数据固定 `LF-NEW` | 服务端统一 `LF-{id:03d}` |
| 发布时间 | 前端 `new Date()` 格式化 | 服务端写入 `published_at` |
| 计数显示 | 前端累加可见卡片数 | 接口返回的 `count` |
| 页面脚本 | 每页内联 `<script>` | 每页独立 `js/<页面>.js` + 共用 `api.js` / `common.js` |
| 主题样式 | 5 份字节相同的内联 `<style>` 副本，另有一份未被引用的 `visual-theme.css` | 单份 `css/visual-theme.css`，各页 `<link>` 引用（渲染结果不变） |
| 本机发布的展示 | 首页/搜索靠 `insertLocalPost` 读 `localStorage` 在**本机**列表顶部插一张卡片（边框色还与他人不同，为 `border-blue-100`） | 后端返回的数据直接渲染，与其它卡片同一模板、同一来源 |

## 9. 初始化与演示数据种子

`backend/seed.py` 负责建表与写入演示数据：

1. 调用 `init_db()` 创建表与索引。
2. 以**固定 id 1~8** 执行 `INSERT INTO items (id, …) VALUES (…) ON CONFLICT(id) DO UPDATE SET …`。

**幂等性设计**：

- 重复执行只覆盖 id 1~8，**不会产生重复数据**。
- 因为显式插入了 1~8，SQLite 的自增序列会推进到 8，因此**用户发布的第一条数据 id 为 9**。
- id ≥ 9 的用户数据**永远不会被种子脚本触碰**。
- 全过程在单个事务内完成，并启用 `PRAGMA journal_mode=WAL`。

## 10. 从 localStorage 到服务端的迁移

| 旧键 | 旧用途 | 替代方案 | 兼容处理 |
| --- | --- | --- | --- |
| `campusResolved` | 记录本机标记为已解决的物品 id | `items.status` 字段 + 标记已解决接口 | 直接废弃，不做数据迁移。旧数据是每浏览器私有的，没有迁移价值；演示数据中 4 号物品初始即为已解决，其余由种子数据决定 |
| `campusNewItem` | 暂存刚发布的信息：成功页（222 行）与详情页 `?id=new`（419 行）读取；**首页与搜索页也读它**（`insertLocalPost`），用来在本机列表顶部插一张卡片 | 发布接口落库 + 成功页按 `?id` 重新查询；首页/搜索由后端数据直接渲染 | 成功页在**无 `?id` 或请求失败**时沿用原有的固定兜底摘要，保证直接打开该页不空白；详情页移除 `id=new` 分支（`loadItem` 里"本机无记录则回落 id=1"的分支一并删除）；首页/搜索的 `insertLocalPost` 整体删除 |

**行为差异（有意为之）**：

- 状态从"每浏览器私有"变为"服务端全局"。任何人标记已解决，所有人都能看到。
- 新发布的物品从"本机可见"变为"全局可见"：此前首页/搜索靠 `insertLocalPost` 在本机列表顶部插一张卡片，换设备即消失、也不进入真正的信息列表；此后它是**可被搜索、可被列表展示、可持久保存**的正式数据。
- 同一件物品不再可能"出现两次"：删掉本机插入逻辑后，列表内容唯一来源是后端。

## 11. 部署与运行

`requirements.txt`（运行期）：

```
fastapi
uvicorn
```

`requirements-dev.txt`（开发与测试，引用运行期依赖）：

```
-r requirements.txt
pytest
httpx
```

> `httpx` 是 FastAPI `TestClient` 的底层依赖，集成测试需要它。

> 使用纯净的 `uvicorn` 而非 `uvicorn[standard]`：后者会拉取需要编译的二进制依赖，在较新的 Python 版本上可能缺少预编译包；纯 Python 版本对本项目完全够用。

运行步骤（Git Bash / Windows）：

```bash
cd "F:/vibe coding/campus-lost-found"
python -m venv .venv
source .venv/Scripts/activate
pip install -r requirements-dev.txt
python -m backend.seed                  # 建表 + 写入演示数据（可重复执行）
uvicorn backend.main:app --reload --port 8000
```

访问：`http://127.0.0.1:8000/`（首页）。接口交互文档：`http://127.0.0.1:8000/docs`。

跑测试（测试层使用临时数据库，**不会触碰 `db.sqlite3`**）：

```bash
python -m pytest -q                     # 全部
python -m pytest tests/unit -q          # 只跑单元测试
python -m pytest tests/integration -q   # 只跑集成测试
python -m pytest tests/contract -q      # 只跑契约测试
ruff check .                            # 代码风格检查
```

用 `python -m pytest` 而非裸 `pytest`，是为了把工作目录加入 `sys.path`、让测试能 `import backend`。

**持续集成**：`.github/workflows/ci.yml` 在任何分支的 push、任何 PR 以及手动触发时运行，步骤为「确认前置条件（测试层目录 + 依赖文件） → 准备 Python → 安装依赖 → ruff 检查 → 单元测试 → 集成测试 → 契约测试」。三层各自独立成步，失败时能直接看出是哪一层的问题；前置条件检查排在装依赖之前，缺测试层或依赖文件时构建会以明确信息失败。某一层**目录存在但还没有测试**同样算失败——`pytest` 在无测试可收集时返回退出码 5，所以不会出现"没有测试却显示通过"的假绿；由此在测试分层建设完成之前 CI 会一直是红的，这属预期。详见《代码规范》第 3.8 节。

**注意事项**：

- 数据库文件 `db.sqlite3` 生成在仓库根目录，已被 `.gitignore` 忽略。
- `frontend/` 整个目录由静态挂载托管，主题样式文件随页面一起提供，无需额外配置。
- 必须通过 http 访问；直接双击 HTML 文件（`file://`）会因浏览器限制导致接口请求失败。
- 页面仍依赖外网 CDN（Tailwind 运行时、Iconify），离线环境页面样式与图标无法显示。

### 11.1 打包成单文件 exe（Windows）

```bash
pip install -r requirements-dev.txt      # 含 pyinstaller
.venv/Scripts/python.exe build_exe.py
```

产物是**仓库根目录**的 `campus-lost-found.exe`（约 17MB，不入库）。双击后：确保数据库存在
（没有就建表并写入演示数据）→ 启动服务 → 用 **Google Chrome** 打开 `/index.html`。
没装 Chrome 时退回系统默认浏览器，并在控制台说明用了哪个。

**exe 与后续代码改动的关系**——这是这个打包方式里最要紧的一点：

| 改动 | 需要重新打包吗 | 说明 |
| --- | --- | --- |
| 前端（HTML / CSS / JS） | **不需要** | exe 运行时优先使用**同级目录的 `frontend/`**。exe 就放在仓库根目录，所以它用的就是仓库里这份活的资源，改完刷新浏览器即可生效 |
| 数据库内容 | 不需要 | `db.sqlite3` 落在 exe 同级目录；删掉它再双击就是全新一份 |
| 后端 Python 代码 | **需要** | 代码是编译进 exe 的，这部分无法解耦。开发时用 `python -m backend`，交付时才打包 |

两个目录都实现了"外部优先、包内兜底"的解析规则：

| 资源 | 解析顺序 |
| --- | --- |
| 前端 | 环境变量 `CLF_FRONTEND_DIR` → **exe 同级 `frontend/`** → 包内 `sys._MEIPASS/frontend` → 开发时的仓库 `frontend/` |
| 数据库 | 显式入参 → 环境变量 `CLF_DB_PATH` → exe 同级 `db.sqlite3`（开发时是仓库根目录的） |

包里仍留了一份 `frontend/` 作兜底，所以把 exe 单独拷到别的机器上（旁边没有 `frontend/`）
也能跑。启动横幅会打印**当前生效的是哪一份**前端资源，免得出现"改了页面却没生效"的困惑。

命令行参数：`--host`、`--port`（默认 `127.0.0.1:8000`）、`--no-browser`（不自动开浏览器）。

## 12. 测试与验收清单

本章是**手工端到端验收清单**，覆盖页面的视觉与交互（自动化测试覆盖不到的部分）。两者的分工：

| 层 | 覆盖 | 在哪里 |
| --- | --- | --- |
| 单元测试 | 脱敏、时间推导、编号生成、搜索索引拼装、请求校验 | `tests/unit/`（自动化） |
| 集成测试 | 5 个接口的端到端行为、排序、条数、幂等、错误码 | `tests/integration/`（自动化） |
| 契约测试 | 接口返回字段与前端渲染所需字段一致 | `tests/contract/`（自动化） |
| 手工验收 | 页面视觉、交互反馈、卡片样式、跳转、空状态 | 本章 12.1–12.3（人工） |

每次提交前 `pytest -q` 必须全绿；每个阶段结束按本章逐条走一遍。

### 12.1 读路径

| # | 操作 | 预期 |
| --- | --- | --- |
| 1 | 访问 `/` 与 `/index.html` | 都能打开首页；6 张卡片，顺序 1~6，计数 6，4 号卡片变淡 |
| 2 | 首页点「寻物」/「招领」 | 分别 3 条（1、4、5）/ 3 条（2、3、6），计数同步 |
| 3 | 首页搜索框空提交 | 提示"请输入物品名称或关键词"，不跳转 |
| 4 | 首页输入"校园卡"提交 | 跳转搜索结果页，关键词回显"校园卡" |
| 5 | 不带参数打开搜索页 | 默认关键词"校园卡"，2 条结果，顺序 1、7 |
| 6 | 搜"钥匙" | 1 条（5 号） |
| 7 | 搜一个不存在的词 | 空状态 + 快捷标签；点「耳机」→ 1 条（4 号） |
| 8 | "校园卡" + 切到「招领」 | 1 条（7 号） |
| 9 | 清空关键词提交 | 8 条，顺序 1、7、5、3、2、4、6、8 |
| 10 | 打开 `?id=1` | 字段完整，时间 2026-09-27 08:20，联系方式 `138****6621` |
| 11 | 点「联系发布者」 | 展示完整联系方式并弹提示 |
| 12 | 打开 `?id=4` | 状态"已解决"，按钮禁用并显示"已标记为已解决" |
| 13 | 打开 `?id=999` | 回落显示 1 号物品 |

### 12.2 写路径

| # | 操作 | 预期 |
| --- | --- | --- |
| 14 | 发布页空提交 | 6 条错误文案正确、红框、滚动到第一个错误字段 |
| 15 | 切「我要招领」 | 标签与错误文案变为"拾取时间""拾取地点" |
| 16 | 填写完整提交 | 进入成功页，摘要与输入一致 |
| 17 | 成功页点「查看详情」 | 打开刚发布的那条（编号 LF-009、发布者"我（本机发布）"） |
| 18 | 返回首页 | 新信息在「最新信息」第一位，计数 7 |
| 19 | 搜索新物品名称 | 新信息排在结果第一位 |
| 20 | 详情页标记 5 号为已解决 | 提示、标签变绿、按钮禁用 |
| 21 | 刷新该页 / 换浏览器打开 | 状态仍为已解决 |
| 22 | 不带参数打开成功页 | 展示固定兜底摘要，不报错 |

### 12.3 数据与工程

| # | 操作 | 预期 |
| --- | --- | --- |
| 23 | 重启服务 | 数据仍在 |
| 24 | 重复执行 `python -m backend.seed` | 无重复数据，id 1~8 未被改变，id ≥ 9 的用户数据保留 |
| 25 | 检查 HTML 源码 | 每页只引用外部 css（`css/visual-theme.css`）、外部 js（api.js / common.js / 本页 js）与两个 CDN 脚本，**无内联 `<style>` 主题块、无内联脚本逻辑** |
| 26 | 全站检索 `home.html`、`localStorage`、`insertLocalPost` | 全部无残留；"返回首页"链接全部指向 `index.html` |
| 27 | 逐页对比改造前后截图 | 布局、间距、配色、图标、文案一致；**卡片左侧金线 / 圆角 / 纸白底色仍在**；仅已解决标签配色按设计统一为绿色 |
| 28 | 检查卡片 DOM 结构 | 首页卡片是 `#list` 的直接子 `<a>` 且带 `data-card`；搜索页卡片带 `data-result` 与 `data-keywords`（否则主题样式会静默失效） |
| 29 | 发布一条新信息后回首页 | 新信息只有**一张**卡片（`insertLocalPost` 已删，不会与本机插入的卡片重复），且与其它卡片样式一致（边框色不再是 `border-blue-100`） |
| 30 | 只保留一份主题文件 | 修改 `css/visual-theme.css` 里的一个 CSS 变量（如 `--accent`），5 个页面的配色**同时**变化 |

## 13. 已知限制与后续规划

| 限制 | 说明 |
| --- | --- |
| 无发布者鉴权 | 任何访客都能把任意物品标记为已解决，且该变更现在是全局的。**这是现有行为的延续**（旧版同样没有归属校验），可作为后续迭代项。 |
| 无用户体系 | 发布者昵称固定为"我（本机发布）"，无法区分真实发布者。 |
| 无分页 | 数据量小时无需分页；数据增长后列表会变长。 |
| 无图片 | 物品图标是固定的 Iconify 图标名，不支持上传实物照片。 |
| 依赖外部 CDN | Tailwind 运行时与 Iconify 从 `modao.cc` 加载，离线不可用；后续可考虑本地化。 |
| 主题依赖类名重映射 | 主题通过**覆盖 Tailwind 类名**实现配色，因此 HTML 里的类名与最终颜色不一致（写着 `bg-blue-600`，实际渲染为朱砂橙 `#e86143`）。改配色应改主题里的 CSS 变量，不要按类名的字面含义改，否则主题覆盖规则会失配。 |
| 测试覆盖的边界 | 测试层（`tests/`）覆盖后端纯逻辑（`unit`）、5 个接口的端到端行为（`integration`）与前后端字段契约（`contract`）。**前端页面本身没有自动化测试**——业务逻辑已全部下沉到后端，前端只剩渲染，因此页面的视觉与交互由第 12 节的手工验收清单覆盖；这也是不引入 Node 构建/测试环境这一决策的代价，见《代码规范》第 3.4 节。 |
| 无版本化的接口演进机制 | 接口未加版本前缀，属于演示级取舍。 |
