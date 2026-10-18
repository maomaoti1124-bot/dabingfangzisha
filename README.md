# 大冰防zisha skill

希望通过真诚、温和且有边界的对话，陪伴正在经历痛苦的人，帮助他们缓解自杀或自伤的念头，并连接现实中的支持与专业帮助。

**当前状态：0.1 对话原型。提供 Codex 技能、WorkBuddy 导入包和 DeepSeek 本地聊天软件。已完成本地接口模拟测试，尚未用真实 API Key 联调，也未经临床验证或专业危机服务验收。**

## 安装与调用

选择一种使用方式即可。Codex 和 WorkBuddy 使用各自客户端选定的模型；DeepSeek 网页聊天软件则通过服务端直接调用 DeepSeek API。安装技能不会自动切换客户端模型，也不会自动获得急救或热线检索能力。

### 方式一：在 Codex 输入一句话安装

把下面整段复制到 Codex 对话框：

```text
请使用 skill-installer 安装这个 GitHub 仓库根目录中的 Skill：
https://github.com/maomaoti1124-bot/dabingfangzisha
仓库路径为 .，技能名称为 dabing-fangzisha-skill，目标目录为 ~/.agents/skills/dabing-fangzisha-skill/。
请先读取 SKILL.md，检查来源和文件内容，再完成安装。如果存在同名目录，请报告差异，不要静默覆盖。
安装后请检查 SKILL.md 和引用文件存在，并告诉我如何调用；本轮不要自动开始心理支持对话。
```

安装后，在新一轮对话中输入：

```text
$dabing-fangzisha-skill 我最近有些难受，想聊一聊。
```

如果没有出现在技能列表中，重启 Codex 后再检查。也可以在终端手动安装（需要 Git，以下适用于 macOS / Linux）：

```sh
mkdir -p "$HOME/.agents/skills"
git clone https://github.com/maomaoti1124-bot/dabingfangzisha.git "$HOME/.agents/skills/dabing-fangzisha-skill"
```

同名目录已存在时，Git 会报错。先检查已有文件，保留备份后再决定更新方式，不要直接删除旧目录。

### 方式二：导入 WorkBuddy 后调用

1. [下载 WorkBuddy 技能包](https://github.com/maomaoti1124-bot/dabingfangzisha/raw/refs/heads/main/dist/dabing-fangzisha-workbuddy.zip)，保存到本机。不要把整个软件目录重新压缩作为导入包。
2. 打开 WorkBuddy 的“专家·技能·连接器 → 技能 → 添加技能 → 上传技能”，选择这个 ZIP 文件。
3. 在“已安装”中确认技能已启用，在对话中选择该技能，或明确输入：

```text
请使用已安装的 dabing-fangzisha-skill（大冰防zisha skill），以温和、直接的方式陪我聊聊。
```

根据 [WorkBuddy 官方说明](https://www.codebuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Skills-Market)，对话搜索安装适用于技能市场，自定义技能使用上传导入。本项目没有声称已上架市场；导入包已做结构检查，尚未在你的 WorkBuddy 客户端完成实际导入验收。不同版本的入口名称可能有所变化。

包内仅包含对话规则和参考示例，不含 API Key。需要重新打包时，在仓库目录运行：

```sh
python3 scripts/build_workbuddy.py
```

### 方式三：运行接入 DeepSeek 的聊天软件

不需要安装 Codex 或 WorkBuddy。准备 Python 3.9 及以上版本、Git，以及 [DeepSeek 开发者平台](https://platform.deepseek.com/)提供的有效 API Key。API 使用受服务商的账户和计费规则约束。

在终端执行：

```sh
git clone https://github.com/maomaoti1124-bot/dabingfangzisha.git
cd dabingfangzisha
python3 server.py --ask-key
```

Windows 可将最后一行改为 `py server.py --ask-key`。本项目只使用 Python 标准库，无需运行 `pip install`。

随后：

1. 在**本地终端**输入 DeepSeek API Key，输入时不显示，应用不将其保存到文件。不要把密钥发送到聊天、Issue 或公开仓库。
2. 打开 [http://127.0.0.1:8787](http://127.0.0.1:8787)。检查页面上方显示密钥已配置，并确认页面说明。
3. 勾选了解数据发送方式后，输入文字并发送。网页会将本轮及当前上下文交给本地服务，再转发到 DeepSeek；不是离线聊天。

没有密钥也可以运行 `python3 server.py` 浏览页面，但不能获得模型回复。点击网页右上角“连接说明”查看配置方法。

默认模型为 `deepseek-flash`，接口为 `https://api.deepseek.com/chat/completions`，依据 [DeepSeek 官方 API 文档](https://api-docs.deepseek.com/zh-cn/)。可通过 `DEEPSEEK_MODEL` 环境变量选择账户可用的模型；密钥也可由 `DEEPSEEK_API_KEY` 环境变量提供。`.env.example` 只是示例，应用不会自动读取 `.env`。

端口被占用时运行 `python3 server.py --ask-key --port 8788`，再打开终端显示的地址。停止服务按 Ctrl + C。本原型仅监听 `127.0.0.1`，没有多用户登录和公共部署方案，不应直接开放到互联网。

### 常见问题

| 情况 | 处理方式 |
|---|---|
| 提示未配置 API Key | 在运行服务的终端用 `--ask-key` 重新启动，或设置 `DEEPSEEK_API_KEY` 后重启。 |
| 密钥无效、余额不足、服务繁忙 | 按页面提示检查 DeepSeek 账户或稍后手动重试，应用不会无限自动重试。 |
| 点击停止等待 | 只停止浏览器等待，服务端和供应商可能仍在处理，不能保证停止计费。 |
| 想清除聊天 | 点击“新对话”，或关闭/刷新页面。本应用不使用浏览器持久化保存历史；不能因此推断服务商也删除了数据。 |
| 对话过长 | 最多 20 轮、单条 6000 字符，请求体最多 128 KiB；超限会提示，不会静默截断已有上下文。 |
| 模型回复不合适 | 不将模型判断作为安全结论；联系现实支持。反馈时使用虚构或去标识化内容。 |

### 文件与检查

```text
SKILL.md                         Codex 入口，也是 DeepSeek 的服务端对话规则来源
agents/openai.yaml               Codex 界面信息
references/conversation-examples.md  虚构示例与参考来源
server.py                        仅本机可访问的 DeepSeek API 代理
web/                             聊天页面
scripts/build_workbuddy.py        WorkBuddy 打包脚本
dist/dabing-fangzisha-workbuddy.zip  WorkBuddy 导入包
tests/test_server.py             本地及模拟接口测试
```

运行检查：

```sh
python3 -m unittest discover -s tests -v
```

测试不会连接真实 DeepSeek API，也不证明模型能可靠识别危机或改善用户状态。Codex 安装位置与调用方式参考 [OpenAI 官方技能文档](https://learn.chatgpt.com/docs/build-skills)；WorkBuddy 导入结构参考 [WorkBuddy 开放平台](https://open.workbuddy.cn/docs/skill)。

## 为什么做这个项目

有些人在最难熬的时候，很难开口求助，也很难独自整理自己的处境。这个项目希望提供一个愿意倾听、认真回应的对话入口，让求助者有机会说出痛苦，先关注眼前的安全，再寻找可以一起面对困难的人。

我们的目标是帮助更多人获得支持，减少自杀或自伤的风险。我们不把“聊完就不再有这些念头”作为承诺，也不要求求助者马上振作或立即找到人生意义。

## 计划提供什么

- **倾听与回应：** 接住求助者表达的痛苦，减少指责、说教和空泛鼓励。
- **关注当下安全：** 出现当前自杀或自伤线索时，用简短、直接的提问了解是否有迫近危险或已经受伤。
- **支持具体行动：** 根据已知情况，帮助求助者联系可信任的人、减少接触危险物品，并寻找现实中的帮助。
- **衔接专业支持：** 鼓励需要帮助的人联系医疗或心理健康专业人员；迫近危险时优先联系当地急救或前往急诊。
- **支持身边的人：** 为关心亲友的人提供倾听、陪伴和协助求助的表达建议。

以上是设计目标，尚不代表当前版本已经实现或验证这些能力。

## 对话应如何进行

### 1. 先听懂对方正在经历什么

从用户已经说出的内容出发，认真回应其具体处境。不把痛苦归结为“想太多”“不够坚强”或“不懂感恩”，不急着用道理压过感受。根据上下文区分当下求助、过去经历、引用文本与一般讨论。

### 2. 有当前危险线索时，优先关注安全

直接、温和地询问必要信息，例如此刻是否安全、是否准备伤害自己、是否已经受伤或服药。每次只问少量关键问题，避免审问式提问和机械重复。

如果对方已经采取伤害行动、存在迫近危险，或表示无法保证当下安全，应优先引导其联系当地急救、前往急诊，并请现实中可信任的人陪伴。不要为了完成问答流程而延误求助，也不要让对方等待 AI 回复才行动。

### 3. 根据处境，一起寻找下一步

在倾听的同时，帮助对方选择此刻能做到的具体行动，例如给可信任的人发出求助信息、请人陪伴，或联系专业服务。对话可以继续，但不能让它成为现实支持的替代品，也不能要求对方一次完成一长串任务。

这个方向参考了 [NIMH 关于倾听、关注安全和连接支持的建议](https://www.nimh.nih.gov/health/publications/5-action-steps-to-help-someone-having-thoughts-of-suicide)，以及 [WHO 关于自杀预防与求助的说明](https://www.who.int/news-room/questions-and-answers/item/suicide)。这些资料支持一般原则，不构成本项目有效性的证明。

## 表达方式与人物边界

语言应直接、具体、温和，允许对方暂时没有答案。不使用羞辱、激将、道德绑架或“别人比你更惨”等比较，也不把生存责任强加到家人或其他人身上。

项目名称由创作者指定，不应被理解为大冰本人参与、授权或提供服务。即使借鉴已有素材中的表达特点，也应说明这是 AI 支持对话，不能冒充本人、编造他的原话，或套用未经核实的个案判断。

## 能力与使用边界

- AI 可能误解语境或遗漏危险线索，不能仅凭聊天判断一个人已经安全。
- 项目不提供诊断、用药建议或治疗，也不能替代急救、危机支持及专业服务。
- 不提供自杀或自伤的方法、比较、实施步骤或隐瞒伤情的建议。
- 不承诺“保证有效”“治愈”或“消除所有念头”。
- 求助资源须按用户实际所在地区核实；不能编造号码、服务时间或可用性，也不能默认某一地区的资源适用于所有人。
- 不声称已经报警、联系亲友或安排救援；只有具备相应工具、授权并确认成功后，才能报告真实完成的动作。

如果你此刻已经受伤、服药，或担心自己马上会伤害自己，请立即联系当地急救或前往急诊，并请可信任的人陪着你。不要等待这个项目更新或依赖 AI 对话处理迫近危险。

## 隐私

不要在公开 Issue、示例或测试材料中提交真实姓名、住址、联系方式、病历或未经同意的私人对话。反馈问题时使用虚构或充分去标识化的材料。

Skill 文件本身不能保证匿名、不留记录或端到端加密。数据如何处理取决于所使用的平台、模型服务和部署配置，使用前应阅读相应隐私说明。

## 后续需要完成的工作

- 使用真实 API Key 完成端到端联调，并在目标 WorkBuddy 客户端验证导入和调用。
- 补充适用场景、资源核实流程，以及遗漏危险线索时的处理边界。
- 用虚构案例检查当前求助、非紧急情绪困扰、亲友求助和引用文本等不同情境，避免误触发或忽略风险。
- 在面向真实危机用户前，寻求具备相关资质的专业人员审阅，并明确运营责任与人工支持安排。

欢迎提交具体、可复现且不含私人信息的改进建议。提出功能时，请同时说明它如何帮助用户，以及可能造成什么误解或风险。
