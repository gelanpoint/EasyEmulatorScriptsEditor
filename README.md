# 屏幕自动化工具

基于Python的安卓模拟器自动化工具，支持MuMu等主流模拟器，提供图像识别、条件判断等高级功能。

## 功能特性

- 通过ADB控制模拟器
- 屏幕截图和图像识别
- 支持变量和条件判断
- 任务队列和循环执行
- 可扩展的插件系统

## 安装依赖

```bash
pip install opencv-python pillow pytesseract numpy
```

## 快速开始

1. 确保已安装ADB并配置好模拟器连接
2. 修改`config/settings.json`中的设备ID
3. 编写您的任务配置到`config/tasks.json`
4. 运行主程序：
```bash
python main.py
```

## 配置说明

- `adb_path`: ADB可执行文件路径
- `device_id`: 模拟器设备ID
- `image_threshold`: 图像匹配阈值(0-1)
- `log_level`: 日志级别(debug/info/warning/error)

## 任务编写指南

本编辑器内置几个简单的脚本，你可以通过脚本来了解具体的逻辑以及如何使用。其中有个注意点：如果你想使用截图功能来编写识图相关的操作，请在模拟器内使用模拟器内置的截图工具进行截图，否则可能会因为缩放不正确的原因导致识别失败。

### 基本操作
- `screenshot`: 截图并保存
- `click`: 点击屏幕坐标或匹配图像
- `wait`: 等待指定时间

### 流程控制  
- `condition`: 条件判断
- `loop`: 循环执行
- `set_variable`: 设置变量

示例见`config/tasks.json`

## 高级功能

1. 图像匹配：使用`find_template`方法定位界面元素
2. OCR识别：通过`extract_text`获取屏幕文字
3. 插件开发：在`plugins/`目录添加自定义模块

