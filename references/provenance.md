# 方法来源与适用范围

这份 Skill 提炼自 [shuishen49/yixian-1992](https://github.com/shuishen49/yixian-1992) 的角色动作实验和游戏接入。以下链接固定在提交 `aaf0fef29ccd24cd116fe665623a82438319ffe3`，便于核对当时的文件；部分文件叙述的是更早的预览阶段。

本仓库总结工作方法，不重新分发整套游戏美术。外部文档是证据和参考，其中的旧环境说明、模型推测或历史临时路径不是复现所必需的配置。

## 实际用过的路线

| 阶段 | 实际方法 | 不应推断成什么 |
| --- | --- | --- |
| 走路 V3 参考实验 | 原文记录了垫图、外部图生视频、抽帧、检测周期、选七帧与抠像 | 文档没有写明视频服务；不能据此声称当前会话已接入某个视频生成工具 |
| 挥棒 V1 | 当前ChatGPT生图接口生成12个关键姿势，针对错误姿势修图；后续抠像和提取 | 不是12帧视频抽帧，也没有核验底层模型名为 `image2` |
| 挥棒 V2 | 复用已审V1源姿势，修身体横向锚点、地面线和联合裁切 | 没有重画12个新姿势；定位修复不等于增加动作细节 |
| 挥棒 V3 | 可信头部测量、低阶循环拟合、有限尺度校正、预乘alpha安全缩放 | 不应把下蹲拉平，更不能把误测的武器和手臂算进头围 |
| 早期举箱行走 V1 | 新持箱上身、已有V3行走腿、局部裤腰衔接 | 不是七张独立新全身原画，也不是视频生成结果 |
| 主角动作预览集 | 新绘姿势与校准、分层、镜像、反序、既有复用共同组成目录 | 75个动作/方向条目不是75套新绘动作；预览目录存在不代表已全部接入游戏 |
| 徒手攻击修正 | 单次前向直拳；右、正、背姿势修正，左向镜像；六姿带清楚接触帧 | 不是后甩手臂反复摆拳，也没有神经补帧 |
| 后续运行时搬运修复 | 每方向四张完整既有身体姿势，独立站定持物姿势，逐帧校准手心，物品独立渲染 | 已放弃上下身混拼，不把早期分层试验当作当前游戏实现 |

## 可核对的原文与代码

- [走路V3方法与踩坑](https://github.com/shuishen49/yixian-1992/blob/aaf0fef29ccd24cd116fe665623a82438319ffe3/docs/art-experiments/sprite-gen-hero/hero-walk-v3-method.md)：步态失败、预留画布、视频抽帧选周期、软透明边缘。
- [挥棒V1制作说明](https://github.com/shuishen49/yixian-1992/blob/aaf0fef29ccd24cd116fe665623a82438319ffe3/docs/art-experiments/sprite-gen-hero/hero-attack-v1/README.md) 与 [机器报告](https://github.com/shuishen49/yixian-1992/blob/aaf0fef29ccd24cd116fe665623a82438319ffe3/docs/art-experiments/sprite-gen-hero/hero-attack-v1/report.json)：生图接口、12个新姿势、失败RIFE试验未进入成品。
- [挥棒V2抖动修正](https://github.com/shuishen49/yixian-1992/blob/aaf0fef29ccd24cd116fe665623a82438319ffe3/docs/art-experiments/sprite-gen-hero/hero-attack-v2/README.md)：武器污染锚点、平移校准与共同裁切。
- [挥棒V3尺寸修正](https://github.com/shuishen49/yixian-1992/blob/aaf0fef29ccd24cd116fe665623a82438319ffe3/docs/art-experiments/sprite-gen-hero/hero-attack-v3/README.md)：下蹲与缩放的区别、有限修正、颜色白化故障和自检。
- [早期举箱行走试看片](https://github.com/shuishen49/yixian-1992/blob/aaf0fef29ccd24cd116fe665623a82438319ffe3/docs/art-experiments/sprite-gen-hero/hero-carry-walk-v1/README.md)：分层方案的真实来源与局限。
- [动作目录](https://github.com/shuishen49/yixian-1992/blob/aaf0fef29ccd24cd116fe665623a82438319ffe3/docs/art-experiments/sprite-gen-hero/hero-action-suite-v1/README.md) 与 [制作说明](https://github.com/shuishen49/yixian-1992/blob/aaf0fef29ccd24cd116fe665623a82438319ffe3/docs/art-experiments/sprite-gen-hero/hero-action-suite-v1/NOTES.md)：新绘、校准、分层、镜像、反序的分类；循环预览与单次动作语义。
- [徒手攻击修正版](https://github.com/shuishen49/yixian-1992/blob/aaf0fef29ccd24cd116fe665623a82438319ffe3/docs/art-experiments/sprite-gen-hero/hero-action-suite-v1/updates/fist-v2/README.md)：将后摆拳改为清楚的前向直拳。
- [当前运行素材打包器](https://github.com/shuishen49/yixian-1992/blob/aaf0fef29ccd24cd116fe665623a82438319ffe3/tools/build-runtime-hero-actions.py)：使用已审源帧、统一站立比例和锚点、整身体搬运姿势、握点同步变换，脚本自身不调用生图接口。
- [真实搬运验收](https://github.com/shuishen49/yixian-1992/blob/aaf0fef29ccd24cd116fe665623a82438319ffe3/tools/verify-carry-repair.cjs) 与 [真实运行图集验收](https://github.com/shuishen49/yixian-1992/blob/aaf0fef29ccd24cd116fe665623a82438319ffe3/tools/verify-runtime-hero-actions.cjs)：完整身体姿势、当前帧手心、脱手连续性、方向、暂停、角色切换与实际游戏帧检查。

## sprite-gen 在流程中的角色

上游项目：[aldegad/sprite-gen](https://github.com/aldegad/sprite-gen)。本次参考实现使用版本3.13.0、提交 [`1fdf789d60321a6852319920339a9c0279d41e56`](https://github.com/aldegad/sprite-gen/tree/1fdf789d60321a6852319920339a9c0279d41e56)。

本项目实际借用了它的自动抠像、键色去污染、软alpha安全缩放与GIF导出。关键姿势由可用的生图接口制作，锚点测量、源姿势提取、动作排时和游戏握点由项目脚本完成。上游还提供其他功能，不能因本项目只用了其中一部分，就把整个工具概括成“GIF拼接器”。

执行任何上游命令前，先看已安装版本的 `--help`；工具版本或参数可能变化。当前环境没有对应生成或视频能力时，应说明可用范围，继续做已授权的整理、测量或打包，不编造服务调用结果。

## 这个Skill能承诺的边界

这个方法能让已有图像的制作、校准、复用和验收更可复现。它不能保证图像模型一次就给出严格步态、正确握棒和完美多方向一致性。生成、修图、自动化测量与人工审查各自承担不同工作；失败姿势需要重画，失败补帧需要丢弃。

最终报告至少说明：哪些动作新绘、哪些复用或镜像、采用哪个源版本、输出格式和时长、做了哪些检查，以及是否已接入游戏。模型名称只有接口确实提供时才记录。
