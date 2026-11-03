# Blender 立体截面实验室

用一把可以移动、旋转的“平面刀”实时剖切立体，并显示真实截线。为立体截面题、空间想象训练和课堂演示而做。

- 六种内置模型：空心圆锥＋圆台、实心圆锥、圆柱、圆台、空心圆柱、正方体
- 四种一键实验：水平、过轴竖切、偏心竖切、斜切
- 三个连续控制量：刀的位置、倾角、水平转向
- 一键“正视截面”，避免把透视中的椭圆误认为真实截面
- 橙色表示实体材料，红色表示截线，青色网格表示刀面
- 无第三方 Python 依赖，不需要开启 Blender 全局自动运行脚本

已在 **Blender 5.2.4** 验证。脚本按 Blender 4.2+ API 编写，其他版本建议先运行文末自检。

## 方法一：一键启动（最简单）

### Windows

1. 下载并解压本仓库。
2. 双击 `启动截面实验室.cmd`。
3. Blender 打开后，在三维视图按 **N**，选择右侧 **“截面实验”** 标签。

启动器会依次查找本地路径配置、PATH 和默认安装目录。如果没有找到 Blender：

1. 复制 `blender_path.local.example.cmd`。
2. 将副本命名为 `blender_path.local.cmd`。
3. 把其中的 `BLENDER_EXE` 改成自己电脑上的 `blender.exe` 完整路径。

本地路径文件已被 Git 忽略，不会被提交或分享。

### macOS / Linux

在终端执行：

```sh
sh start_section_lab.sh
```

也可以先设置可执行文件路径：

```sh
BLENDER_EXE=/path/to/blender sh start_section_lab.sh
```

macOS 默认会尝试 `/Applications/Blender.app/Contents/MacOS/Blender`。

### 任意系统：手动启动

```sh
blender section_lab.blend --python section_lab_blender.py
```

## 方法二：安装为 Blender 插件

1. 从 Release 下载 `section-lab-addon.zip`。
2. 打开 Blender 的 **Edit → Preferences → Add-ons**。
3. 通过 **Install from Disk** 选择这个 ZIP，并启用“立体截面实验室”。
4. 在三维视图按 **N → 截面实验 → 创建截面实验室**。

插件会在独立场景中创建实验，不删除或覆盖当前场景。禁用插件不会影响已经创建的模型，但实时控制面板需要先启用插件。

## 建议的第一次实验

以“本题：空心圆锥＋圆台”为例：

1. 点 **①水平 → 正视截面**。刀的位置在 `0.8～1.65` 之间时，外圆锥产生外圆，空心圆锥产生内圆，橙色材料形成圆环。
2. 把位置升到 `1.65` 以上。刀已经越过空腔顶点，内圆消失，截面变为实心圆。
3. 点 **②过轴 → 正视截面**。外轮廓为五边形，中间必须保留三角形空白孔。
4. 点 **③偏心 → 正视截面**。刀避开中央空腔，但圆锥顶部变为曲线，不再是尖顶直线。
5. 切换圆柱、圆锥和圆台，分别过轴竖切，对照矩形、三角形和梯形。
6. 点 **④斜切**，每次只改变一个滑块，观察截线如何连续变化。

推荐练习方式：**先猜 → 再切 → 正视 → 用自己的话解释。**

## 控制说明

| 控制项 | 含义 |
| --- | --- |
| 刀的位置 | 平面沿自身法线的有符号距离；水平切割时可直观理解为高度 |
| 刀的倾角 | `0°` 为水平，`90°` 为竖直 |
| 水平转向 | 倾斜或竖直刀面的水平方向；水平刀时不起作用 |
| 剖开显示 | 去掉刀面正侧，露出内部材料与空腔 |
| 正视截面 | 从刀面法线方向正交观察真实截面 |
| 立体斜视 | 返回可旋转的三维观察状态 |

鼠标左键拖动旋转，滚轮缩放。

## 实现原理

这不是预先制作的动画。每次控制量变化时，程序都会：

1. 用 `bmesh.ops.bisect_plane` 计算网格与平面的真实交线。
2. 将交线连接为闭合轮廓。
3. 把轮廓投影到刀面局部二维坐标。
4. 根据轮廓包含关系调整绕向，用填充曲线表现实体区域和孔洞。
5. 可选择保留刀面一侧，形成剖开显示。

当前版本面向内置的闭合流形训练模型，不是通用 CAD 布尔工具。特殊相切、共面等情况应结合几何意义判断。

## 自检

无需安装测试框架，直接运行：

```sh
blender --background --factory-startup --python section_lab_blender.py -- --self-test
```

自检覆盖圆环面积、三角形空腔、圆柱矩形、圆锥三角形、圆台梯形、空心圆柱双矩形和正方体正方形。

重新生成场景文件：

```sh
blender --background --factory-startup --python section_lab_blender.py -- --build --self-test
```

## 文件说明

```text
section_lab.blend               可直接打开的现成场景
section_lab_blender.py           场景生成、实时求交、面板与自检
启动截面实验室.cmd              Windows 启动器
start_section_lab.sh            macOS / Linux 启动器
blender_path.local.example.cmd  Windows 本地 Blender 路径模板
```

## English

An interactive Blender plane-section lab for spatial-geometry learning. It includes six solids, live plane controls, cutaway display, exact section outlines and filled material regions with holes.

Quick start: open `section_lab.blend` with `section_lab_blender.py` using the command above, or install the Release add-on ZIP and choose **N → 截面实验 → 创建截面实验室**. No third-party Python packages are required.

## License

MIT，可自由使用、修改和分享，保留许可证即可。
