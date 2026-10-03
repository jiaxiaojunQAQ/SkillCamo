# create-agent

> 基于 [OpenClaw](https://github.com/openclaw/openclaw) 的 AgentSkill

OpenClaw skill：创建 Agent 及 Workspace 的完整流程工具。

## 功能

自动化完成新 Agent 的全套创建流程：

- **Phase 1** — 信息收集（agentId / 工具权限 / 父 Agent / 类型）
- **Phase 2** — Workspace 构造（SOUL.md / AGENTS.md / BOOTSTRAP.md 等全套文件）
- **Phase 3** — 系统注册（安全修改 openclaw.json，备份 + 双向绑定 + validate）
- **Phase 4** — 重启验证（以工具可用性验证作为完成标志）

## 核心设计理念

> **skill 负责骨架，BOOTSTRAP.md 负责灵魂。**

- skill 产出可运行的 Agent（系统层 + workspace 骨架）
- BOOTSTRAP.md 通过动态对话（由浅入深，推荐型提问）完成 workspace 内容层定制
- workspace 从真实使用中持续生长（触发式写入 + heartbeat 精炼）

## 文件结构

```
create-agent/
├── SKILL.md                          # 触发条件 + 四 Phase 执行流程
├── references/
│   ├── file-formats.md               # 每个 workspace 文件"写好"的标准
│   ├── soul-writing-guide.md         # SOUL.md 素材→叙事的组织方法
│   ├── evolve-rules.md               # workspace 持续生长规则
│   └── bootstrap-protocol.md        # BOOTSTRAP.md 动态对话协议蓝本
└── scripts/
    ├── create_workspace.sh           # 创建目录结构
    └── register_agent.py             # 安全注册（备份+双向绑定+validate+回滚）
```

## 安装

需要先安装 [OpenClaw](https://github.com/openclaw/openclaw)。

```bash
clawhub install openclaw-create-agent
```

或手动克隆到 `~/.openclaw/skills/create-agent/`。

## 触发

在 OpenClaw 对话中说：
- "创建 agent"
- "新建 agent"
- "新员工配对后创建 agent"
- "新增专业 agent"

## 依赖

- OpenClaw >= 2026.3.0
- `openclaw` CLI（用于 config validate）
- `systemctl --user`（用于 Gateway 重启）
