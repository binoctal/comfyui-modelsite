# Modelsite for ComfyUI

在 ComfyUI 里使用 [Modelsite](https://modelsite.ai) 模型目录的视频与图像生成节点。

- **一个 API Key 就够。** 不需要 comfy.org 账号、不消耗 Comfy 积分、没有登录闸门。
- **模型列表自动更新。** 目录里上了新模型，刷新页面就能在下拉框里看到，不必等 ComfyUI 发版。
- **节点很朴素。** 文生视频、图生视频、文生图、图生图，输出直接接 ComfyUI 自带的 `Save Video` / `Save Image`。

## 安装

在 ComfyUI Manager 里搜索 **Modelsite**；或者手动安装：

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/binoctal/comfyui-modelsite
```

重启 ComfyUI。本包没有额外的 Python 依赖。

## 设置 API Key

在 Modelsite 控制台获取 Key（形如 `sk-ms-...`），然后二选一：

1. 打开 ComfyUI 的 **Settings → Modelsite → Connection**，把 Key 粘贴到 **API key**。Key 只保存在你本机，**不会写进工作流，也不会写进生成的文件**；
2. 或者启动 ComfyUI 之前设置环境变量 `MODELSITE_API_KEY`。

默认 API 地址是 `https://api.modelsite.ai`。只有拿到了别的地址时才需要改：在同一个设置页里改，或设置 `MODELSITE_BASE_URL`。

## 节点

所有节点在 **Modelsite/Video** 与 **Modelsite/Image** 分类下（在画布上双击，搜索 "Modelsite"）。

| 节点 | 作用 |
|---|---|
| Modelsite Text to Video | 提示词 → 视频 |
| Modelsite Image to Video | 首帧（可选尾帧）→ 视频 |
| Modelsite Text to Image | 提示词 → 图片 |
| Modelsite Image to Image | 1–3 张参考图 + 提示词 → 图片 |

视频节点输出 `video`、`task_id` 和 `usage`（接口返回的用量数据，本包不自己计算价格）；图像节点输出 `image` 和 `usage`。

### 模型

`model` 下拉框在页面加载时从在线目录取得。本包目前会调用的家族：

| 家族 | 视频 | 图像 |
|---|---|---|
| Seedance 2.0 / 2.0 mini | 文生、首帧、首尾帧 | — |
| Wan 2.7 | 文生、首帧、首尾帧 | — |
| HappyHorse 1.0 / 1.1 | 文生、首帧 | — |
| MiniMax H3 / H3 Max | 文生、首帧、首尾帧 | — |
| Seedream 4.0 / 4.5 / 5.0 lite | — | 文生、参考图 |

目录里在你加载页面之后才上架的模型，可以立刻使用：把模型 id 填到 **custom_model**（它会覆盖下拉框），或者刷新页面。

### 值得知道的参数

- **resolution**：Wan 和 HappyHorse 只接受 `720p` / `1080p`；Seedance 支持 `480p` / `720p` / `1080p`；MiniMax H3 是 `768p`（H3 Max 另有 `480p`）。不支持的取值会在发出任何请求之前就被拒绝。
- **duration**：Seedance 4–15 秒，Wan 2–15 秒，HappyHorse 3–15 秒，MiniMax H3 4–15 秒（H3 Max 5–15 秒）。
- **seed**：`-1` 表示由模型决定。默认的 `control after generate = randomize` 会让每次运行都不同，这对按次计费的 API 节点正是想要的（否则 ComfyUI 会直接复用缓存结果）。
- **generate_audio** 只对 Seedance 有效；**negative_prompt** 只对 Wan 和 HappyHorse 有效，其他模型会忽略。
- **HappyHorse 图生视频** 只支持首帧，连了尾帧会报错。
- 暂不支持参考**视频和音频**（需要上传步骤）。

## 安全行为

- **每个任务只创建一次。** 请求发出后失败、等待超时、或者你点了取消，本包都**不会**再次创建同一个任务，因为重复创建可能被计费两次。错误信息里带有任务 id，方便你在用量日志里查询。
- 等待时使用退避轮询，可以用 ComfyUI 的取消按钮中断。
- 接口返回的错误信息原样显示；你的 Key 会从所有错误信息和日志里被移除。
- 结果链接是有时效的签名地址：本包会立刻下载文件，并且绝不会把你的 Key 发给这些地址。

## 配置一览

| 项目 | 设置页 | 环境变量 | 文件 |
|---|---|---|---|
| API Key | Modelsite → API key | `MODELSITE_API_KEY` | `user/modelsite/config.json`（权限 600） |
| API 地址 | Modelsite → API base URL | `MODELSITE_BASE_URL` | 同上 |
| 配置目录 | — | `MODELSITE_CONFIG_DIR` | — |

优先级：本次会话在设置页里设置的值 > 环境变量 > 文件。

## 示例

`examples/` 里有四个现成的工作流（把文件拖到画布上即可）。图像类工作流用的是 ComfyUI input 目录里自带的 `example.png`，请换成你自己的图片。

## 开发

```bash
pip install pytest pytest-asyncio aiohttp pillow numpy
pytest          # 对本地的 API 假服务器运行；把 PYTHONPATH 指向 ComfyUI 源码目录可以同时跑节点 schema 测试
```

## 许可证

MIT
