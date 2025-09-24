#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
屏幕自动化工具 - 主程序入口
支持安卓模拟器(MuMu等)的自动化操作
"""

import sys
import os
import json
from PyQt5.QtWidgets import QApplication

# 将项目根目录添加到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.adb_controller import ADBController
from core.image_processor import ImageProcessor
from core.task_engine import TaskEngine
from ui.main_window import MainWindow

def main():
    """主程序入口"""
    # 1. 加载配置
    base_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(base_dir, "config", "settings.json")
    config = {}
    try:
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        else:
            print(f"警告：找不到配置文件 {config_path}，将使用默认设置。")
    except Exception as e:
        print(f"加载配置文件失败: {e}")

    # 2. 初始化核心模块
    adb_path = config.get("adb_path", "adb")
    # 确保device_addrs是一个列表
    device_addrs = config.get("device_addrs", [])
    if isinstance(device_addrs, str): # 兼容旧的device_id格式
        device_addrs = [device_addrs] if device_addrs else []

    tesseract_path = config.get("tesseract_path")
    adb_controller = ADBController(adb_path, device_addrs)
    img_processor = ImageProcessor(base_dir=base_dir, tesseract_path=tesseract_path)
    task_engine = TaskEngine(adb_controller, img_processor, settings=config)

    # 3. 创建GUI应用
    app = QApplication(sys.argv)

    # --- 新增：应用酷炫的QSS样式 ---
    qss_style = """
        QWidget {
            background-color: #2c3e50;
            color: #ecf0f1;
            font-family: 'Segoe UI', 'Microsoft YaHei', 'Arial';
            font-size: 10pt;
        }
        QMainWindow, QDialog {
            background-color: #2c3e50;
        }
        QTextEdit, QLineEdit, QComboBox {
            background-color: #34495e;
            border: 1px solid #566573;
            border-radius: 4px;
            padding: 5px;
        }
        QTextEdit:focus, QLineEdit:focus, QComboBox:focus {
            border: 1px solid #5dade2;
        }
        QListWidget {
            background-color: #34495e;
            border: 1px solid #566573;
            border-radius: 4px;
        }
        QListWidget::item {
            padding: 8px;
        }
        QListWidget::item:selected {
            background-color: #5a7aa5;
            color: #ffffff;
        }
        QPushButton {
            background-color: #5dade2;
            color: #ffffff;
            border: none;
            border-radius: 4px;
            padding: 8px 16px;
            min-width: 80px;
        }
        QPushButton:hover {
            background-color: #85c1e9;
        }
        QPushButton:pressed {
            background-color: #3498db;
        }
        QPushButton:disabled {
            background-color: #566573;
            color: #99a3a4;
        }
        QLabel {
            color: #ecf0f1;
        }
        QProgressBar {
            border: 1px solid #566573;
            border-radius: 4px;
            text-align: center;
            color: #ecf0f1;
        }
        QProgressBar::chunk {
            background-color: #5dade2;
            border-radius: 3px;
        }
        QToolTip {
            background-color: #34495e;
            color: #ecf0f1;
            border: 1px solid #566573;
        }
    """
    app.setStyleSheet(qss_style)
    
    # 4. 创建主窗口，并传入依赖
    window = MainWindow(task_engine, adb_controller, img_processor)
    window.show()

    # 5. 运行应用
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
