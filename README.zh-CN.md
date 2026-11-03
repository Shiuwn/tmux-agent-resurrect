# tmux-agent-resurrect

tmux-resurrect 配套插件：为每个 pane 保存 Codex / OpenCode 对话 ID，恢复布局时打开对应对话。同一目录的多个窗口也能恢复不同对话。

## 安装

依赖：tmux、Bash、Python 3.9+、ps、lsof，以及 [tmux-resurrect](https://github.com/tmux-plugins/tmux-resurrect)。已在 macOS 验证，Windows 下的 WSL 环境也已由用户验证可用。原生 Linux 环境尚未实机验证。Codex / OpenCode 应在登录 shell 的 PATH 中。

在新电脑上解压并安装：

```sh
mkdir -p ~/.tmux/plugins
tar -xzf tmux-agent-resurrect-0.2.0.tar.gz -C ~/.tmux/plugins
python3 ~/.tmux/plugins/tmux-agent-resurrect/install.py
```

如果尚未安装 tmux-resurrect，先执行：

```sh
git clone https://github.com/tmux-plugins/tmux-resurrect ~/.tmux/plugins/tmux-resurrect
```

安装脚本先备份 `~/.tmux.conf`，再添加托管配置块；检测到运行中的 tmux 时重新加载配置，不重启 pane。本目录可以放在任意位置，安装脚本自动记录路径。安装后请保留该目录。无 tmux 服务时，配置在下次启动时生效。

```sh
python3 install.py --config ~/.config/tmux/tmux.conf
python3 install.py --resurrect /path/to/tmux-resurrect
python3 install.py --no-reload
python3 install.py --uninstall
```

也可参考 `tmux.conf.example` 手动加载。使用 TPM 时先声明 `tmux-plugins/tmux-resurrect`，再声明 `Shiuwn/tmux-agent-resurrect`，将 TPM 启动行放在最后。安装脚本和 TPM 选择一种加载方式即可。

## 使用

1. 关机前按前缀键（默认 `Ctrl+b`），再按 `Ctrl+s` 保存。
2. 开机后运行 `tmux`，按前缀键，再按 `Ctrl+r` 恢复。

沿用 tmux-resurrect 的快捷键，不自动保存或开机启动。已有 pane 会跳过。对话历史可恢复，正在运行的命令和模型生成不会从断点继续。恢复不自动提交提示词，也不添加绕过权限的参数。

## 识别与存储

保存后置 hook 读取每个 pane 的进程树。

- Codex：读取 `${CODEX_HOME:-~/.codex}/state_*.sqlite`，用当前标题和目录唯一匹配；进程打开的 rollout 文件可辅助确认 ID。
- OpenCode：读取 `${XDG_DATA_HOME:-~/.local/share}/opencode/opencode.db`，用标题和目录匹配。如果标题只是 `OpenCode`，则读取当前右侧栏的标题区，处理换行和中文字符宽度。**保存时保持会话侧栏可见。**

快照中保存：

```sh
codex resume UUID -C '工作目录'
opencode --session ses_ID '工作目录'
```

识别依赖工具本地索引和终端界面格式，不是官方的 pane → session ID 接口。已验证当前机器上的 Codex 和 OpenCode 1.19.3；升级后应检查保存报告。重名、标题不可见或无法唯一确认的 pane 会恢复为空终端，并提示 `skipped`。为对话设置独有名称后再保存。脚本不按目录选择最近会话。

目录由 tmux-resurrect 的 `@resurrect-dir` 决定；默认通常是 `~/.local/share/tmux/resurrect/`，也可能是 `~/.tmux/resurrect/`。`last` 指向最近快照，旁边的 `.txt.codex.json` 列出 pane、工具、ID、目录和识别来源。插件只读工具会话索引，不修改对话或认证配置。

已有保存 hook 会先执行，再执行本插件。已有程序白名单保留。`@resurrect-processes=false` 仍禁用进程恢复；`:all:` 仍按原行为恢复所有程序。重复加载不重复添加 hook 或白名单。可在插件加载前指定解释器：

```tmux
set -g @agent-resurrect-python /path/to/python3
```

## 换电脑

**仅希望有同样功能：** 安装本插件、tmux-resurrect 和 Codex / OpenCode，并重新登录。新电脑创建的会话便可保存和恢复。

**还要继续旧电脑的对话：** 另外需要迁移 tmux 快照、项目文件及工具自己的会话数据。session ID 不包含对话内容。

先保存 tmux，再正常退出相关工具。SQLite 数据可能仍在 WAL 文件中，不要在进程写入期间只复制 `.sqlite` / `.db` 主文件。优先使用工具自身的导出、导入功能，或退出后完整备份对应数据，再按工具版本的迁移方式操作。安装脚本不会复制会话、认证文件或 API 密钥。

项目最好保持相同绝对路径，用户名变化也会影响路径。如果路径变化，需要调整 tmux 快照的 pane 目录、恢复命令中的目录，并确认工具会话能在新路径恢复。插件不自动改写旧路径或迁移对话数据库。先手动恢复一个对话，确认成功后再恢复全部窗口。

## 卸载与回滚

```sh
python3 /path/to/tmux-agent-resurrect/install.py --uninstall
```

卸载先备份配置，移除托管块；在当前 tmux 中恢复先前 hook，并移除本插件新增的白名单。配置中原有的 tmux-resurrect 和快照保留。安装时自动补充的 tmux-resurrect 加载行随托管块移除，卸载后若仍需它，请自行保留加载行。重启过 tmux 后，先前 hook 的恢复由原配置中的声明负责。

完整回滚可使用安装时输出的 `.tmux.conf.backup-...-agent-resurrect`。

## 验证与打包

```sh
python3 -m unittest -v test_codex_resurrect.py test_adapters.py test_plugin.py
python3 package.py
```

独立 tmux socket 测试覆盖带空格和引号的安装路径、重复安装、已有 hook 参数传递、白名单保留和卸载。另已用假命令验证混合恢复及重复恢复。压缩包仅包含显式列出的源码、测试、示例和说明，不包含本机配置、会话或密钥。


## 用户扩展（0.2.0）

默认自动加载 `adapters/codex.py` 和 `adapters/opencode.py`，无需额外配置。
用户适配器放在 `${XDG_CONFIG_HOME:-~/.config}/tmux-agent-resurrect/adapters/*.py`，
与内置适配器一起加载。更新插件不会覆盖该目录。只加载普通 `.py` 文件，忽略以 `_` 开头的文件。

```sh
mkdir -p ~/.config/tmux-agent-resurrect/adapters
cp /path/to/tmux-agent-resurrect/examples/example_agent.py ~/.config/tmux-agent-resurrect/adapters/my_agent.py
# 编辑 my_agent.py，填写实际进程名、会话查询方式和恢复参数。
python3 /path/to/tmux-agent-resurrect/scripts/configure.py --list
tmux source-file ~/.tmux.conf
```

示例是待修改的模板，`example-cli` 及其参数不是已验证的真实工具命令。
**先根据 CLI 的帮助或官方接口修改模板，再重新加载。**
每个文件导出一个 `ADAPTER`，无需改核心代码、白名单、安装卸载脚本或报告统计：

```python
from adapter_api import Adapter, Resolution

def resolve(ctx):
    # 实现查询：返回这个 pane 当前会话的真实 ID。
    # 无法确认或有歧义时返回 None，绝不选目录最近的会话。
    session_id = read_current_session(ctx)  # 用户自行实现
    return Resolution(session_id, "current-session-index")

ADAPTER = Adapter(
    name="my-agent",                         # 全局唯一的小写名称
    process_names=("my-agent",),              # 进程可执行文件的 basename
    session_id_pattern=r"session_[A-Za-z0-9_-]+",
    resume_argv=("my-agent", "--resume", "{session_id}", "-C", "{cwd}"),
    resolve=resolve,
)
```

`ctx` 包含 `pane_id`、`title`、`cwd`、`pids`（匹配到的进程 PID 元组），以及
`run(argv)`（30 秒超时、返回标准输出的命令调用方法）。可读取工具的本地状态接口、
会话索引或 hook 记录，但查询应保持只读。返回 `Resolution(None, "原因")` 会跳过该 pane。
从 CLI 启动后切换对话的情况也应正确处理，不要只相信进程原始参数。

恢复参数必须是字符串元组，`{session_id}`、`{cwd}` 必须各自占一个完整参数。
不写 shell 命令拼接；核心统一验证 ID 并转义参数。第一个占位符前的命令和选项
自动组成白名单，因此该部分只允许字母、数字、下划线、连字符，命令应位于 PATH 中。
例如上面的白名单为 `my-agent --resume`。卸载和移除适配器时，自动清理本插件新增的项。

新增或删除文件后重新加载 tmux 配置，使白名单同步更新。可用 `--list` 检查加载结果。
重复名称、错误元数据或语法错误会报告文件路径并拒绝加载，修正后再保存。
单个 resolver 抛异常、返回无效 ID，或同一 pane 匹配多个适配器时，跳过对应 pane；
其他 pane 继续保存。旧的 `.txt.codex.json` 报告文件名保留兼容，`tool` 字段写入适配器名称。

可通过 `AGENT_RESURRECT_ADAPTER_DIR` 添加其他目录（多个目录用系统路径分隔符连接）；
该环境变量需在 tmux 服务环境中设置。通常使用默认用户配置目录最简单。
自定义 `.py` 文件以本机用户权限运行，只安装自己信任的代码；示例不会自动启用。
打包脚本只收录内置适配器和示例，不会收录用户目录的扩展。
