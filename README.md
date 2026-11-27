# imagepool

**独立共享的图片生成 provider 池**（node module 语义）——多 provider 顺序消费 + 轮转 + 配额兜底。
与文本生成完全解耦：只认 `spec / data / io`，不认识任何业务域（不认识「旅游 / 角色 / 千面」）。

本文档目标：**不读源码即可完成「使用 / 集成 / 发布」**。
源码级契约另有测试锁定：`tests/test_api_signatures.py`（签名）+ `tests/test_readme_reference.py`（本文档）。

---

## 1. 定位

通用图片能力仓：**provider 池 + 词引擎 + 画面组装 + 工艺 + 编排 + MCP**。
覆盖「**文生 + 图生图**」「**人像 + 空镜**」四象限。零第三方依赖（核心）；只认 `spec / data / io`。

- **池子语义**：多 provider **顺序消费**（`pool_order` 声明顺序优先 → 未耗尽者兜底）
  + **轮转**（`rr=True`，`_rr_next` 整型索引指向下一起点）
  + **配额兜底**（401/配额类错误自动置 `exhausted` 跳过，运行态落盘）。
  `pool_order` 为空 = 全按 `providers` 声明顺序。
- **与文本生成无关**：英译等 LLM 能力一律由调用方经 `io.translate_backend` 回调注入，
  本仓不含任何 LLM 客户端、不读任何业务文件。
- **双通道**：**生图**（prompt → provider 出图）与 **检索**（`imagepool.scenic`：YAML 配置 → chain →
  provider → 候选归一化 → 下载/验货）并列，见 §4.5。

## 2. 安装

```bash
pip install -e .          # 核心（零第三方依赖）
pip install -e ".[dev]"   # + pytest
pip install -e ".[mcp]"   # + MCP（mcp>=1.0,<2）
pip install -e ".[scenic]"# + scenic 检索通道（pyyaml）
```

不发 PyPI，按 git tag 锁定版本：

```bash
pip install "imagepool @ git+https://github.com/jasonjkj/imagepool.git@v0.4.6"
```

- `requires-python = ">=3.11"`。
- **MCP 为可选依赖**：未装 `mcp` 时，核心库与 CLI 照常工作，仅 `imagepool-mcp` 入口不可用。

## 3. 用法 / CLI

### 3.1 入口（`pyproject.toml` `[project.scripts]`）

| 入口 | 命令 | 定义 | 说明 |
|---|---|---|---|
| console script | `imagepool` | `imagepool.__main__:main` | 出图 / 池管理 |
| console script | `imagepool-mcp` | `mcp_server:main` | stdio MCP server（需 `[mcp]`） |
| 模块 | `python -m imagepool` | 同上 CLI | 不依赖已安装 console script，直接跑工作树 |
| 库 | `import imagepool` | 见 §4 | 进程内调用 |

> `python3 x.py`（脚本文件形式）会优先解析**已安装包**而非工作树；跑工作树务必
> `python -m imagepool` 或设 `PYTHONPATH=<repo-root>`。

### 3.2 CLI 参数

`python -m imagepool --help`：

| 参数 | 说明 |
|---|---|
| `--config PATH` | **必填**，主配置 JSON（`pool_order` + `providers`） |
| `--runtime PATH` | 运行态 sidecar JSON（缺省不落盘） |
| `--out-dir DIR` | 落盘目录（缺省 cwd） |
| `--prompt-file PATH` | craft 模板文件（池层不校验内容） |
| `--size {portrait,landscape,square}` | 尺寸档，缺省 `square` |
| `--provider NAME` | 强制指定 provider（跳过轮转） |
| `--n N` | 张数（缺省 1） |
| `--rr` | 轮转模式（从上次成功者的下一家起步） |
| `--negative TEXT` | 负向词 |
| `--list-providers` | 列出池子顺序与用量 |
| `--state` | 池子运行态（调用/成功/最后使用） |
| `--reset-provider` | 重置所有 provider 的 `exhausted` |
| `--mark-exhausted NAME` | 把指定 provider 标记为已耗尽 |
| `--dry-run` | 只预览 provider，不调接口 |

退出码：`0` 成功 / `1` 出图失败（全池无图）/ `2` 用法或配置错误。

### 3.3 最小示例

```bash
# 配置（只写 api_key_env 环境变量名，真实 key 放环境，绝不下库）
cp config.example.json config.json
cp runtime.example.json runtime.json

# 查看池子顺序与用量
python -m imagepool --config config.json --runtime runtime.json --list-providers

# 离线预览（不调接口、不用真 key）
python -m imagepool --config config.json --dry-run

# 出一帧
python -m imagepool --config config.json --runtime runtime.json \
    --prompt-file /tmp/craft.txt --size portrait
```

```python
import imagepool

cfg = imagepool.load_config("config.json", runtime_path="runtime.json")
result = imagepool.generate("一段成品提示词", cfg, config_path="config.json",
                            runtime_path="runtime.json", size="portrait")
# → {"urls": [...], "provider": "ark", "model": "...", "local": ".../xx.png"}
# 或 {"error": "所有 provider 均失败", "details": [...]}
```

### 3.4 MCP

`imagepool-mcp`（stdio）。出图工具需要一个池配置：由 `IMAGEPOOL_CONFIG` 指向，或按调用传 `config_path`；
落盘目录取 `IMAGEPOOL_OUT_DIR`（缺省 cwd）。未提供配置时抛清晰错误，不静默。

工具面（`mcp_server.py`）：

| 工具 | 签名 | 说明 |
|---|---|---|
| `imagepool_build_craft` | `(spec_json, data_json="")` | 由 spec（JSON）组装 craft 文本（纯函数，不出图） |
| `imagepool_generate` | `(prompt, config_path="", images_json="")` | 直接走池子出一张图；`images_json` 传输入参考图（图生图） |
| `imagepool_render` | `(spec_json, data_json="", io_json="", config_path="")` | 组装 + 一站式出图（真实消耗池子） |

## 4. API / 模块参考

### 4.1 顶层公共 API（`imagepool/__init__.py` 再导出）

```python
# 池子
load_config(config_path, runtime_path=None) -> dict        # 主配置 + 可选运行态合并视图
save_config(cfg, config_path=None, runtime_path=None)      # 拆分落盘（静态→主配置，运行态→runtime）
generate(prompt, cfg, config_path=None, runtime_path=None, out_dir=".",
         size="square", n=1, negative="", force_provider=None, rr=False,
         images=None) -> dict                              # 顺序消费池出图
ordered_active_providers(cfg) -> list[dict]                # pool_order 优先 → 未 exhausted 兜底
save_image(url, provider, out_dir, name_hint=None) -> str | None   # http(s) 下载 / data URI 直写
to_data_uri(src) -> str                                    # 本地路径 → data URI（图生图输入归一化）

# 组装 / 工艺 / 编排
build_craft(spec, data=None) -> str                        # 组装 + 上戳（纯函数）
generate_image(craft_text, io=None, mode="person") -> dict # 门禁 +（可选）英译 + 池子
render(spec, data=None, io=None) -> dict                   # = generate_image(build_craft(spec, data), io)
ShotSpec                                                   # 画面参数契约（§4.4）
```

> **v0.4.0 破坏性变更（2026-10-18）**：`imagepool.engines`
> （expression / pose / framing / wardrobe / face）与默认池 `data/*.default.json` **已移除**。
> **共享库不内嵌业务内容**——景别池 / 锁脸锚句改为调用方注入：
> `compose_prompt(..., framing_pool=<业务池>, anchor_picker=<业务锚句函数>)`。

**`generate` 返回结构**：成功 `{"urls": [...], "provider": ..., "model": ..., "local": "/abs/path.png"}`；
全败 `{"error": "所有 provider 均失败", "details": [...]}`。图生图时仅保留支持输入图的 provider（当前 `ark`）。

**`craft.*` / `compose` 等非顶层导出**（经子模块访问）：

```python
from imagepool.craft import gate, split, translate
from imagepool import compose

# 门禁（validate 支持 rules 覆盖；空镜用 gate.SCENE_RULES）
gate.validate_craft_prompt(text, rules=None) -> (bool, str)
gate.assert_craft_or_die(text, *, allow_raw=False, rules=None) -> str   # 不合法抛 SystemExit
gate.extract_negative(text) -> str | None
gate.strip_stamp(text) -> str          # 去 "# imagepool-craft-v1" 戳
gate.with_stamp(text) -> str           # 上戳
gate.found_sections(text) -> set       # 已出现的【节】名集合
# 常量：gate.REQUIRED_SECTIONS / gate.CRAFT_STAMP / gate.SCENE_REQUIRED_SECTIONS / gate.SCENE_RULES

# 拆段 / 派生（变体图零 LLM 路径）
split.split_craft(text) -> dict        # {节名: 内容}；缺必需节（非 craft 结构）→ {}
split.build_variant_craft(base_secs, background, subject, picture,
                          size="portrait", negative="") -> str
split.build_hint_craft(base_secs, kink, layer, size="portrait", banned=None,
                       mapping=None, negative="", seed=None) -> str    # mapping 由调用方注入（无文件 IO）
split.build_explicit_craft(base_secs, kink, size="portrait", negative="") -> str

# 整篇英译（backend 回调注入；mode="none" = 空镜，不注女性锚）
translate.translate_craft_en(craft_text, backend=None, timeout=120,
                             mode="person") -> (str | None, str)

# 画面组装（景别池 / 锚句全注入，仓内无默认池）
compose.resolve_framing(spec, framing_pool=None, ref_tag_lookup=None) -> (dict | None, str)
compose.compose_prompt(spec, framing_pool=None, ref_tag_lookup=None,
                       anchor_picker=None) -> (prompt, shot_phrase, shot_src)
# shot_src ∈ {"override", "context", "neutral"}
# anchor_picker: (has_ref, has_pose_block, has_shot) -> str；缺省 None = 不写锚句
```

**协议层**（`imagepool.protocols`）：

```python
CALL_MAP            # {"qwen", "doubao", "ark", "sensenova", "agnes"} → call_* 函数
DEFAULT_SIZE_MAP    # {"portrait": "2048x2048", ...}（各 provider size_map 缺省兜底）
IMAGE_INPUT_PROVIDERS   # {"ark"}（支持图生图的 provider 集合）
supports_image_input(name) -> bool
# 各 call_*(p, prompt, size, n=1, negative="", images=None) -> {"urls"/"error", ...}
```

### 4.2 `spec` — 做什么图（`ShotSpec`，dataclass）

| 字段 | 类型 | 缺省 | 说明 |
|---|---|---|---|
| `expression_block` | `str` | **必填** | 上游渲染好的表情段（本层只接收拼好的文字） |
| `context_sentence` | `str` | **必填** | 背景情境句 |
| `ref_image` | `str \| None` | `None` | 人物参考图（**只查景别 tag + 脸锚句，不吃像素**） |
| `shot_override` | `str \| None` | `None` | 手动景别档名/id（显式 > 参考图派生标 > 泛化锚） |
| `scene_image` | `str \| None` | `None` | 真景图路径（`None` = 纯文字背景） |
| `mood` | `str \| None` | `None` | 情绪（预留持有，compose 当前不消费） |
| `pose_block` | `str \| None` | `None` | 上游姿势引擎 roll 好的短语；`None` = 不写【姿势】 |
| `pose_strategy` | `str` | `"anchor_ref"` | 姿势策略名 |
| `persona_dir` | `str \| None` | `None` | 参考图 persona 目录（供 `ref_tag_lookup` 回调） |
| `outfit_block` | `str \| None` | `None` | 上游渲染好的穿着段（业务块） |
| `kink_block` | `str \| None` | `None` | 上游渲染好的情趣段（业务块） |
| `style` | `str \| None` | `None` | 画风串（业务块；`None` = 用仓内默认） |
| `subject` | `str` | `"person"` | `person` / `none`（空镜，无主体） |
| `input_images` | `list[str] \| None` | `None` | 喂模型的图源（图生图：本地路径 / http(s) / `data:`）；与 `ref_image`/`scene_image` 语义分离 |
| `size` | `str` | `"portrait"` | `portrait` / `landscape` / `square` |

### 4.3 `data` — 领域内容（业务提供，仓只消费）

```python
data = {
  "pools": {"framing": [...], "pose": [...], "expression": {...}},  # 业务池（由调用方注入）
  "templates": {"合规": "...", "风格": "...", ...},                 # 分节模板（仓带生产默认，可覆盖）
  "negative": "...",                                                # 全局负向
  # 其余业务词表（wardrobe / craft_rules / kink / props 等）按算法需要注入
}
```

### 4.4 `io` — 外部能力（业务注入的可变/有副作用的东西）

```python
io = {
  "generate": callable,           # (prompt, negative=, images=?) -> dict；出图函数（必需）
  "translate_backend": callable,  # (craft_text, system_prompt) -> str | None；None = 跳过英译
  "images": list,                 # 图生图输入图（本地路径 / http(s) / data:）
  "craft_rules": dict,            # 门禁规则覆盖（空镜可传 gate.SCENE_RULES）
  "out_dir": str,                 # 落盘目录
  "ref_tag_lookup": callable,     # (ref_image, persona_dir) -> 景别标；None = 不查
}
```

**红线一句话**：imagepool 只认 `spec / data / io`，不认识任何业务域。

### 4.5 scenic 检索通道（`imagepool.scenic`，与「生图」通道并列）

仓内两条 provider 通道：

| 通道 | 方向 | 入口 | 依赖 |
|---|---|---|---|
| 生图 | 文本 prompt → provider 出图 | `imagepool.generate` / `render` | 零第三方依赖 |
| **检索** | YAML 配置 → chain → provider → 候选归一化 → 下载/验货 | `imagepool.scenic.engine` | `pip install imagepool[scenic]`（仅 YAML 解析需 `pyyaml`） |

```python
from imagepool.scenic import engine

cfg = engine.load_config()                  # 缺省路径：SCENIC_CONFIG → IMAGEPOOL_SCENIC_CONFIG → 无（返回 {} 走默认链）
for cand in engine.iter_candidates("kyoto temple", ctx, cfg):   # 按 chain 顺序、fail-isolated
    path, kept = engine.acquire(cand, dst, ctx, cfg)            # 下载 → 可选验货 hook
engine.resolve_verify(cfg)                  # 验货 hook callable | None（看不了就不验货，放行）
```

- **模块**：`engine`（链式引擎：`load_config` / `iter_candidates` / `acquire` / `resolve_verify` / `download` /
  `resolve_entry` / `default_config_path`）+ `sources`（内置源 `builtin:bing` / `builtin:pexels` / `builtin:local_dir`）
  + 契约 `Candidate` / `ScenicError` / `ConfigError` / `ProviderError`。
- **配置语义**：`chain`（provider 优先级）/ `limit`（每 provider 候选上限）/ `providers.<name>.{enabled,entry,options}` /
  `hooks.verify`；配置缺失或损坏 → 回落默认链 `[bing, pexels]`，不阻塞调用方。
- **`yaml` 惰性 import**：只在 `engine.load_config()` 内 import——未装 `[scenic]` 时
  `import imagepool.scenic` 与不出图的其余能力照常可用（`load_config` 才会因缺 pyyaml 抛错，
  文件不存在则直接返回 `{}`）。
- **无宿主假设**：核心不读 `.env`、不翻译、不碰宿主目录；密钥（`PEXELS_API_KEY`）/ 落库根 / 条数 / 验货 hook
  全由配置与 `ctx` 注入。

## 5. 集成方式

本仓按 tag 被下游消费，契约面 = 顶层导出 + `ShotSpec` + `pool.generate` + CLI/MCP 入口。
任何一处变更都必须 bump version + 打新 tag（见 §6）。三种集成方式：

- **库调用（推荐）**：`import imagepool`，用 `build_craft` / `generate` / `render` 组合业务逻辑；
  业务词表、模板、英译 backend 一律经 `data` / `io` 注入，仓内不内嵌业务内容。
- **CLI**：`python -m imagepool --config ... --prompt-file ...`，适合脚本/batch 出图。
- **MCP**：`imagepool-mcp`，适合 Claude / WorkBuddy / 任意 MCP 客户端直接调用。

**导入纪律**：下游若把本仓作为可选能力，建议**函数内惰性 import**（顶层不做 `import imagepool`），
底层缺包时不拖垮整个业务域的 import 期。

**版本锁定**：下游在 `requirements.txt` 用 `imagepool @ git+https://github.com/jasonjkj/imagepool.git@vX.Y.Z`
按 tag 锁定，避免吃到未发布变更。

## 6. 版本 / 发布

**node module 分发**：按 annotated tag 锁版本，不发 PyPI。改公开契约（入口 / `ShotSpec` /
`pool.generate` / 引擎签名 / CLI 参数 / MCP 工具）**必须**发新 tag。

**发版步骤**：

```bash
# 1. bump 版本号（pyproject.toml [project].version）
# 2. 更新 README 状态行与测试期望
# 3. 冒烟全绿（见 §8）——未全绿不许提交
python3 -m pytest tests/ -q
export PYTHONPATH="$PWD"
python3 -m imagepool --help && python3 scripts/mcp_smoke.py

# 4. 提交（中文 message）
git add -A && git commit -m "chore: imagepool vX.Y.Z（...）"

# 5. 打 annotated tag + 推送
git tag -a vX.Y.Z -m "imagepool vX.Y.Z"
git push origin main
git push origin vX.Y.Z
```

## 7. env 变量表

| 变量 | 归属 | 作用 | 缺省 |
|---|---|---|---|
| `api_key_env`（**配置字段**，非环境变量本身） | 池配置 | 每个 provider 声明的环境变量名；真实 key 从 `os.environ` 读。空 = 该 provider「未配置」（`call_*` 返回 error，不置 `exhausted`） | 无 |
| `IMAGEPOOL_CONFIG` | MCP | 出图池配置路径（`--config_path` 未传时用） | 无（未设且未传 → 抛清晰错误） |
| `IMAGEPOOL_OUT_DIR` | MCP | 落盘目录 | `.`（cwd） |
| `SCENIC_CONFIG` | scenic 检索通道 | 链配置文件路径（优先级最高） | 未设 → 看 `IMAGEPOOL_SCENIC_CONFIG` |
| `IMAGEPOOL_SCENIC_CONFIG` | scenic 检索通道 | 链配置文件路径（次选） | 未设 → 无默认配置（`load_config()` 返回 `{}`） |
| `PEXELS_API_KEY` | scenic `builtin:pexels` | pexels 源密钥（也可用 provider `options.api_key`） | 未设 → pexels 源返回空候选（跳过） |

`api_key_env` 契约（脱敏红线）：**仓库任何文件禁止出现真实 API key**；配置只存环境变量名，
真实 key 从环境读、不进配置体 / 日志 / 文档。示例见 `config.example.json`。

## 8. 测试

**全 mock，零真网、零真 key**（patch `imagepool._net._post_json` / `_get_bytes`）。

```bash
python3 -m pytest tests/ -q          # 仓根运行；全部离线
```

覆盖矩阵：

| 层 | 测试文件 | 断言点 |
|---|---|---|
| 协议 | `test_protocols.py` | 各 provider 响应解析 + exhausted 分类 + 图生图 payload |
| 池 | `test_pool.py` | 顺序消费 / 轮转推进 / exhausted 跳过 / 全败 / force / images |
| 配置 | `test_config.py`、`test_config_contract.py` | 主配置+runtime 拆分 / 未知键报错 / `api_key_env` 契约 |
| 落盘 | `test_storage.py` | data URI 直写 / URL 下载 / 后缀识别 / 输入图归一化 |
| 组装 | `test_compose.py`、`test_orchestrator.py` | 冲突守卫 / 分节模板 / 空镜 / input_images 透传 |
| 工艺 | `test_gate.py`、`test_translate.py`、`test_split.py` | 缺节拒绝 / 英译格式还原 / 派生结构 |
| 契约 | `test_public_api.py`、`test_api_signatures.py`、`test_contract.py` | 导出面 / 签名锁定 / `ShotSpec` 字段 |
| 入口 | `test_cli.py`、`test_cli_entry.py`、`test_e2e.py`、`test_mcp_smoke.py` | CLI 各分支 / console script 映射 / craft 全链 e2e / MCP 冒烟 |
| 文档 | `test_readme_reference.py` | README 自包含（章节 / 符号 / 无 dev 绝对路径） |
| 检索 | `test_scenic.py` | 配置解析 / 缺省路径语义 / 链顺序与启停 / 失败隔离 / 下载 magic 闸门 / 验货 hook |

## 9. 边界 / 已知缺口

- **真出图不纳入硬门槛**：走 provider 端点 + 真 key + 网络无法离线复现；离线只验证
  「配置装载 + 池排序 + 参数解析 + 组装/编排契约」。真出图验证由调用方 / 线上负责。
- **图生图仅 JSON 内嵌**：本期只支持把图放进 JSON payload 的 provider（`ark`/Seedream）；
  需 multipart `/images/edits` 的 provider 不支持；不做 mask / inpainting / 局部重绘。
- **不做**：多 provider 并发 / 预热（顺序消费足够）、连续多帧 / 视频 / seq 生成。
- **MCP `--help` 不受支持**（FastMCP stdio 入口不解析参数）→ 入口存活改用
  `scripts/mcp_smoke.py` + EOF stdin 检查。
- **console script 指向已安装版本**：工作树为最新时，`imagepool` / `imagepool-mcp`
  console script 可能指向已安装旧版；跑工作树须 `python -m imagepool` 或 `PYTHONPATH=<repo-root>`。

---

## 设计原则

- **可配置化**：provider 池、顺序、尺寸映射、协议全走配置文件，引擎不写死 provider。
- **独立**：独立仓库 + pip 包，不绑定任何宿主项目目录。
- **兼容通用**：兼容多协议响应格式（OpenAI 兼容 / qwen / sensenova / ark），统一返回结构。
- **可复用**：顶层 `generate` / `render` 与 CLI / MCP 入口可直接被任意业务引用。
- **机制进仓、内容注入**：仓内只放算法与结构（池子 / 引擎 / 组装骨架 / 工艺算法 / 编排骨架）
  + 生产默认；领域内容（词池正文、模板、kink 词表、角色卡）一律可经 `data` 覆盖。
- **可单用**：池子、任一引擎、组装层各自可独立调用；引擎/组装为可选子模块。

## 实现目的

1. **出图频率高，单 provider 不可靠**：一场戏多次出图（场景/暗示/明示/示意图），
   单 provider 遇配额耗尽或 key 失效即断档。池化按顺序消费 + 自动换家兜底。
2. **迁移线上验证过的行为基准**：已验证的 5 家顺序消费池（`call_*` 协议、`_rr_next` 轮转、
   exhausted 跳过、usage 记账）原样迁移，只改接线（requests→stdlib、路径→参数化），不重写不仿写。
3. **跨项目复用**：同一语言共享一份出图池，避免多方各维护一套。

## 脱敏约束

仓库任何文件（含 README / 示例 / 单测）**禁止出现真实 API key**；配置只存 `api_key_env`，
真实 key 从环境变量读、不进配置体/日志/文档。示例见 `config.example.json`。

## 状态

> **实现完成**（基线 2026-10-12；craft 扩展 2026-10-13，v0.2.0；img2img + person-optional 2026-10-14，
> v0.3.0；F1 副本清除 2026-10-18，v0.4.0；scenic 检索通道 v0.4.5）。

## 进度

- [x] 仓库初始化（git init）
- [x] 协议层（`protocols.py`：qwen/doubao/sensenova/agnes/ark）
- [x] 池逻辑（`pool.py`：顺序消费 + 轮转索引 + exhausted + usage）
- [x] 配置/运行态（`config.py`：主配置 + runtime 拆分，路径参数化）
- [x] 落盘（`storage.py`：URL/data URI）
- [x] CLI（`__main__.py`）
- [x] 单测（tests/ 全 mock）
- [x] craft 扩展（v0.2.0）：词引擎 + compose + 门禁/英译/拆段 + 编排 + MCP
- [x] 四象限补位（v0.3.0）：图生图输入（`images`/`input_images`/`images_json`）+ 空镜（`subject="none"`）
- [x] scenic 检索通道（v0.4.5）：`imagepool.scenic.engine` 链式检索 + 内置源 + 验货 hook
- [x] 公开 API 签名 + README 参考面锁定（`tests/test_api_signatures.py` / `test_readme_reference.py`）

## 变更记录

- **v0.4.0（2026-10-18）** — F1 副本清除：移除 `engines/`
  （expression / pose / framing / wardrobe / face）与 `data/*.default.json` 默认池——业务特质
  内容不内嵌共享库，单一真源 = 调用方业务层。
  - `compose.compose_prompt` 增 `anchor_picker=None`（锚句注入；缺省不写锚句）。
  - 景别机制内联 `compose._lookup_shot`（`framing_pool` 注入池纯查表，无池静默回退）。
  - `orchestrator.render` 透传 `data["anchor_picker"]`。
