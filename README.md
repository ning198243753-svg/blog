# blog

个人学习博客 —— 用来记录学习笔记、知识整理与实践总结。

## 项目性质

以**学习为首要目的**、以**真实上线为约束条件**的单人全栈项目。
成功标准不是访问量，而是「能不能解释它、能不能给它排障、能不能从零重建它」。

## 技术栈

| 层次 | 选型 |
| --- | --- |
| 前端 | Vue 3（Composition API）+ Vite + Axios |
| 后端 | FastAPI + Uvicorn + Pydantic |
| 数据 | SQLite + SQLAlchemy + Alembic（开启 WAL 模式） |
| 部署 | 单机 4 核 / 4G 内存 / 3Mbps ｜ Ubuntu 22.04 + Docker Compose + Nginx + HTTPS |

## 文档

所有项目文档位于 [`docx/`](docx/)：

| 文档 | 内容 | 状态 |
| --- | --- | --- |
| [01-项目定义基线](docx/01-项目定义基线-v1.3.docx) | **阶段一 · 定义**：目标、非目标、用户、旅程、规模、功能与非功能需求、成功指标、约束、假设与风险、术语、参照物、预算、范围与里程碑 | 定稿（v1.3，已回写阶段二修订） |
| [02-技术决策记录](docx/02-技术决策记录-v1.0.docx) | **阶段二 · ADR**：10 条技术决策，每条含背景、候选方案、决策、理由、代价与重新评估的触发条件 | 定稿（v1.0） |
| [03-系统架构设计](docx/03-系统架构设计-v1.0.docx) | 分层架构、前后端目录结构、部署拓扑、关键流程时序、错误与日志规范 | 定稿（v1.0） |
| [04-数据库设计](docx/04-数据库设计-v1.0.docx) | ER 图、表结构、索引策略、迁移与备份策略、SQLite 专项设置 | 定稿（v1.0） |
| [05-接口设计](docx/05-接口设计-v1.0.docx) | 21 个接口契约、15 个错误码、鉴权约定、统一响应体、前端调用组织 | 定稿（v1.0） |
| [06-前端页面设计](docx/06-前端页面设计-v1.0.docx) | 11 个页面的线框与元素清单、站点地图、路由表、状态放置规则 | 定稿（v1.0） |
| [07-视觉设计系统](docx/07-视觉设计系统-v1.0.docx) | 设计令牌、排版规范、组件样式、响应式断点、暗色模式预案 | 定稿（v1.0） |
| [08-阶段三实施计划](docx/08-阶段三实施计划-v1.0.docx) | **阶段三 · 实现与验证**：可执行性检查、M0–M6 工作分解、验证线与完成的定义、AI 协作边界 | 定稿（v1.0） |

文档生成脚本与最终文档同目录，重跑脚本即可重新生成（版式参数集中在脚本顶部）。

## 阶段流程

五阶段 + 两条贯穿线：

```
定义不变量 ──▶ 约束与设计 ──▶ 实现与验证 ──▶ 交付 ──▶ 迭代
     │              │              │            │        │
     └──── 验证线：需求验收标准 / 单测与接口测试 / 系统验收 ────┘
     └──── 文档线：定义 / 设计 / 接口 / 部署 / 变更记录 ────────┘
```

## 当前进度

阶段一（定义）与阶段二（设计）已完成，正在执行阶段三（实现与验证）。

| 里程碑 | 内容 | 状态 |
| --- | --- | --- |
| M0 | 工程骨架：目录结构、依赖、数据库迁移、前端路由与代理 | ✅ 完成 |
| M1 | 后端公开 API：8 个只读接口 + 种子数据 | ✅ 完成 |
| M2 | 前端公开页面：列表 / 详情 / 标签 / 归档 / 搜索 / 关于 | ✅ 完成 |
| M3 | 鉴权与管理接口：13 个后台接口 + 图片上传 | ✅ 完成 |
| M4 | 管理后台页面：登录 / 文章 / 标签 / 设置 | ✅ 完成 |
| M5 | 部署：Docker Compose + Nginx + HTTPS | ✅ 配置完成，**未在真机验证** |
| M6 | 验收与交付 | 未开始 |

### 部署配置（M5）

**开发机上没有安装 Docker，所以容器相关配置全部未经运行验证。**
已验证与未验证的清单写在 [docs/部署文档.md](docs/部署文档.md) 第一节 ——
**首次部署前请先读那一节。**

```bash
# 服务器上（Ubuntu 22.04，已装 Docker）
git clone https://github.com/ning198243753-svg/blog.git /opt/blog
cd /opt/blog
cp backend/.env.example backend/.env && chmod 600 backend/.env
# 编辑 .env 填入 SECRET_KEY 与 ADMIN_PASSWORD
sed -i 's/__DOMAIN__/你的域名/g' nginx/nginx.conf
./deploy.sh init          # 首次
./deploy.sh update        # 之后每次更新
DOMAIN=你的域名 ./deploy.sh verify
```

| 文件 | 作用 |
| --- | --- |
| `docker-compose.yml` | 三个服务（nginx / backend / certbot）+ 一次性前端构建任务 |
| `backend/Dockerfile` | 多阶段构建，非 root 运行 |
| `frontend/Dockerfile` | 多阶段构建，产物单独成阶段（不含 node_modules） |
| `nginx/nginx.conf` | SPA 回退、API 转发、图片直出、HTTPS |
| `deploy.sh` | init / update / rollback / backup / verify / status |
| `deploy_check.py` | 部署配置一致性检查（10 类 40 项，本机可跑） |

**改动部署配置后请先跑一次一致性检查**，它会抓出「看起来对但实际不一致」的问题
（比如数据库路径不在卷内、Nginx 上限小于应用上限、后端端口意外暴露）：

```bash
python deploy_check.py
```

**为什么需要这个检查**：Docker 配置最典型的故障不是语法错（那些启动就报），
而是多处配置之间的约定不一致 —— 启动不报错、健康检查也过，
只有等到「容器重建后数据全没了」才暴露。而那时你可能已经在上面写了几周文章。

### 接口完成情况（对照文档 05）

| 分组 | 数量 | 路径前缀 |
| --- | --- | --- |
| 公开（无需登录） | 8 | `/api/articles`、`/api/tags`、`/api/archive`、`/api/search`、`/api/site`、`/api/health` |
| 鉴权 | 3 | `/api/auth/login`、`/api/auth/logout`、`/api/auth/me` |
| 后台文章 | 5 | `/api/admin/articles` |
| 后台标签 | 5 | `/api/admin/tags` |
| 站点配置 | 2 | `/api/admin/site` |
| 图片上传 | 1 | `/api/admin/upload` |

### 前端管理后台

访问 `/admin/login` 进入。会话是 HttpOnly Cookie（ADR-03），
JavaScript 读不到它，所以前端不管理令牌，只管理「当前用户是谁」。

| 页面 | 路径 | 说明 |
| --- | --- | --- |
| 登录 | `/admin/login` | 未登录访问后台会自动跳到这里，并保留原目标地址 |
| 文章管理 | `/admin/articles` | 列表 / 筛选 / 搜索 / 删除。筛选与分页状态放在 URL 里 |
| 文章编辑 | `/admin/articles/new`、`/admin/articles/:id/edit` | Markdown 编辑 + 实时预览 + 图片上传 |
| 标签管理 | `/admin/tags` | 新建 / 重命名 / 删除（删除前显示影响范围） |
| 站点设置 | `/admin/settings` | 基本信息 / 作者 / 链接 / 列表设置 |

**编辑器是 `<textarea>` + 实时预览，没有引入 md-editor-v3**：
文档 06 要求用成熟组件（不自研，NG-6），但预览复用 M2 已验证的
`markdown-body` 样式，代码约 100 行、零新依赖，且预览走独立 chunk
不进首屏包。**自动保存（文档要求每 30 秒）尚未实现**，目前只有
离开页面时的未保存提醒。

### 已知代价与待办

这些是**明确接受**的问题，不是遗漏。列在这里是为了避免它们被遗忘：

| 项 | 说明 | 计划 |
| --- | --- | --- |
| 登出后旧令牌仍有效 | 签名 Cookie 方案没有可作废的会话记录（ADR-03）。浏览器侧 Cookie 已清除，但令牌本身要等到过期。需要强制下线时只能改 `SECRET_KEY`（所有人一起掉线） | M5 评估会话有效期 |
| 孤儿图片文件 | 删除文章不会清理它引用的图片，文件会留在 `data/uploads/`。同一张图可能被多篇文章引用，自动删除有误删风险 | 记录为已知代价；M6 可加「未引用文件」查询 |
| 关于页不渲染 Markdown | `/api/site` 的 `author_intro` 返回原文，页面按纯文本显示。文档 06 写的是「Markdown 渲染后的 HTML」。后台设置页已能预览，前台仍不渲染 | M5 或 M6 |
| 编辑器无自动保存 | 文档 06 要求「每 30 秒或失去焦点保存为草稿」，理由是「丢内容是写作工具的头号死因」。目前只有离开提醒 | 下一轮 |
| 标签改名不改 slug | 文档 06 说「slug 同步更新」，实现是保持 slug 不变 —— 这样旧链接 `/tags/vue` 不会失效，代价是改名后 URL 与名称不一致 | 待用户确认 |
| 测试库与开发库共用 uploads | 上传测试产生的文件在结尾清理，但仍属于共享目录 | 低优先级 |
| 图片数量与总体积无上限 | 单机磁盘有限，目前靠人工 | M6 加监控 |

## 开发

### 后端

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate          # Windows；Linux/macOS 用 source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env            # 按注释填入 SECRET_KEY 与 ADMIN_PASSWORD
python -m alembic upgrade head  # 建表
python -m app.init_db           # 写入站点配置与管理员账号
python -m app.seed_data         # 可选：生成演示用种子数据
python -m uvicorn app.main:app --reload
```

接口文档：<http://127.0.0.1:8000/docs>

### 前端

```bash
cd frontend
pnpm install
pnpm dev                        # http://127.0.0.1:5173（已配置 /api 代理到 8000）
```

### 测试

```bash
cd backend
python run_tests.py             # 不依赖服务的测试
python run_tests.py --with-api  # 额外启动服务，跑接口端到端测试
python run_tests.py --with-api --keep-db   # 保留测试库，便于事后排查
```

当前共 11 个测试套件：6 个不依赖服务（Markdown/XSS、外键与 PRAGMA、N+1 查询、
种子数据确定性、密码哈希、登录流程），5 个接口端到端（鉴权、文章 CRUD、
标签与站点配置、图片上传、公开接口）。

前端页面用真实浏览器验证（需要前后端都在运行）：

```bash
cd frontend
node e2e-m2.mjs                 # 访客页面，46 项断言
node e2e-m4.mjs                 # 管理后台，67 项断言（需 ADMIN_PASSWORD）
```

**为什么接口测试通过还不够**：接口测试只证明「服务端契约正确」。
M2 时接口返回了 4 个 `<h2>`，而页面的目录却是空的（一个循环等待的 bug）——
接口测试完全看不见这类问题。所以凡是与浏览器行为有关的（Cookie 属性、
路由守卫、刷新后的登录态、表单提交、v-html 渲染），都在真实浏览器里验证。

**测试数据隔离**：接口测试跑在独立的 `data/db/blog_test.db` 上，跑完即删，
**不会读写 `data/db/blog.db`**。单元测试（外键、N+1）一律使用内存数据库。
每个可能写入的测试脚本启动时都会调用 `assert_not_dev_db()`，
连的是开发库就直接退出。

> 这条隔离不是洁癖，而是踩过坑之后的补救：早期版本的 `test_foreign_keys.py`
> 直接连开发库，并且为了验证级联删除而清空全部表 —— 它不会恢复原有数据。
> 结果是每跑一次测试，开发数据就被清空一次，而报错现象却是别的测试
> 报「列表为空 / total=0」，看起来像代码坏了。详见该文件顶部的说明。

**接口测试要求 8000 端口空闲**。端口被占用时脚本会直接中止并说明原因：
uvicorn 启动会失败，而探测到的「服务已就绪」其实是占用端口的那个进程
（通常是开发后端，它连的是开发库）。那样测试会全部打在开发库上，
报出一堆「正确密码返回 401」之类的误导性失败 —— 而且可能**写入开发库**。

**浏览器测试会自己清理数据**：`e2e-m4.mjs` 启动时先扫除历史残留
（上次运行中途失败会留下测试文章，那些残留会让别的测试出现莫名其妙
的失败），退出时用 `try/finally` 再清一次，异常路径也覆盖。

**开发期辅助脚本**（`tests/_` 开头，不属于测试套件，也不会被 `run_tests.py` 执行）：

| 脚本 | 用途 |
| --- | --- |
| `_env.py` | 数据库隔离工具（被测试引用） |
| `_list_routes.py` | 打印全部已注册路由，确认注册完整 |
| `_check_imports.py` | 找出未使用的导入与语法错误（不装 linter 的替代方案） |
| `_check_db.py` | 检查数据库 PRAGMA 与数据量 |
| `_check_leftovers.py` | 检查测试是否在开发库留下残留数据 |
| `_reproduce_kill.py` | 排查「强杀进程是否丢 WAL 数据」的诊断脚本 |


## 许可证

MIT
