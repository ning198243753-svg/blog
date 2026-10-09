# ============================================================
# 前端镜像（只用于「构建」，不用于运行）
#
# 【这个镜像的产物是 dist/ 静态文件，不是运行中的服务】
# 静态文件最终由 Nginx 直接返回（ADR-01：纯 SPA + 无 SSR）。
# 所以这个镜像的用法是：
#   构建 → 把 dist 拷进一个卷 → Nginx 读那个卷 → 构建镜像本身可以丢弃
#
# 详见 nginx/Dockerfile 与 docker-compose.yml 里的说明。
#
# 【为什么不在服务器上跑 pnpm dev】
# 开发服务器会实时编译，单机 4G 内存下构建峰值就能打满，
# 而且它不适合对外服务。生产必须用构建好的静态文件。
# ============================================================

FROM node:22-alpine AS builder

WORKDIR /app

# 【为什么要装 pnpm 而不是用 npm】
# 仓库里的 lockfile 是 pnpm-lock.yaml（项目最初就用 pnpm）。
# 用 npm 会因为缺少 package-lock.json 而重新解析全部依赖，
# 结果是「本地能构建、服务器构建出的依赖版本不同」——
# 这类差异会在运行时才暴露，而且极难排查。
#
# 【为什么是 corepack enable 而不是 corepack prepare pnpm@版本号】
# package.json 里已经声明了 packageManager: "pnpm@10.15.0"，
# corepack 会读那个字段并使用对应版本。
# Node.js 官方文档：「The Corepack proxies will find the closest
# package.json file in your current directory hierarchy to extract
# its "packageManager" property... Corepack will make sure that all
# calls to the relevant binaries are run against the requested version,
# downloading it on demand if needed.」
#
# 之前这里写的是 `corepack prepare pnpm@latest --activate`，
# 那是错的：latest 意味着「今天构建」和「三个月后构建」
# 可能用不同的 pnpm 大版本，而不同大版本对 lockfile 的
# 兼容性不作保证 —— 于是「同样的代码，构建结果不同」。
#
# 版本只有一个来源（package.json），比在两处各写一遍更不容易失配。
#
# 【注意：这一步需要网络】
# corepack 会在首次使用时从 registry 下载 pnpm 本身
# （文档：「Upon first use, Corepack downloads the latest version
# from the network」）。所以构建机必须能访问 npm registry。
# 完全离线的环境需要预先 `corepack pack` 把包管理器打进去。
RUN corepack enable

# ---- 依赖层：单独一层，利用缓存 ----
# 只 COPY 依赖清单，源码变化不会让这一层失效。
COPY package.json pnpm-lock.yaml ./

# 【为什么要 --frozen-lockfile】
# 它强制 pnpm 严格按 lockfile 安装，如果有任何不一致就直接失败。
# 不加的话 pnpm 会「顺手」更新 lockfile 并装上新版本 ——
# 于是生产环境跑的可能是一个从未被测试过的依赖版本。
RUN pnpm install --frozen-lockfile

# ---- 源码与构建 ----
COPY . .

# 【为什么要设这个环境变量】
# vite.config.ts 里如果根据 NODE_ENV 判断构建模式，
# 不明确设置会依赖基础镜像的默认值 —— 那是 Alpine 镜像的偶然属性，
# 不是我们声明的意图。
ENV NODE_ENV=production

# vue-tsc 做类型检查 + vite build。
# 【类型检查放在构建里而不是只放 CI】
# 类型错误在运行时表现为 undefined 访问之类的怪现象，
# 而构建期直接失败能把它挡在部署之前。
RUN pnpm run build

# ============================================================
# 产物阶段：把 dist 单独拿出来，供 compose 拷进共享卷
#
# 【为什么要这个空阶段】
# 直接用 builder 阶段也能取文件（--target builder），
# 但那样产物和 node_modules（几百 MB）混在一起，
# 任何取文件的命令都要小心别把它一起拷出去。
# 单独一个只含 dist 的阶段，目标明确、不可能拷错。
# ============================================================
FROM alpine:3.20 AS dist

WORKDIR /dist
COPY --from=builder /app/dist ./

# 默认命令：把产物输出到 stdout 会让镜像无法使用，
# 这里给一个明确的行为 —— 列出来，方便确认构建成功且内容合理。
CMD ["ls", "-la", "/dist"]
