---
name: google-gemini-image
description: "Google Gemini 网页端生图。通过 OpenClaw Browser Tool（profile=user）控制 Chrome 生成和下载图片。使用场景：谷歌生图/Gemini 生图/Google Gemini 图片。"
---

# Google Gemini 生图

通过 OpenClaw Browser Tool（`profile="user"`）操控已登录 Google 账号的 Chrome 浏览器，在 Gemini 网页端生成并下载图片。

## 前置条件

- Chrome 已登录 Google 账号
- OpenClaw Gateway 正常运行
- OpenClaw Browser Tool 可用（`profile="user"` 连接已登录的 Chrome）

## 执行流程

### 1. 打开 Gemini 页面

```javascript
browser(action="open", profile="user", url="https://gemini.google.com")
```

记录返回的 `targetId`，后续所有操作都带上这个 `targetId`。

也可以直接打开已有对话链接复用图片：
```javascript
browser(action="open", profile="user", url="https://gemini.google.com/app/<对话ID>")
```

### 2. 点击「制作图片」

```javascript
browser(action="snapshot", profile="user", targetId="<ID>", compact=true)
// 找到「制作图片」按钮的 ref，然后 click
browser(action="act", profile="user", targetId="<ID>", ref="<ref>", kind="click")
```

### 3. 输入 Prompt 并发送

在 textarea 中输入 prompt，然后按 Enter 发送：

```javascript
browser(action="act", profile="user", targetId="<ID>", ref="<textarea ref>", kind="type", text="你的Prompt")
browser(action="act", profile="user", targetId="<ID>", ref="<textarea ref>", kind="press", key="Enter")
```

**注意**：prompt 中避免使用"唱""弹奏"等动词关键词，否则 Gemini 会误触发音乐生成而非图片生成。

### 4. 等待图片生成

`wait` 操作后 snapshot 检查是否出现「下载完整尺寸的图片」按钮：

```javascript
browser(action="act", profile="user", targetId="<ID>", kind="wait", timeMs=15000)
browser(action="snapshot", profile="user", targetId="<ID>", compact=true)
```

生成完成标志：页面出现「下载完整尺寸的图片」「复制图片」「分享图片」等按钮。

### 5. 下载图片

点击「下载完整尺寸的图片」按钮：

```javascript
browser(action="act", profile="user", targetId="<ID>", ref="<下载按钮ref>", kind="click")
```

等待几秒后检查下载目录：

```bash
sleep 3 && ls -lt ~/Downloads/Gemini_Generated_Image* | head -3
```

### 6. 去水印（可选）

Gemini 生成的图片带有水印，可使用 [GeminiWatermarkTool](https://github.com/allenk/GeminiWatermarkTool) 去除。

**安装**（macOS / Linux）：
```bash
brew install allenk/tap/gwt
```
或从 [GitHub Releases](https://github.com/allenk/GeminiWatermarkTool/releases) 下载二进制文件。

**使用**：
```bash
gwt --force -i <输入图片> -o <输出图片>
```

## 已知问题

| 问题 | 解决方案 |
|------|----------|
| `timed out` | browser tool 超时后不要盲目重试，用 `snapshot` 检查连接状态 |
| `tab not found` | `browser(action="stop")` → `browser(action="start")` 重置 |
| 标签页立即断开 | 先 `browser(action="tabs")` 查看已有 tabs，复用已有 ID |
| 触发了音乐生成 | prompt 去掉"唱""弹"等词，改为纯视觉描述 |
| 图片长时间未生成 | Gemini Nano Banana 模型较慢，耐心等待或刷新页面重试 |

## 完成后

- 关闭不用的标签页：`browser(action="close", profile="user", targetId="<ID>")`
- 如果后续还要用 browser tool，先 stop 再 start 重置 session
