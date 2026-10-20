# 三阶段安全扫描框架

## 概述

本模块实现了研究论文中描述的三阶段安全扫描框架，用于检测 AI 技能的安全漏洞。

## 架构

```
┌─────────────────────────────────────────────────────────────┐
│                    三阶段安全扫描框架                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  阶段一: 静态安全扫描 (Static Security Scanner)              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ • 数据外泄: HTTP 请求, 环境变量, 凭证文件              │    │
│  │ • 代码注入: eval, exec, Shell 命令                    │    │
│  │ • 权限提升: sudo, chmod, 凭证访问                     │    │
│  │ • 供应链: 未固定依赖, 远程脚本执行                     │    │
│  │ • 指令威胁: "ignore previous", "override safety"      │    │
│  └─────────────────────────────────────────────────────┘    │
│                          │                                  │
│                          ▼                                  │
│  阶段二: LLM-Guard 分析 (LLM-Guard Scanner)                 │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ 10 个专用扫描器:                                       │    │
│  │ • PromptInjection, Secrets, Gibberish (0.6)           │    │
│  │ • InvisibleText, Sentiment (0.6), Toxicity           │    │
│  │ • BanSubstrings, BanTopics, Code, Regex              │    │
│  └─────────────────────────────────────────────────────┘    │
│                          │                                  │
│                          ▼                                  │
│                   Union 逻辑 (OR)                           │
│              静态阳性 OR LLM-Guard 阳性                      │
│                          │                                  │
│                          ▼                                  │
│  阶段三: 混合 LLM 分类 (Hybrid LLM Classifier)               │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ • 模型: Claude 3.5 Sonnet                             │    │
│  │ • Temperature: 0 (确定性)                              │    │
│  │ • Max Tokens: 4096                                    │    │
│  │ • 置信度阈值: ≥0.6 确认, [0.4,0.6) 不确定, <0.4 良性   │    │
│  └─────────────────────────────────────────────────────┘    │
│                          │                                  │
│                          ▼                                  │
│              聚合逻辑 (Aggregation)                          │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ • 推翻规则: LLM 置信度 ≥0.8 可推翻静态结果             │    │
│  │ • 最终状态: benign, flagged, uncertain                │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## 使用方法

### 命令行使用

```bash
# 扫描单个技能
python -m skillscan.three_phase_scanner /path/to/skill

# 指定 LLM 提供商和模型
python -m skillscan.three_phase_scanner /path/to/skill \
    --provider openai \
    --model claude-3-5-sonnet-20241022 \
    --out result.json \
    --pretty
```

### Python API 使用

```python
from pathlib import Path
from skillscan import ThreePhaseSecurityScanner

# 创建扫描器
scanner = ThreePhaseSecurityScanner(
    provider="openai",
    model="claude-3-5-sonnet-20241022"
)

# 扫描技能
result = scanner.scan(Path("/path/to/skill"))

# 检查结果
if result["status"] == "flagged":
    print("检测到安全威胁!")
    print(f"原因: {result['aggregation']['reason']}")
elif result["status"] == "uncertain":
    print("需要人工审查")
else:
    print("技能安全")
```

### 批量扫描

```python
from pathlib import Path
from skillscan import ThreePhaseSecurityScanner, calculate_prevalence

scanner = ThreePhaseSecurityScanner()

# 扫描多个技能
skill_dirs = list(Path("/skills").iterdir())
results = scanner.scan_batch(skill_dirs)

# 计算流行率
stats = calculate_prevalence(results)
print(f"总技能数: {stats['total']}")
print(f"标记率: {stats['prevalence_rate']:.1%}")
print(f"范围: [{stats['prevalence_range'][0]:.1%}, {stats['prevalence_range'][1]:.1%}]")
```

## 输出格式

```json
{
  "status": "flagged",
  "phase": "phase3",
  "aggregation": {
    "union_logic": true,
    "overridden": false,
    "reason": "LLM confirms threat (confidence: 0.75 ≥ 0.6)"
  },
  "phase1": {
    "has_findings": true,
    "findings_count": 2,
    "findings": [...]
  },
  "phase2": {
    "flagged": true,
    "flagged_scanners": ["secrets"],
    "details": {...}
  },
  "phase3": {
    "classification": "malicious",
    "confidence": 0.75,
    "threat_type": "data_exfiltration",
    "evidence": "...",
    "can_override_static": false
  }
}
```

## 状态说明

| 状态 | 说明 | 置信度条件 |
|------|------|-----------|
| `benign` | 良性，无安全威胁 | < 0.4 或被推翻 |
| `flagged` | 标记，存在安全威胁 | ≥ 0.6 |
| `uncertain` | 不确定，需要人工审查 | [0.4, 0.6) |

## 测试

```bash
# 运行测试套件
python skillscan/test_three_phase.py
```

## 模块结构

```
skillscan/
├── __init__.py                 # 模块导出
├── three_phase_scanner.py      # 主扫描器
├── hybrid_classifier.py        # 阶段三 LLM 分类器
├── llm_guard_scanner.py        # 阶段二 LLM-Guard 扫描器
├── aggregation.py              # 聚合逻辑
├── static_analysis_scan_skill.py  # 阶段一静态扫描器
├── skillscan.py                # 原有 8 维分类器（保留兼容）
└── test_three_phase.py         # 测试套件
```
