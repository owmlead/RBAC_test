# RBAC 权限管理系统需求分析说明书

**版本**：v1.0
**更新日期**：2026-07-19

# 1 引言

## 1.1 编写目的

本文档用于明确 RBAC 权限管理系统的建设目标、业务需求、功能需求以及非功能需求，为系统设计、开发、测试和验收提供依据。

RBAC 权限管理系统旨在为企业级后台应用提供统一的身份认证、角色管理与权限控制能力，实现"用户 → 角色 → 权限"的标准化授权模型，提高企业应用的安全性和可维护性。

## 1.2 系统背景

随着企业信息化系统不断增加，各业务系统通常需要独立管理用户权限，面临以下问题：

- 权限管理分散——每个系统各自维护用户和权限，重复建设
- 授权不灵活——直接在代码中硬编码权限判断（`if user == 'admin'`），新增角色需要修改代码
- 缺乏审计追溯——不知道谁在什么时间做了什么操作
- 权限粒度粗糙——只有"能看"和"不能看"，无法精确到按钮级别
- 角色关系混乱——角色之间没有继承关系，无法复用权限配置

因此，需要建设一套统一的 RBAC（Role-Based Access Control）权限管理系统，提供：

- 用户管理（创建、编辑、启禁用、删除）
- 角色管理（创建、编辑、删除、复制、继承）
- 权限资源管理（菜单 + 按钮级别，树形结构）
- 菜单动态渲染（有权限才显示对应菜单项）
- 审计日志（记录所有操作行为）

## 1.3 术语定义

| 术语 | 说明 |
|---|---|
| 用户（User） | 系统的登录账号，一个用户可拥有多个角色 |
| 角色（Role） | 权限的集合，如"编辑者"、"只读用户"。角色可继承父角色 |
| 权限（Permission） | 操作的最小粒度。类型：MENU（菜单）或 BUTTON（按钮） |
| 权限编码（Permission Code） | 全局唯一的权限标识，如 `user:list`、`role:delete` |
| deny 优先 | 任一角色标记某权限为"拒绝"，则该权限最终被拒绝 |
| 角色继承 | 角色可设置父角色（parent_role_ids），BFS 递归获取祖先权限 |
| 审计日志（Audit Log） | 记录每次增删改操作的用户、时间、IP、结果等信息 |
| JWT | JSON Web Token，无状态身份认证令牌，分 access_token 和 refresh_token |

# 2 系统建设目标

## 2.1 统一身份认证

建立统一的用户认证体系，基于 JWT 双 Token 机制（access_token 30 分钟 + refresh_token 1 天），支持：

- 登录 / 登出 / Token 刷新
- Token 黑名单（登出后立即使 Token 失效）
- 登录失败锁定（5 次失败锁定 30 分钟）
- 图形验证码（登录失败 3 次后要求输入）
- 强制踢人下线

## 2.2 灵活的权限模型

实现"用户 → 角色 → 权限"三级 RBAC 模型：

- **用户** —— 可分配多个角色，最终权限为所有角色权限的并集
- **角色** —— 权限的集合，支持父子继承（BFS 递归），支持 deny 优先
- **权限** —— 最小操作单元，支持 MENU（菜单）和 BUTTON（按钮）两种类型，树形结构无限层级

## 2.3 动态菜单与前端权限控制

- 前端菜单由后端权限数据动态生成，而非写死在代码中
- 路由守卫根据用户权限控制页面访问（无权限跳 403）
- 按钮级别控制（v-if 根据权限码决定按钮是否显示）
- 后端双重校验（所有 API 端点强制验证权限）

## 2.4 操作审计

- 记录所有增删改操作的审计日志
- 支持按用户、操作类型、模块、时间、结果等条件筛选
- 支持日志导出（JSON 格式）

## 2.5 安全防护

- 密码 BCrypt 哈希存储
- 密码强度校验（≥8 位，字母/数字/特殊字符至少两类）
- 防暴力破解（登录失败锁定 + 验证码）
- 防用户名枚举（不存在用户和密码错误统一响应）
- API 速率限制（每 IP 每分钟 200 次）
- CORS 来源白名单
- JWT 密钥通过环境变量注入
- Token 黑名单持久化（Redis TTL 自动过期）

# 3 系统用户角色分析

## 3.1 预设角色

系统通过种子数据预置 4 个角色：

| 角色 | 角色编码 | 说明 |
|---|---|---|
| 超级管理员 | SUPER_ADMIN | 拥有全部 23 项权限，可管理用户、角色、权限、审计日志 |
| 管理员 | ADMIN | 可管理用户和角色，不可管理权限资源 |
| 编辑者 | EDITOR | 可查看、创建、编辑用户，**不可删除**用户（user:delete 被拒绝） |
| 只读用户 | VIEWER | 仅可查看列表，不可做任何修改操作 |

## 3.2 角色继承说明

角色通过 `parent_role_ids` 字段实现继承。系统启动时递归展开祖先角色，最终权限为所有角色（含祖先）的权限并集。

**deny 优先规则：** 若任一角色对某权限标记了 `is_deny=True`，则该权限最终被拒绝，即使其他角色授予了该权限。

示例：用户同时拥有 SUPER_ADMIN（授予 user:delete）和 EDITOR（拒绝 user:delete），最终 user:delete 被拒绝。

## 3.3 预设账号

| 用户名 | 密码 | 角色 | 说明 |
|---|---|---|---|
| admin | admin123 | SUPER_ADMIN | 超级管理员，全部权限 |
| editor | editor123 | EDITOR | 编辑者，可管理用户但不能删除 |
| viewer | viewer123 | VIEWER | 只读用户，仅查看 |
| multi | multi123 | EDITOR + VIEWER | 多角色演示 |

# 4 系统总体业务流程

## 4.1 用户登录流程

```Plaintext
用户输入用户名、密码
        ↓
系统检查是否被锁定（Redis/DB 查询失败次数）
        ↓
失败次数 ≥ 3？ → 要求输入验证码
        ↓
查询用户是否存在
        ↓
BCrypt 校验密码
        ↓
失败 → 记录登录失败（Redis INCR + EXPIRE），返回"用户名或密码错误"
        ↓
成功 → 签发 JWT（access_token 30min + refresh_token 1day）
        ↓
返回 Token + 用户信息（id, username, real_name, roles, permissions）
        ↓
前端存储 Token 到 localStorage，跳转仪表盘
```

## 4.2 权限校验流程

```Plaintext
API 请求到达
        ↓
提取 Authorization: Bearer <token>
        ↓
解析 JWT → 获取 user_id 和 jti
        ↓
Redis 检查 jti 是否在黑名单 → 是 → 401 "token 已被注销"
        ↓
DB 查询用户 → 不存在/已删除/已禁用 → 401
        ↓
检查路由所需权限码（如 "user:list"）
        ↓
从缓存或 DB 获取用户所有权限
        ↓
通配符匹配（"*" 或 "user:*" 匹配 "user:list"）
        ↓
通过 → 执行请求 | 不通过 → 403 "缺少权限"
```

## 4.3 页面刷新恢复流程

```Plaintext
用户刷新页面（F5）
        ↓
Vue 组件重新初始化
        ↓
从 localStorage 恢复 user（id, username, real_name）和 token
        ↓
路由守卫检查：token 存在 → 调 API 获取最新菜单和权限
        ↓
成功 → 渲染页面 | 失败 → 清除状态，跳登录
```

## 4.4 菜单动态渲染流程

```Plaintext
登录成功 → 调 GET /user/{id}/permissions
        ↓
后端查询用户权限 → 构建菜单树
        ↓
MENU 类型：保留所有（有权限的和无权限的都返回，用于导航结构）
BUTTON 类型：只返回用户拥有的
        ↓
递归过滤空菜单节点
        ↓
前端 SidebarMenu 递归渲染 el-menu → 点击菜单项 → router.push(path)
        ↓
路由守卫再次校验权限 → 放行或跳 403
```

# 5 功能需求分析

## 5.1 用户认证管理

### 功能描述

系统提供基于 JWT 的用户身份认证功能，包括登录、登出、Token 刷新、验证码和强制下线。

### 功能要求

1. **用户登录**

    - 输入用户名和密码
    - 密码使用 BCrypt 验证
    - 连续失败 5 次锁定 30 分钟（持久化到 Redis/DB）
    - 失败 3 次后要求输入图形验证码（数学运算 SVG）
    - 登录成功后签发 JWT（access_token 30 分钟 + refresh_token 1 天）
    - 返回用户信息（id, username, real_name, roles, permissions）

2. **Token 刷新**

    - 使用 refresh_token（在 Header 中传递）换取新的 access_token + refresh_token
    - 旧的 refresh_token 加入黑名单

3. **用户登出**

    - access_token 加入黑名单，使其立即失效

4. **强制下线（管理员）**

    - 管理员可强制下线指定用户
    - 使目标用户的权限缓存失效

5. **获取验证码**

    - 生成简单数学验证码（如 "3 + 5 = ?"），返回 SVG 图片 Base64
    - 一次性消费，验证后销毁

6. **权限检查**

    - 检查当前用户是否拥有指定权限编码

## 5.2 用户管理

### 功能描述

管理员可以对系统用户进行 CRUD 操作，批量启禁用，重置密码，分配角色。

### 功能要求

1. **用户列表查询**

    - 分页查询，支持关键字（用户名/邮箱/真实姓名）和状态筛选
    - 返回字段：id, username, real_name, email, phone, status, last_login_time, create_time

2. **创建用户**

    - 必填：username（4-20 字符）、password（≥8 位）、real_name（1-50 字符）、gender（0 未知/1 男/2 女）
    - 可选：email、phone、avatar、role_ids
    - 密码强度校验：须包含字母/数字/特殊字符中至少两类
    - 用户名唯一性校验

3. **编辑用户**

    - 可选更新：real_name、email、phone、status

4. **删除用户**

    - 软删除（标记 deleted_at）
    - 不能删除自己

5. **批量操作**

    - 批量启用/禁用
    - 批量删除

6. **重置密码**

    - 管理员可直接重置任意用户的密码（需新密码 ≥8 位，强度校验）
    - 重置后用户需要重新登录

7. **分配角色**

    - 全量覆盖用户角色
    - 分配后使权限缓存失效

8. **获取用户权限**

    - 获取用户的最终权限列表和动态菜单树

## 5.3 角色管理

### 功能描述

管理员可以对角色进行 CRUD 操作，支持角色树、复制、权限管理和用户关联。

### 功能要求

1. **角色列表查询**

    - 支持分页列表和角色树两种视图
    - 列表模式返回用户数（user_count）
    - 树模式按 parent_role_ids 构建层级结构

2. **创建角色**

    - 必填：role_name、role_code（唯一标识）
    - 可选：description、parent_role_ids（继承）、permissions（权限分配列表）
    - 循环依赖检测

3. **编辑角色**

    - 可选更新：role_name、description、parent_role_ids、permissions
    - 权限更新时使所有波及用户的缓存失效

4. **删除角色**

    - 有关联用户时拒绝删除
    - 系统内置角色（is_system=True）不可删除

5. **复制角色**

    - 复制角色的描述、父角色 ID 列表和权限分配

6. **角色关联用户查询**

    - 查询拥有该角色的所有用户（分页）

7. **移除角色关联用户**

    - 批量从角色中移除用户

## 5.4 权限资源管理

### 功能描述

管理系统的权限资源树（菜单 + 按钮），支持 CRUD、排序、导入导出。

### 功能要求

1. **权限树查询**

    - 返回完整权限树（嵌套结构），含 id, name, code, type, path, icon, sort, status, api_paths, children

2. **创建权限资源**

    - 必填：name、code（全局唯一）、type（MENU/BUTTON）
    - 可选：parent_id、path、icon、sort、status、api_paths
    - MENU 类型可设置前端路由路径和图标
    - BUTTON 类型可设置关联 API 路径列表

3. **编辑权限资源**

    - 可选更新：name、parent_id、path、icon、sort、status、api_paths
    - code 创建后不可修改

4. **删除权限资源**

    - 级联处理：子节点的 parent_id 设为 NULL（数据库外键 SET NULL）
    - 关联的 role_permission 记录自动删除（外键 CASCADE）

5. **排序**

    - 提交排序后的权限 ID 列表，按索引更新 sort 值

6. **导出**

    - 导出完整权限树（JSON 格式）

7. **导入**

    - 接收嵌套权限树 JSON，按 code 匹配：存在则更新，不存在则创建
    - 递归处理 children

## 5.5 审计日志管理

### 功能描述

记录系统所有增删改操作，支持多条件筛选和导出。

### 功能要求

1. **日志查询**

    - 分页查询，支持按用户名、操作类型、模块、结果、时间范围筛选
    - 返回字段：id, username, operation, module, description, request_params, ip, result, create_time

2. **日志导出**

    - 导出筛选结果（最多 1000 条），JSON 格式

3. **自动记录**

    - 所有增删改操作自动写入审计日志
    - 操作类型：LOGIN、CREATE、UPDATE、DELETE、KICK_OUT
    - 操作模块：AUTH、USER、ROLE、PERMISSION
    - 记录字段：操作人 ID、操作人用户名、操作类型、模块、描述、请求参数（脱敏）、IP、结果

# 6 权限模型详细说明

本章对系统的核心功能——RBAC 权限模型做详细说明。

## 6.1 权限编码体系

### 命名规范

权限编码采用 `模块:操作` 格式：

| 权限码 | 类型 | 说明 |
|---|---|---|
| system | MENU | 系统管理（顶级菜单） |
| user:manage | MENU | 用户管理（菜单入口） |
| user:list | BUTTON | 用户列表查询 |
| user:create | BUTTON | 创建用户 |
| user:update | BUTTON | 编辑用户 |
| user:delete | BUTTON | 删除用户 |
| user:assign-role | BUTTON | 分配角色 |
| user:detail | BUTTON | 查看用户详情 |
| user:kick | BUTTON | 踢人下线 |
| role:manage | MENU | 角色管理（菜单入口） |
| role:list | BUTTON | 角色列表 |
| role:create | BUTTON | 创建角色 |
| role:update | BUTTON | 编辑角色 |
| role:delete | BUTTON | 删除角色 |
| role:detail | BUTTON | 查看角色详情 |
| role:assign-user | BUTTON | 分配用户 |
| permission:manage | MENU | 资源管理（菜单入口） |
| permission:list | BUTTON | 资源列表 |
| permission:create | BUTTON | 创建资源 |
| permission:update | BUTTON | 编辑资源 |
| permission:delete | BUTTON | 删除资源 |
| audit:manage | MENU | 审计日志（菜单入口） |
| audit:list | BUTTON | 日志列表 |

### 通配符匹配

- `*` —— 超级管理员，拥有所有权限
- `user:*` —— 匹配 user:list、user:create 等所有 user 相关权限
- `user:list` —— 精确匹配

## 6.2 角色继承

### 继承机制

角色通过 `parent_role_ids` 字段声明父角色（JSON 数组，如 `[1, 2]`）。系统计算用户权限时 BFS 递归展开所有祖先角色。

### 循环检测

创建/更新角色时校验继承关系不会形成循环依赖。

## 6.3 deny 优先原则

```
最终权限 = 所有角色权限的并集
deny 优先：任一角色标记拒绝 → 最终拒绝
```

### 示例

| 角色 | user:list | user:delete |
|---|---|---|
| SUPER_ADMIN | ✅ 允许 | ✅ 允许 |
| EDITOR | ✅ 允许 | ❌ 拒绝 |
| **最终（deny 优先）** | ✅ 允许 | ❌ 拒绝 |

## 6.4 权限缓存

- 内存缓存 `{user_id: set(permission_codes)}`
- 角色变更 / 权限变更时自动清除波及用户的缓存
- 无 TTL 限制（重启清空）

# 7 数据库设计

## 7.1 数据库概览

- 数据库类型：MySQL 8.0
- 驱动：aiomysql（异步）
- ORM：SQLAlchemy 2.0（异步 session）
- 表数量：7 张业务表

## 7.2 E-R 关系图

```
                    ┌──────────────┐
                    │    user      │
                    │──────────────│
                    │ PK  id       │◄──────────────┐
                    │     username │               │
                    │     password │               │  user_id (FK)
                    │     ...      │               │
                    └──────┬───────┘               │
                           │ user_id (FK)          │
                           │                       │
                    ┌──────▼───────┐     ┌─────────┴─────────┐
                    │  user_role   │     │       logs        │
                    │──────────────│     │───────────────────│
                    │ PK,FK user_id│     │ PK  id            │
                    │ PK,FK role_id│     │     user_id       │
                    └──────┬───────┘     │     username      │
                           │ role_id (FK)│     operation     │
                           │             │     module        │
                    ┌──────▼───────┐     │     ...           │
                    │     role     │     └───────────────────┘
                    │──────────────│
                    │ PK  id       │◄───────────┐
                    │     role_name│            │
                    │     role_code│            │ role_id (FK)
                    │     ...      │            │
                    └──────┬───────┘            │
                           │ role_id (FK)      │
                           │            ┌──────┴───────────┐
                    ┌──────▼───────┐    │ role_permission   │
                    │  permission  │    │───────────────────│
                    │──────────────│    │ PK,FK role_id     │
                    │ PK  id       │◄───│ PK,FK permission_id│
                    │     name     │    │     is_deny       │
                    │     code     │    └───────────────────┘
                    │     type     │
                    │ FK  parent_id│───┐ (自关联)
                    │     ...      │   │
                    └──────────────┘   │
                           ▲           │
                           └───────────┘

┌────────────────┐     ┌─────────────────┐
│ token_blacklist│     │  login_failure  │
│────────────────│     │─────────────────│
│ PK  id         │     │ PK  id          │
│     jti (UQ)   │     │     username    │
│     expire_time│     │     ip          │
│     create_time│     │     fail_count  │
└────────────────┘     │     locked_until│
                       └─────────────────┘
```

**表间关系说明：**

| 关联 | 类型 | 说明 |
|---|---|---|
| user ←→ role | 多对多 | 通过 user_role 关联表，一个用户可有多个角色，一个角色可有多个用户 |
| role ←→ permission | 多对多 | 通过 role_permission 关联表，含 is_deny 拒绝标记 |
| permission → permission | 一对多（自关联） | parent_id 指向父资源，形成无限层级树 |
| logs → user | 多对一 | user_id 关联操作人（非外键，用户删除后日志保留） |
| token_blacklist | 独立 | 存储 JWT 的 jti，与用户无直接关联 |
| login_failure | 独立 | 按 username 记录失败次数，与 user 表无外键关联 |

## 7.3 表结构设计

### 7.3.1 user（用户表）

| 字段 | 类型 | 允许空 | 默认值 | 说明 |
|---|---|---|---|---|
| id | BIGINT | 否 | AUTO_INCREMENT | 主键 |
| username | VARCHAR(50) | 否 | — | 用户名（登录凭证） |
| password | VARCHAR(255) | 否 | — | BCrypt 哈希密码 |
| real_name | VARCHAR(50) | 否 | — | 真实姓名 |
| gender | TINYINT | 否 | 0 | 0=未知，1=男，2=女 |
| email | VARCHAR(100) | 是 | NULL | 邮箱 |
| phone | VARCHAR(20) | 是 | NULL | 手机号 |
| avatar | VARCHAR(255) | 是 | NULL | 头像 URL |
| status | TINYINT(1) | 否 | 1 | 1=启用，0=禁用 |
| remark | VARCHAR(500) | 是 | NULL | 备注 |
| last_login_time | DATETIME | 是 | NULL | 最近登录时间 |
| last_login_ip | VARCHAR(50) | 是 | NULL | 最近登录 IP |
| deleted_at | DATETIME | 是 | NULL | 软删除时间（NULL=未删除） |
| create_time | DATETIME | 否 | CURRENT_TIMESTAMP | 创建时间 |
| update_time | DATETIME | 否 | CURRENT_TIMESTAMP ON UPDATE | 更新时间 |

**唯一约束：** `(username, deleted_at)`、`(email, deleted_at)`、`(phone, deleted_at)`
**索引：** `(status, deleted_at)`、`(last_login_time)`

### 7.3.2 role（角色表）

| 字段 | 类型 | 允许空 | 默认值 | 说明 |
|---|---|---|---|---|
| id | BIGINT | 否 | AUTO_INCREMENT | 主键 |
| role_name | VARCHAR(50) | 否 | — | 角色名称 |
| role_code | VARCHAR(50) | 否 | — | 角色编码（UNIQUE） |
| description | VARCHAR(255) | 是 | NULL | 描述 |
| status | TINYINT(1) | 否 | 1 | 1=启用，0=禁用 |
| parent_role_ids | JSON | 是 | NULL | 父角色 ID 列表（如 [1,2]） |
| is_system | TINYINT(1) | 否 | 0 | 系统内置标记（1=不可删除） |
| sort | INT | 否 | 0 | 排序号 |
| create_time | DATETIME | 否 | CURRENT_TIMESTAMP | 创建时间 |
| update_time | DATETIME | 否 | CURRENT_TIMESTAMP ON UPDATE | 更新时间 |

**索引：** `(status)`、`(sort)`

### 7.3.3 permission（权限资源表）

| 字段 | 类型 | 允许空 | 默认值 | 说明 |
|---|---|---|---|---|
| id | BIGINT | 否 | AUTO_INCREMENT | 主键 |
| name | VARCHAR(50) | 否 | — | 资源名称 |
| code | VARCHAR(100) | 否 | — | 权限编码（UNIQUE） |
| type | VARCHAR(10) | 否 | — | MENU 或 BUTTON |
| parent_id | BIGINT | 是 | NULL | 父资源 ID（FK→permission.id, SET NULL） |
| path | VARCHAR(200) | 是 | NULL | 前端路由路径（菜单专用） |
| icon | VARCHAR(50) | 是 | NULL | 图标标识 |
| sort | INT | 否 | 0 | 排序号 |
| status | TINYINT(1) | 否 | 1 | 1=启用，0=禁用 |
| api_paths | JSON | 是 | NULL | 关联 API 路径列表（按钮专用） |
| create_time | DATETIME | 否 | CURRENT_TIMESTAMP | 创建时间 |
| update_time | DATETIME | 否 | CURRENT_TIMESTAMP ON UPDATE | 更新时间 |

**自关联：** `parent_id` → `id`，树形结构

### 7.3.4 user_role（用户-角色关联表）

| 字段 | 类型 | 允许空 | 说明 |
|---|---|---|---|
| user_id | BIGINT | 否 | 用户 ID（FK→user.id, CASCADE） |
| role_id | BIGINT | 否 | 角色 ID（FK→role.id, CASCADE） |

**主键：** `(user_id, role_id)` 复合主键

### 7.3.5 role_permission（角色-权限关联表）

| 字段 | 类型 | 允许空 | 默认值 | 说明 |
|---|---|---|---|---|
| role_id | BIGINT | 否 | — | 角色 ID（FK→role.id, CASCADE） |
| permission_id | BIGINT | 否 | — | 权限 ID（FK→permission.id, CASCADE） |
| is_deny | TINYINT(1) | 否 | 0 | 0=授予，1=拒绝（拒绝优先） |

**主键：** `(role_id, permission_id)` 复合主键
**索引：** `(permission_id)`

### 7.3.6 token_blacklist（Token 黑名单表）

| 字段 | 类型 | 允许空 | 说明 |
|---|---|---|---|
| id | BIGINT | 否 | 主键 |
| jti | VARCHAR(255) | 否 | JWT 唯一标识符（UNIQUE） |
| expire_time | DATETIME | 否 | Token 原始过期时间 |
| create_time | DATETIME | 否 | 加入黑名单时间 |

### 7.3.7 login_failure（登录失败记录表）

| 字段 | 类型 | 允许空 | 说明 |
|---|---|---|---|
| id | BIGINT | 否 | 主键 |
| username | VARCHAR(50) | 否 | 尝试登录的用户名（INDEX） |
| ip | VARCHAR(50) | 否 | 登录来源 IP |
| fail_count | INT | 否 | 失败次数 |
| locked_until | DATETIME | 是 | 锁定截止时间 |
| create_time | DATETIME | 否 | 首次失败时间 |
| update_time | DATETIME | 否 | 最近失败时间 |

### 7.3.8 logs（审计日志表）

| 字段 | 类型 | 允许空 | 说明 |
|---|---|---|---|
| id | BIGINT | 否 | 主键 |
| user_id | INT | 是 | 操作用户 ID |
| username | VARCHAR(50) | 否 | 操作人用户名（快照） |
| operation | VARCHAR(20) | 否 | 操作类型（LOGIN/CREATE/UPDATE/DELETE） |
| module | VARCHAR(20) | 否 | 操作模块（AUTH/USER/ROLE/PERMISSION） |
| description | VARCHAR(500) | 否 | 操作描述 |
| request_params | TEXT | 是 | 请求参数（脱敏 JSON） |
| ip | VARCHAR(50) | 是 | 操作 IP |
| result | VARCHAR(10) | 否 | SUCCESS 或 FAIL |
| create_time | DATETIME | 否 | 操作时间 |

# 8 接口设计

## 8.1 接口规范

- 协议：HTTP/1.1
- 格式：JSON
- 认证：Bearer Token（Header: `Authorization: Bearer <jwt>`）
- 全局前缀：`/api`

### 统一响应格式

**成功：**
```json
{"code": 0, "message": "success", "data": {...}}
```

**失败：**
```json
{"code": 401, "message": "token 无效或已过期", "data": null}
```

**分页：**
```json
{"code": 0, "data": {"total": 100, "page": 1, "size": 20, "list": [...]}}
```

### 分页参数

所有列表接口统一使用查询参数：`page`（≥1，默认 1）、`size`（1-100，默认 20）

## 8.2 认证鉴权 — `/api/auth`

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | `/auth/captcha` | 无 | 获取图形验证码 |
| POST | `/auth/login` | 无 | 用户登录 |
| POST | `/auth/refresh` | 无 | 刷新 Token（Header 传 refresh_token） |
| POST | `/auth/logout` | 无 | 用户登出 |
| POST | `/auth/kick-out` | user:kick | 强制下线用户 |
| POST | `/auth/check-permission` | 无 | 检查当前用户权限 |

### POST /auth/login 请求体

```json
{
  "username": "admin",
  "password": "admin123",
  "captcha_id": "可选",
  "captcha": "可选"
}
```

### POST /auth/login 响应

```json
{
  "code": 0,
  "data": {
    "access_token": "eyJ...",
    "refresh_token": "eyJ...",
    "token_type": "Bearer",
    "expires_in": 1800,
    "user_info": {
      "id": 1,
      "username": "admin",
      "real_name": "系统管理员",
      "roles": ["SUPER_ADMIN"],
      "permissions": ["user:list", "user:create", ...]
    }
  }
}
```

## 8.3 用户管理 — `/api/user`

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | `/user/` | user:list | 分页查询用户列表 |
| POST | `/user/` | user:create | 创建用户 |
| GET | `/user/{id}` | user:detail | 用户详情（含角色和权限） |
| PUT | `/user/{id}` | user:update | 编辑用户 |
| DELETE | `/user/{id}` | user:delete | 软删除用户 |
| PUT | `/user/batch-status` | user:update | 批量启用/禁用 |
| DELETE | `/user/batch` | user:delete | 批量删除 |
| PUT | `/user/{id}/reset-password` | user:update | 重置密码 |
| PUT | `/user/{id}/roles` | user:assign-role | 分配角色 |
| GET | `/user/{id}/permissions` | user:detail | 获取用户权限和菜单 |

### POST /user/ 请求体

```json
{
  "username": "newuser",
  "password": "Pass@123",
  "real_name": "新用户",
  "gender": 0,
  "email": "user@example.com",
  "phone": "13800000000",
  "role_ids": [11]
}
```

## 8.4 角色管理 — `/api/role`

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | `/role/` | role:list | 角色列表/树（?tree=true 返回树形） |
| POST | `/role/` | role:create | 创建角色 |
| GET | `/role/{id}` | role:detail | 角色详情（含权限树） |
| PUT | `/role/{id}` | role:update | 编辑角色 |
| DELETE | `/role/{id}` | role:delete | 删除角色 |
| POST | `/role/{id}/copy` | role:create | 复制角色 |
| GET | `/role/{id}/users` | role:detail | 角色关联用户列表 |
| DELETE | `/role/{id}/users` | role:assign-user | 移除角色关联用户 |

### POST /role/ 请求体

```json
{
  "role_name": "内容编辑",
  "role_code": "CONTENT_EDITOR",
  "description": "可编辑内容模块",
  "parent_role_ids": [11],
  "permissions": [
    {"permission_id": 72, "is_deny": false},
    {"permission_id": 74, "is_deny": false},
    {"permission_id": 76, "is_deny": true}
  ]
}
```

## 8.5 权限管理 — `/api/permission`

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | `/permission/tree` | permission:list | 完整权限树 |
| POST | `/permission/` | permission:create | 创建权限资源 |
| PUT | `/permission/{id}` | permission:update | 编辑权限资源 |
| DELETE | `/permission/{id}` | permission:delete | 删除权限资源 |
| PUT | `/permission/sort` | permission:update | 排序 |
| GET | `/permission/export` | permission:list | 导出权限树 |
| POST | `/permission/import` | permission:create | 导入权限树 |

### POST /permission/ 请求体

```json
{
  "name": "用户列表",
  "code": "user:list",
  "type": "BUTTON",
  "parent_id": 71,
  "sort": 0,
  "status": 1,
  "api_paths": ["GET /api/v1/user/"]
}
```

## 8.6 审计日志 — `/api/logs`

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | `/logs/` | audit:list | 多条件分页查询日志 |

### 查询参数

| 参数 | 类型 | 说明 |
|---|---|---|
| page | int | 页码（≥1） |
| size | int | 每页条数（1-100） |
| username | str | 操作人筛选 |
| operation | str | 操作类型（LOGIN/CREATE/UPDATE/DELETE） |
| module | str | 模块（AUTH/USER/ROLE/PERMISSION） |
| result | str | 结果（SUCCESS/FAIL） |
| start_time | str | 开始时间（ISO 8601） |
| end_time | str | 结束时间（ISO 8601） |

## 8.7 错误码参考

| HTTP 状态码 | code | 说明 | 触发场景 |
|---|---|---|---|
| 400 | 400 | 请求参数错误 | Pydantic 校验失败 |
| 401 | 401 | 未认证 | 缺少 Token、Token 无效/过期/已注销、用户禁用 |
| 401 | 401 | 账号锁定 | 连续登录失败超过阈值 |
| 403 | 403 | 无权限 | 用户缺少所需权限码 |
| 404 | 404 | 资源不存在 | 用户/角色/权限不存在 |
| 409 | 409 | 操作冲突 | 用户名已存在、角色编码重复、角色有关联用户不能删、不能删除自己 |
| 422 | 422 | 参数校验失败 | FastAPI 参数类型错误 |
| 429 | 429 | 请求过于频繁 | 超过速率限制（每 IP 200 次/分钟） |
| 500 | 500 | 服务器内部错误 | 未捕获异常 |

## 8.8 系统配置项

| 配置项 | 默认值 | 环境变量 | 说明 |
|---|---|---|---|
| DATABASE_URL | `mysql+aiomysql://root:root@localhost:3306/rbac_db` | `DATABASE_URL` | 数据库连接 |
| REDIS_URL | `redis://localhost:6380/0` | `REDIS_URL` | Redis 连接（不可用时降级 DB） |
| JWT_SECRET_KEY | `rbac-dev-secret-...` | `JWT_SECRET_KEY` | JWT 签名密钥（生产必须修改） |
| JWT_ALGORITHM | HS256 | — | JWT 签名算法 |
| ACCESS_TOKEN_EXPIRE_MINUTES | 30 | — | Access Token 有效期（分钟） |
| REFRESH_TOKEN_EXPIRE_DAYS | 1 | — | Refresh Token 有效期（天） |
| PASSWORD_MIN_LENGTH | 8 | — | 密码最小长度 |
| MAX_LOGIN_ATTEMPTS | 5 | — | 登录失败锁定阈值 |
| LOGIN_LOCK_MINUTES | 30 | — | 锁定时间（分钟） |
| CAPTCHA_THRESHOLD | 3 | — | 多少次失败后要求验证码 |
| CORS_ORIGINS | `http://localhost:5173` | `CORS_ORIGINS` | 允许的跨域来源（逗号分隔） |
| RATE_LIMIT | `200/minute` | — | 速率限制 |

## 8.9 项目目录结构

### 后端 (FastAPI)

```
src/rbac/
├── main.py                 # 应用入口，中间件注册，lifespan
├── seed.py                 # 测试数据种子脚本
├── api/                    # 接口层（路由 + 参数校验 + 依赖注入）
│   ├── router.py           # 顶层路由（/api 前缀）
│   ├── auth.py             # 认证接口
│   ├── user.py             # 用户接口
│   ├── role.py             # 角色接口
│   ├── permission.py       # 权限接口
│   └── logs.py             # 审计日志接口
├── service/                # 业务逻辑层
│   ├── _audit.py           # 审计日志写入（共享模块）
│   ├── auth.py             # 登录/刷新/登出/踢人
│   ├── user.py             # 用户 CRUD / 角色分配
│   ├── role.py             # 角色 CRUD / 继承 / 用户关联
│   ├── permision.py        # 权限 CRUD / 树构建 / 导入
│   └── checker.py          # 权限计算 / 缓存 / 菜单构建
├── crud/                   # 数据访问层
│   ├── user.py             # UserRepository
│   ├── role.py             # RoleRepository
│   ├── permission.py       # PermissionRepository
│   └── logs.py             # 审计日志读写
├── models/                 # ORM 模型
│   ├── user.py
│   ├── role.py
│   ├── permission.py
│   ├── user_role.py
│   ├── role_permission.py
│   ├── token_blacklist.py
│   ├── login_failure.py
│   └── logs.py
├── schemas/                # Pydantic 请求/响应模型
│   ├── auth.py
│   ├── user.py
│   ├── role.py
│   └── permission.py
├── core/                   # 核心模块
│   ├── config.py           # 配置管理（pydantic-settings）
│   ├── deps.py             # FastAPI 依赖（认证、权限、分页）
│   ├── exceptions.py       # 异常类 + 全局处理器
│   ├── security.py         # 密码哈希、JWT、验证码
│   └── redis_client.py     # Redis 客户端（含降级逻辑）
└── db/
    ├── base.py             # SQLAlchemy Base
    └── session.py          # 异步引擎、会话工厂、get_db
```

### 前端 (Vue 3)

```
src/
├── main.js                 # 应用入口，Element Plus + 图标全局注册
├── App.vue                 # 根组件（中文语言包）
├── api/                    # API 封装
│   ├── index.js            # Axios 实例 + 拦截器（Token 刷新、全局错误提示）
│   ├── auth.js
│   ├── user.js
│   ├── role.js
│   ├── permission.js
│   └── logs.js
├── stores/                 # Pinia 状态管理
│   ├── auth.js             # 用户、Token、权限、菜单、会话恢复
│   └── app.js              # 侧边栏、移动端抽屉
├── router/
│   └── index.js            # 路由配置 + 守卫（权限校验、会话恢复）
├── views/                  # 页面组件
│   ├── login/LoginView.vue
│   ├── dashboard/DashboardView.vue
│   ├── error/403.vue, 404.vue
│   └── system/
│       ├── users/UserList.vue, UserFormDialog.vue
│       ├── roles/RoleList.vue, RoleFormDialog.vue
│       ├── permissions/PermissionList.vue
│       └── audit/Log.vue
├── components/             # 公共组件
│   ├── layout/AppLayout.vue, HeaderBar.vue, SidebarMenu.vue
│   └── common/PermissionTree.vue
├── assets/styles/global.css  # 全局样式 + 移动端适配
└── utils/index.js          # Token 存储、日期格式化、用户信息持久化
```

# 9 前端系统需求

## 9.1 技术栈

| 技术 | 用途 |
|---|---|
| Vue 3 (Composition API) | 前端框架 |
| Vite | 构建工具 |
| vue-router 4 | 路由管理 |
| Pinia | 状态管理 |
| Element Plus | UI 组件库 |
| Axios | HTTP 客户端 |
| @element-plus/icons-vue | 图标库 |

## 9.2 页面需求

### 9.2.1 登录页面

- 输入用户名和密码
- 失败 3 次后显示图形验证码
- 登录成功后跳转仪表盘
- 已登录状态访问登录页自动跳转仪表盘

### 9.2.2 仪表盘

- 欢迎信息（欢迎回来，用户名）
- 统计卡片：用户总数、角色总数、权限资源数、审计日志数
- 快速导航：用户管理、角色管理、权限管理、审计日志（根据权限显示）

### 9.2.3 用户管理页面

- 搜索栏：关键字搜索 + 状态下拉筛选
- 工具栏：新增用户、批量启用、批量禁用、批量删除
- 数据表格：ID / 用户名 / 真实姓名 / 邮箱 / 手机号 / 状态 / 最后登录 / 创建时间 / 操作
- 操作按钮：编辑、角色、重置密码、删除（根据权限显示）
- 弹窗：新增/编辑用户表单、分配角色（checkbox-group）、重置密码

### 9.2.4 角色管理页面

- 列表/树形视图切换
- 搜索、新增、复制、删除角色
- 查看角色关联用户
- 角色表单：名称、编码、描述、权限分配（PermissionTree 组件）

### 9.2.5 权限资源管理页面

- 树形表格展示（可展开/收起）
- 新增根资源、添加子资源
- 编辑、删除资源
- 拖拽排序（提交全量排序）
- 导出/导入权限树

### 9.2.6 审计日志页面

- 多条件搜索：用户名、操作类型、模块、结果、时间范围
- 数据表格：ID / 用户名 / 操作类型 / 模块 / 描述 / IP / 结果 / 时间
- 日志详情弹窗（含请求参数）
- 导出日志

### 9.2.7 错误页面

- 403 无权限页面
- 404 页面不存在

## 9.3 移动端适配

- 响应式布局：桌面端（≥768px）侧边栏常驻，移动端（\<768px）侧边栏改为抽屉式
- 表格横向滚动
- 搜索栏纵向堆叠
- 对话框全屏适配
- 分页简化（小屏隐藏跳转和每页条数选择器）

# 10 非功能需求

## 10.1 安全性需求

1. **密码安全**

    - BCrypt 哈希存储，不存储明文
    - 密码强度校验：≥8 位，字母/数字/特殊字符至少两类

2. **认证安全**

    - JWT 双 Token 机制（access 30min + refresh 1day）
    - Token 黑名单（登出后立即失效）
    - 登录失败锁定（5 次 / 30 分钟，持久化到 Redis/DB）

3. **防攻击**

    - 防暴力破解：登录锁定 + 验证码
    - 防用户名枚举：不存在用户与密码错误统一响应
    - API 速率限制：每 IP 每分钟 200 次
    - CORS 白名单

4. **输入校验**

    - 服务端 Pydantic 模型校验所有输入
    - 用户名 4-20 字符、密码 ≥8 位
    - 分页参数 page≥1、size 1-100

5. **审计追溯**

    - 所有增删改操作记录审计日志
    - 记录操作人、时间、IP、参数（脱敏）

## 10.2 性能需求

1. **缓存策略**

    - 用户权限内存缓存（避免每次请求查库）
    - Redis 缓存 Token 黑名单和登录失败计数（TTL 自动过期）

2. **数据库**

    - 异步驱动（aiomysql）
    - 连接池（pool_size=20, max_overflow=10）
    - 关键查询字段建立索引（username, status, deleted_at）

3. **批量操作**

    - 批量 INSERT（单条 SQL 多值）
    - 分页查询避免全表扫描

## 10.3 可维护性需求

1. **模块分层**

    - API 层（路由 + 参数校验 + 依赖注入）
    - Service 层（业务逻辑 + 权限校验 + 审计）
    - CRUD 层（数据访问）
    - Model 层（ORM 模型）

2. **配置管理**

    - pydantic-settings 集中管理配置
    - 环境变量 > .env 文件 > 默认值三级优先级
    - 开发/生产环境通过环境变量切换

3. **错误处理**

    - 统一异常类（AppError / ConflictError / NotFoundError / ForbiddenError / UnauthorizedError）
    - 全局异常处理器（业务异常 + 兜底 500）
    - 500 错误记录日志（exc_info=True）

## 10.4 可靠性需求

1. **Redis 降级**

    - Redis 不可用时自动降级到 MySQL
    - Token 黑名单和登录失败计数均支持 DB 兜底
    - Redis 恢复后自动切换回 Redis

2. **事务保护**

    - session 级别事务管理（显式 commit/rollback）
    - 批量操作原子性（先删后插在同一事务内）

3. **软删除**

    - 用户使用软删除（标记 deleted_at，数据可恢复）
    - 角色和权限使用硬删除

# 11 系统开发范围说明

## 11.1 后端部分

| 模块 | 开发内容 | 状态 |
|---|---|---|
| 用户认证 | 登录、登出、Token 刷新、验证码、强制下线 | ✅ |
| 用户管理 | CRUD、批量启禁用、批量删除、重置密码、分配角色、权限查询 | ✅ |
| 角色管理 | CRUD、角色树、复制、用户关联查询、移除用户、循环依赖检测 | ✅ |
| 权限管理 | CRUD、权限树、排序、导入导出、deny 优先、角色继承 | ✅ |
| 审计日志 | 自动记录、多条件查询、导出 | ✅ |
| 安全防护 | BCrypt 密码、JWT 双 Token、黑名单、登录锁定、速率限制 | ✅ |
| Redis 集成 | Token 黑名单 TTL、登录失败 TTL、降级到 DB | ✅ |
| 菜单构建 | 用户菜单树、权限过滤、空节点清理 | ✅ |

## 11.2 前端部分

| 页面/组件 | 开发内容 | 状态 |
|---|---|---|
| 登录页面 | 用户登录、验证码 | ✅ |
| 仪表盘 | 统计卡片、快速导航 | ✅ |
| 用户管理 | 列表、搜索、CRUD、批量操作、角色分配、重置密码 | ✅ |
| 角色管理 | 列表/树形视图、CRUD、复制、权限分配、用户关联 | ✅ |
| 权限管理 | 树形表格、CRUD、排序、导入导出 | ✅ |
| 审计日志 | 多条件搜索、列表、详情、导出 | ✅ |
| 布局组件 | 侧边栏、顶栏、移动端抽屉 | ✅ |
| 错误页面 | 403、404 | ✅ |
| 移动端适配 | 响应式布局、抽屉式菜单 | ✅ |
| 权限树组件 | 勾选 + 允许/拒绝单选框 | ✅ |
| 路由守卫 | 权限校验、登录状态恢复 | ✅ |
| 全局错误处理 | Axios 拦截器统一提示 | ✅ |

