# 📖 OpenMemory 详细使用说明手册 (User Manual)

欢迎使用 **OpenMemory**！本文档专为开发者与终端用户编写，从「0 基础小白配置」到「进阶私有化部署与 Obsidian 联动」，带你快速玩转个人 AI 记忆治理系统。

---

## 目录
- [一、3 分钟极速上手（本地单机模式，最推荐）](#一3-分钟极速上手本地单机模式最推荐)
  - [1.1 自动配置向导（1 秒搞定）](#11-自动配置向导1-秒搞定)
  - [1.2 手动配置 Cursor](#12-手动配置-cursor)
  - [1.3 手动配置 Claude Desktop](#13-手动配置-claude-desktop)
  - [1.4 手动配置 Windsurf / Cline](#14-手动配置-windsurf--cline)
- [二、日常与 AI 对话使用范例](#二日常与-ai-对话使用范例)
  - [2.1 注入新习惯与技术决策](#21-注入新习惯与技术决策)
  - [2.2 自动回忆与检索](#22-自动回忆与检索)
  - [2.3 纠正 AI 的错误判断（非破坏性演进）](#23-纠正-ai-的错误判断非破坏性演进)
  - [2.4 强制遗忘旧偏好](#24-强制遗忘旧偏好)
- [三、可视化审查与冲突仲裁 Web 控制台](#三可视化审查与冲突仲裁-web-控制台)
- [四、Obsidian / Markdown 笔记与多端同步](#四obsidian--markdown-笔记与多端同步)
- [五、数据存储与备份](#五数据存储与备份)
- [六、常见问题排查 (FAQ)](#六常见问题排查-faq)

---

## 一、3 分钟极速上手（本地单机模式，最推荐）

> 💡 **本地模式特点**：
> 100% 离线、零外部网络请求、零费用、不需要配置任何 API 密钥，响应延迟在 1 毫秒以内。

### 1.1 自动配置向导（1 秒搞定）

在项目根目录下：
- **Windows 用户**：双击运行 `scripts\setup.bat`。
- **Mac / Linux 用户**：终端运行 `./scripts/setup.sh`。

或者直接在终端运行 Python 向导：
```bash
python client/wizard.py
```
向导会让你选择想要配置的 IDE，按提示输入数字回车，就会自动在对应的配置文件中注入 MCP 服务端！

---

### 1.2 手动配置 Cursor

如果你习惯手动修改配置：

1. 在你的项目根目录新建或打开 `.cursor/mcp.json`（如果没有该文件夹直接新建即可）。
2. 添加以下配置（**注意将路径替换为你实际存放 openmemory 的绝对路径**）：

```json
{
  "mcpServers": {
    "openmemory": {
      "command": "python",
      "args": [
        "D:/opensource/client/mcp_server.py",
        "--mode",
        "local"
      ],
      "env": {
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```
*(Windows 路径中的斜杠建议使用正斜杠 `/` 或双反斜杠 `\\`)*

3. 重启 Cursor 或在 Cursor Settings -> Features -> MCP 中查看 `openmemory` 状态，显示绿色小圆点即代表连接成功！

---

### 1.3 手动配置 Claude Desktop

打开 Claude Desktop 的配置文件：
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

在 `mcpServers` 对象中追加：
```json
{
  "mcpServers": {
    "openmemory": {
      "command": "python",
      "args": [
        "D:/opensource/client/mcp_server.py",
        "--mode",
        "local"
      ]
    }
  }
}
```
保存并完全重启 Claude Desktop 客户端即可。

---

### 1.4 手动配置 Windsurf / Cline

- **Windsurf**：在 `~/.codeium/windsurf/mcp_config.json` 中添加上述同样的 JSON 块。
- **Cline**：在 VS Code 插件设置中搜索 Cline MCP Settings，将上述内容加入 `mcpServers`。

---

## 二、日常与 AI 对话使用范例

配置完成后，**你不需要在每次对话时手动唤起任何命令**。在正常对话过程中，支持 MCP 的 AI Agent 会在后台自主调用 OpenMemory 的 6 个标准化治理工具：

### 2.1 注入新习惯与技术决策
> **你的提示词**：
> *“从今天起，我们所有 Python 代码必须遵循 Google Style，强制使用 4 个空格缩进，严禁使用 tab，请记住这个规则。”*

🤖 **AI Agent 后台行为**：
- 自动调用 `record_memory`
- 标记为 `source_type: "user_statement"`（直接陈述，置信度最高 1.0）
- 标记为 `sensitivity: "L0"`（通用公开编码规范）
- 记录原句为溯源证据证据链。

---

### 2.2 自动回忆与检索
> **你的提示词**：
> *“帮我新建一个 Python 工具类文件，处理时间转换。”*

🤖 **AI Agent 后台行为**：
- 自动调用 `recall_memories(query="python style")`
- 从本地 SQLite 数据库检出“必须遵循 Google Style，4 空格缩进”的记忆
- 在生成的代码中直接套用你的习惯，无需反复重复要求。

---

### 2.3 纠正 AI 的错误判断（非破坏性演进）
> **你的提示词**：
> *“你之前记的我喜欢用 unittest，那个判断是错的，我现在全面换成 pytest 了，更正一下。”*

🤖 **AI Agent 后台行为**：
- 自动调用 `correct_memory(old_memory_id="mem_...", new_statement="全面使用 pytest 进行单元测试")`
- 旧记录不会被直接物理抹除，而是标记为 `superseded`（已被取代），指向新条目
- 新条目记录 `supersedes_id` 指向旧条目，保留完整的审计演进链路。

---

### 2.4 强制遗忘旧偏好
> **你的提示词**：
> *“把我之前提到的某个临时测试账号的记忆彻底遗忘掉。”*

🤖 **AI Agent 后台行为**：
- 自动调用 `forget_memory(memory_id="mem_...")`
- 进入软删除回收期或永久封存，如果这条记忆曾经作为推导前提推导出了其他画像，系统会自动将下游衍生结论标记为 `stale_recalc`（待重算），杜绝僵尸结论干扰。

---

## 三、可视化审查与冲突仲裁 Web 控制台

如果你想用图形化界面直接查看、搜索、修改所有被记住的信息，可以启动随附的 Web 控制台：

### 启动控制台：
- **Windows**：双击 `scripts\start_server.bat`
- **Linux / Mac**：执行 `./scripts/start_server.sh`
- 或命令行直接启动：
  ```bash
  python -m server.app
  ```

然后在浏览器打开：**`http://localhost:8080`**

### 控制台核心功能：
1. **记忆全维看板**：按状态（活跃 / 冲突隔离 / 待复核 / 已废弃 / 软删除）与敏感度（L0 / L1 / L2）一键过滤筛选。
2. **冲突仲裁厅**：当同一分类下存在两条相互矛盾的规则时，系统自动双向隔离，暂停提示词注入，等待你在网页上点击「以新代旧」、「场景分流（工作/生活）」或「手动重构」。
3. **不可篡改审计流水**：查看每一次记录由哪个 Agent、在什么时间、因为什么原因被创建、加固或废除。
4. **一键数据导出**：直接在网页点击按钮导出为 JSON 或 Markdown 压缩包。

---

## 四、Obsidian / Markdown 笔记与多端同步

如果你不想维护 24 小时开机的服务器，只想把两台电脑（比如家里的台式机和公司的笔记本）的记忆打通：

### 1. 导出为 Markdown Vault：
```bash
python client/export_import.py export --format vault -o ./my_vault
```
导出的目录结构如下：
```text
my_vault/
├── README.md                  # 记忆全景索引目录
├── preference_mem_001.md      # 单条记忆卡片（带 YAML 头信息）
└── architecture_mem_002.md
```
每个文件都带有标准的 Obsidian Frontmatter：
```markdown
---
id: mem_20261103_01
category: preference
confidence: 0.95
sensitivity: L0
source_type: direct_statement
status: active
---
# Python 代码规范
严格遵循 Google Style，全流程使用 4 空格缩进。
```

### 2. 多端同步方案：
- 将导出目录直接保存在你的 **Obsidian 库**、**iCloud Drive**、**OneDrive**、**坚果云** 或一个**私有 Git 仓库**中。
- 在另一台电脑上，直接运行导入指令即可同步：
  ```bash
  python client/export_import.py import -f ./backup.json
  ```

---

## 五、数据存储与备份

- **数据库路径**：默认存放在当前用户的主目录 `~/.openmemory/memory.db`。
- **自定义存放路径**：如果你希望将数据库保存在特定硬盘或同步盘中，设置系统环境变量即可：
  ```bash
  # Windows PowerShell
  $env:OPENMEMORY_DATA_DIR="D:\MySyncFolder\openmemory_data"

  # Linux / macOS
  export OPENMEMORY_DATA_DIR="/Users/yourname/MySyncFolder/openmemory_data"
  ```
- **彻底重置**：如果想清空所有记忆重新开始，只需关闭 IDE 并删除 `~/.openmemory/memory.db` 即可。

---

## 六、常见问题排查 (FAQ)

### Q1: Cursor 提示 `Failed to start MCP server`？
- **检查 Python 环境**：确保命令行输入 `python --version` 是 Python 3.10 或更高版本。
- **检查路径拼写**：在 Windows 上，路径中的反斜杠 `\` 可能会被 JSON 转义，请务必使用正斜杠 `/`（例如 `D:/opensource/client/mcp_server.py`）或者双反斜杠 `\\\\`。

### Q2: AI 真的在用这套记忆吗？我怎么知道它调用了？
- 在 Cursor 对话框中，当 AI Agent 做出响应时，你会看到它折叠的「Tool Call: recall_memories」或「record_memory」调用痕迹。
- 也可以直接在对话框问 AI：*“请调用 get_governance_stats 工具帮我看看你现在记住了多少条规则。”*，AI 就会读取并回答你。

### Q3: 为什么有的推断记忆会提示进入“待复核”？
- 这是 OpenMemory 的**第 3 层置信度衰减机制**：由 AI 自行推断但超过 14 天从未被你再次印证的推论，置信度会按周逐渐下降。当跌破 0.40 时会自动转入待复核，防止过时的错误推论成为黑箱僵尸结论。

---
祝使用愉快！如有疑问或建议，欢迎提交 Issue 或 Pull Request！
