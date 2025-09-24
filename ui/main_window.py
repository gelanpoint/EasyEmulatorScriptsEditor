#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
主界面实现
使用PyQt5构建图形界面
"""

from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                            QPushButton, QListWidget, QTextEdit, QLabel,
                            QComboBox, QProgressBar, QDialog, QFormLayout,
                            QLineEdit, QDialogButtonBox, QInputDialog, QMessageBox,
                            QFileDialog, QStackedWidget, QApplication,QCheckBox, QMenu,
                            QGroupBox, QTimeEdit)
from PyQt5.QtGui import QKeySequence, QIntValidator, QDoubleValidator, QColor
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTime, QTimer
import datetime
import os
import json
from core.task_engine import TaskEngine
from core.adb_controller import ADBController

class ImagePasteLineEdit(QLineEdit):
    """支持粘贴图片的行编辑器"""
    def __init__(self, parent=None):
        super().__init__(parent)
        # 获取主脚本的绝对路径的目录
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.templates_dir = os.path.join(base_dir, "templates")
        if not os.path.exists(self.templates_dir):
            os.makedirs(self.templates_dir)

    def keyPressEvent(self, event):
        """重写按键事件，拦截Ctrl+V"""
        if event.matches(QKeySequence.Paste):
            clipboard = QApplication.clipboard()
            mime_data = clipboard.mimeData()
            if mime_data.hasImage():
                image = clipboard.image()
                if not image.isNull():
                    self.save_image_from_clipboard(image)
                    return  # 阻止默认的粘贴行为
        super().keyPressEvent(event)

    def save_image_from_clipboard(self, image):
        """将剪贴板的图片保存到文件"""
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"paste_{timestamp}.png"
            save_path = os.path.join(self.templates_dir, filename)
            
            # 使用相对路径以提高可移植性
            relative_path = os.path.join("templates", filename)

            if image.save(save_path, "PNG"):
                self.setText(relative_path)
                print(f"图片已从剪贴板保存到: {save_path}")
            else:
                print("从剪贴板保存图片失败")
        except Exception as e:
            print(f"保存剪贴板图片时出错: {e}")

class TaskEditDialog(QDialog):
    """任务编辑对话框"""
    def __init__(self, task=None, parent=None):
        super().__init__(parent)
        self.task = task or {"type": "click", "description": "新任务"}
        self.setWindowTitle(f"编辑任务 - {self.task['type']}")

        # 主布局
        self.main_layout = QVBoxLayout(self)
        self.form_layout = QFormLayout()

        # 通用字段
        self.type_combo = QComboBox()
        self.type_combo.addItems(["click", "long_press", "screenshot", "wait", "set_variable", "swipe", "ocr", "find_and_click_one", "restart_app", "LOOP", "END_LOOP"])
        self.desc_edit = QLineEdit(self.task.get("description", ""))
        self.wait_for_success_check = QCheckBox("等待执行成功 (阻塞模式)")
        self.wait_for_success_check.setToolTip("勾选后，此任务会一直重试直到成功，才会执行下一个任务。")
        self.wait_for_success_check.setChecked(self.task.get("wait_for_success", False))
        
        self.continue_on_fail_check = QCheckBox("失败时继续")
        self.continue_on_fail_check.setToolTip("勾选后，如果此任务执行失败（且非阻塞），将继续执行下一个任务。")
        self.continue_on_fail_check.setChecked(self.task.get("continue_on_fail", False))
        
        self.print_log_check = QCheckBox("打印此任务的日志")
        self.print_log_check.setToolTip("勾选后，此任务执行时将打印详细日志。")
        self.print_log_check.setChecked(self.task.get("print_log", False))
        
        self.timer_check = QCheckBox("计时")
        self.timer_check.setToolTip("勾选后，任务成功时将计算与上个任务成功时的时间差。")
        self.timer_check.setChecked(self.task.get("enable_timer", False))

        options_layout = QHBoxLayout()
        options_layout.addWidget(self.wait_for_success_check)
        options_layout.addWidget(self.continue_on_fail_check)
        options_layout.addWidget(self.print_log_check)
        options_layout.addWidget(self.timer_check)

        self.form_layout.addRow("任务类型:", self.type_combo)
        self.form_layout.addRow("任务描述:", self.desc_edit)
        self.form_layout.addRow("执行选项:", options_layout)

        # 阻塞任务的超时设置
        self.timeout_label = QLabel("阻塞超时(秒):")
        self.timeout_edit = QLineEdit(str(self.task.get("timeout", "")))
        self.timeout_edit.setPlaceholderText("留空则无限等待")
        self.timeout_edit.setValidator(QIntValidator(1, 9999))
        self.form_layout.addRow(self.timeout_label, self.timeout_edit)

        # --- 新增：执行条件 ---
        self.pre_cond_combo = QComboBox()
        self.pre_cond_combo.addItems(["无", "变量"])
        self.pre_cond_edit = QLineEdit(self.task.get("pre_condition", ""))
        self.form_layout.addRow("执行条件:", self.pre_cond_combo)
        self.form_layout.addRow("条件表达式:", self.pre_cond_edit)

        # --- 新增：执行后动作 ---
        self.post_action_combo = QComboBox()
        self.post_action_combo.addItems(["无", "变量"])
        self.post_action_edit = QLineEdit(self.task.get("post_action", ""))
        self.form_layout.addRow("执行后动作:", self.post_action_combo)
        self.form_layout.addRow("动作表达式:", self.post_action_edit)

        # --- 新增：失败时动作 ---
        self.fail_action_combo = QComboBox()
        self.fail_action_combo.addItems(["无", "变量"])
        self.fail_action_edit = QLineEdit(self.task.get("on_fail_action", ""))
        self.form_layout.addRow("失败时动作:", self.fail_action_combo)
        self.form_layout.addRow("失败动作表达式:", self.fail_action_edit)

        self.main_layout.addLayout(self.form_layout)

        # 根据初始值设置可见性
        self.pre_cond_edit.setVisible(self.task.get("pre_condition") is not None)
        self.post_action_edit.setVisible(self.task.get("post_action") is not None)
        self.fail_action_edit.setVisible(self.task.get("on_fail_action") is not None)
        if self.task.get("pre_condition"):
            self.pre_cond_combo.setCurrentText("变量")
        if self.task.get("post_action"):
            self.post_action_combo.setCurrentText("变量")
        if self.task.get("on_fail_action"):
            self.fail_action_combo.setCurrentText("变量")

        # 动态参数区域
        self.stacked_widget = QStackedWidget()
        self.main_layout.addWidget(self.stacked_widget)
        self.setup_task_widgets()

        # 确认按钮
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.main_layout.addWidget(buttons)

        # 连接信号
        self.type_combo.currentIndexChanged.connect(self.update_form)
        self.pre_cond_combo.currentIndexChanged.connect(self.toggle_condition_edit)
        self.post_action_combo.currentIndexChanged.connect(self.toggle_action_edit)
        self.fail_action_combo.currentIndexChanged.connect(self.toggle_fail_action_edit)
        self.wait_for_success_check.stateChanged.connect(self.toggle_timeout_edit)


        self.type_combo.setCurrentText(self.task["type"])
        self.update_form()
        self.toggle_condition_edit()
        self.toggle_action_edit()
        self.toggle_fail_action_edit()
        self.toggle_timeout_edit()

    def setup_task_widgets(self):
        """为每种任务类型创建独立的参数设置控件"""
        # 点击任务
        self.click_widget = QWidget()
        click_layout = QFormLayout(self.click_widget)
        self.click_x = QLineEdit(str(self.task.get("x")) if self.task.get("x") is not None else "")
        self.click_x.setValidator(QIntValidator())
        self.click_y = QLineEdit(str(self.task.get("y")) if self.task.get("y") is not None else "")
        self.click_y.setValidator(QIntValidator())
        self.click_target_text = QLineEdit(self.task.get("target_text", ""))
        self.click_target_image = ImagePasteLineEdit(self.task.get("target", ""))
        self.click_target_image.setPlaceholderText("可浏览文件或直接粘贴图片")
        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(lambda: self.browse_file(self.click_target_image))
        
        click_layout.addRow("目标文字(优先):", self.click_target_text)
        
        target_layout = QHBoxLayout()
        target_layout.addWidget(self.click_target_image)
        target_layout.addWidget(browse_btn)
        click_layout.addRow("目标图片(次选):", target_layout)

        click_layout.addRow("X坐标(备用):", self.click_x)
        click_layout.addRow("Y坐标(备用):", self.click_y)
        self.stacked_widget.addWidget(self.click_widget)

        # 截图任务
        self.screenshot_widget = QWidget()
        ss_layout = QFormLayout(self.screenshot_widget)
        self.ss_path = QLineEdit(self.task.get("save_path", "screenshots/capture.png"))
        browse_btn = QPushButton("选择路径...")
        browse_btn.clicked.connect(lambda: self.browse_save_path(self.ss_path))
        path_layout = QHBoxLayout()
        path_layout.addWidget(self.ss_path)
        path_layout.addWidget(browse_btn)
        ss_layout.addRow("保存路径:", path_layout)
        self.stacked_widget.addWidget(self.screenshot_widget)

        # 等待任务
        self.wait_widget = QWidget()
        wait_layout = QFormLayout(self.wait_widget)
        self.wait_duration = QLineEdit(str(self.task.get("duration", "1")))
        self.wait_duration.setValidator(QDoubleValidator(0, 9999, 2))
        wait_layout.addRow("等待时间(秒):", self.wait_duration)
        self.stacked_widget.addWidget(self.wait_widget)

        # 设置变量任务
        self.variable_widget = QWidget()
        var_layout = QFormLayout(self.variable_widget)
        self.var_name = QLineEdit(self.task.get("name", ""))
        self.var_value = QLineEdit(str(self.task.get("value", "")))
        var_layout.addRow("变量名:", self.var_name)
        var_layout.addRow("变量值:", self.var_value)
        self.stacked_widget.addWidget(self.variable_widget)

        # 滑动任务
        self.swipe_widget = QWidget()
        swipe_layout = QFormLayout(self.swipe_widget)
        self.swipe_x1 = QLineEdit(str(self.task.get("x1")) if self.task.get("x1") is not None else "")
        self.swipe_x1.setValidator(QIntValidator())
        self.swipe_y1 = QLineEdit(str(self.task.get("y1")) if self.task.get("y1") is not None else "")
        self.swipe_y1.setValidator(QIntValidator())
        self.swipe_x2 = QLineEdit(str(self.task.get("x2")) if self.task.get("x2") is not None else "")
        self.swipe_x2.setValidator(QIntValidator())
        self.swipe_y2 = QLineEdit(str(self.task.get("y2")) if self.task.get("y2") is not None else "")
        self.swipe_y2.setValidator(QIntValidator())
        self.swipe_duration = QLineEdit(str(self.task.get("duration", "300")))
        self.swipe_duration.setValidator(QIntValidator())
        swipe_layout.addRow("起始X:", self.swipe_x1)
        swipe_layout.addRow("起始Y:", self.swipe_y1)
        swipe_layout.addRow("结束X:", self.swipe_x2)
        swipe_layout.addRow("结束Y:", self.swipe_y2)
        swipe_layout.addRow("持续时间(ms):", self.swipe_duration)
        self.stacked_widget.addWidget(self.swipe_widget)

        # 长按任务
        self.long_press_widget = QWidget()
        long_press_layout = QFormLayout(self.long_press_widget)
        self.long_press_x = QLineEdit(str(self.task.get("x")) if self.task.get("x") is not None else "")
        self.long_press_x.setValidator(QIntValidator())
        self.long_press_y = QLineEdit(str(self.task.get("y")) if self.task.get("y") is not None else "")
        self.long_press_y.setValidator(QIntValidator())
        self.long_press_duration = QLineEdit(str(self.task.get("duration", "1000")))
        self.long_press_duration.setValidator(QIntValidator())
        long_press_layout.addRow("X坐标:", self.long_press_x)
        long_press_layout.addRow("Y坐标:", self.long_press_y)
        long_press_layout.addRow("持续时间(ms):", self.long_press_duration)
        self.stacked_widget.addWidget(self.long_press_widget)

        # 重启应用任务
        self.restart_app_widget = QWidget()
        restart_app_layout = QFormLayout(self.restart_app_widget)
        self.restart_app_package = QLineEdit(self.task.get("package_name", ""))
        self.restart_app_package.setPlaceholderText("例如: com.android.settings")
        restart_app_layout.addRow("应用包名:", self.restart_app_package)
        self.stacked_widget.addWidget(self.restart_app_widget)

        # OCR任务
        self.ocr_widget = QWidget()
        ocr_layout = QFormLayout(self.ocr_widget)
        self.ocr_area = QLineEdit(",".join(map(str, self.task.get("area", []))))
        self.ocr_area.setPlaceholderText("可选, 格式: x1,y1,x2,y2")
        self.ocr_variable = QLineEdit(self.task.get("variable_name", ""))
        self.ocr_lang = QLineEdit(self.task.get("lang", "chi_sim+eng"))
        ocr_layout.addRow("识别区域(可选):", self.ocr_area)
        ocr_layout.addRow("存入变量名:", self.ocr_variable)
        ocr_layout.addRow("识别语言:", self.ocr_lang)
        self.stacked_widget.addWidget(self.ocr_widget)

        # Find and Click One Task
        self.find_one_widget = QWidget()
        find_one_layout = QVBoxLayout(self.find_one_widget)
        find_one_layout.addWidget(QLabel("目标图片列表 (按顺序查找):"))
        self.find_one_list = QListWidget()
        if self.task.get("type") == "find_and_click_one":
            self.find_one_list.addItems(self.task.get("targets", []))
        
        find_one_btn_layout = QHBoxLayout()
        add_btn = QPushButton("添加...")
        add_btn.clicked.connect(self._add_image_to_list)
        remove_btn = QPushButton("移除")
        remove_btn.clicked.connect(self._remove_image_from_list)
        find_one_btn_layout.addWidget(add_btn)
        find_one_btn_layout.addWidget(remove_btn)
        
        find_one_layout.addWidget(self.find_one_list)
        find_one_layout.addLayout(find_one_btn_layout)

        # 新增：仅判断复选框
        self.find_one_judge_only_check = QCheckBox("仅判断 (成功后不点击)")
        self.find_one_judge_only_check.setToolTip("勾选后，匹配成功将只执行“执行后动作”（如果有），而不进行点击。")
        self.find_one_judge_only_check.setChecked(self.task.get("judge_only", False))
        find_one_layout.addWidget(self.find_one_judge_only_check)

        self.stacked_widget.addWidget(self.find_one_widget)

    def _add_image_to_list(self):
        """为find_one_list添加图片路径"""
        path, _ = QFileDialog.getOpenFileName(self, "选择图片", "", "图片文件 (*.png *.jpg *.bmp)")
        if path:
            self.find_one_list.addItem(path)

    def _remove_image_from_list(self):
        """从find_one_list移除选中图片"""
        for item in self.find_one_list.selectedItems():
            self.find_one_list.takeItem(self.find_one_list.row(item))

    def update_form(self):
        """根据任务类型切换显示的控件"""
        task_type = self.type_combo.currentText()
        self.setWindowTitle(f"编辑任务 - {task_type}")

        # 根据任务类型调整“执行条件”的标签
        cond_label = self.form_layout.labelForField(self.pre_cond_combo)
        if cond_label:
            if task_type == "END_LOOP":
                cond_label.setText("停止条件(满足则停):")
            else:
                cond_label.setText("执行条件(满足才执行):")
        
        is_param_task = task_type not in ["LOOP", "END_LOOP"]
        self.stacked_widget.setVisible(is_param_task)

        if task_type == "click":
            self.stacked_widget.setCurrentWidget(self.click_widget)
        elif task_type == "screenshot":
            self.stacked_widget.setCurrentWidget(self.screenshot_widget)
        elif task_type == "wait":
            self.stacked_widget.setCurrentWidget(self.wait_widget)
        elif task_type == "set_variable":
            self.stacked_widget.setCurrentWidget(self.variable_widget)
        elif task_type == "swipe":
            self.stacked_widget.setCurrentWidget(self.swipe_widget)
        elif task_type == "ocr":
            self.stacked_widget.setCurrentWidget(self.ocr_widget)
        elif task_type == "find_and_click_one":
            self.stacked_widget.setCurrentWidget(self.find_one_widget)
        elif task_type == "long_press":
            self.stacked_widget.setCurrentWidget(self.long_press_widget)
        elif task_type == "restart_app":
            self.stacked_widget.setCurrentWidget(self.restart_app_widget)

    def browse_file(self, line_edit):
        """浏览文件对话框"""
        path, _ = QFileDialog.getOpenFileName(self, "选择图片", "", "图片文件 (*.png *.jpg *.bmp)")
        if path:
            line_edit.setText(path)

    def browse_save_path(self, line_edit):
        """浏览保存路径对话框"""
        path, _ = QFileDialog.getSaveFileName(self, "选择保存路径", "", "PNG图片 (*.png)")
        if path:
            line_edit.setText(path)

    def toggle_condition_edit(self):
        """切换条件输入框的可见性"""
        is_variable = self.pre_cond_combo.currentText() == "变量"
        self.pre_cond_edit.setVisible(is_variable)
        self.form_layout.labelForField(self.pre_cond_edit).setVisible(is_variable)

    def toggle_action_edit(self):
        """切换动作输入框的可见性"""
        is_variable = self.post_action_combo.currentText() == "变量"
        self.post_action_edit.setVisible(is_variable)
        self.form_layout.labelForField(self.post_action_edit).setVisible(is_variable)

    def toggle_fail_action_edit(self):
        """切换失败时动作输入框的可见性"""
        is_variable = self.fail_action_combo.currentText() == "变量"
        self.fail_action_edit.setVisible(is_variable)
        self.form_layout.labelForField(self.fail_action_edit).setVisible(is_variable)

    def toggle_timeout_edit(self):
        """根据是否为阻塞任务，切换超时输入框的可见性"""
        is_blocking = self.wait_for_success_check.isChecked()
        self.timeout_label.setVisible(is_blocking)
        self.timeout_edit.setVisible(is_blocking)

    def get_task(self):
        """获取编辑后的任务"""
        task_type = self.type_combo.currentText()
        task = {
            "type": task_type,
            "description": self.desc_edit.text() or f"未命名 {task_type} 任务",
            "wait_for_success": self.wait_for_success_check.isChecked(),
            "continue_on_fail": self.continue_on_fail_check.isChecked(),
            "print_log": self.print_log_check.isChecked(),
            "enable_timer": self.timer_check.isChecked()
        }
        
        # 为阻塞任务添加可选的超时
        if task["wait_for_success"]:
            timeout_text = self.timeout_edit.text()
            if timeout_text:
                task["timeout"] = int(timeout_text)

        # 添加条件和动作
        if self.pre_cond_combo.currentText() == "变量" and self.pre_cond_edit.text():
            task["pre_condition"] = self.pre_cond_edit.text()
        if self.post_action_combo.currentText() == "变量" and self.post_action_edit.text():
            task["post_action"] = self.post_action_edit.text()
        if self.fail_action_combo.currentText() == "变量" and self.fail_action_edit.text():
            task["on_fail_action"] = self.fail_action_edit.text()

        # 添加特定于任务的参数
        if task_type == "click":
            task.update({
                "target_text": self.click_target_text.text(),
                "target": self.click_target_image.text(),
                "x": int(self.click_x.text()) if self.click_x.text() else None,
                "y": int(self.click_y.text()) if self.click_y.text() else None
            })
        elif task_type == "screenshot":
            task["save_path"] = self.ss_path.text()
        elif task_type == "wait":
            task["duration"] = float(self.wait_duration.text()) if self.wait_duration.text() else 1.0
        elif task_type == "set_variable":
            task.update({
                "name": self.var_name.text(),
                "value": self.var_value.text()
            })
        elif task_type == "swipe":
            task.update({
                "x1": int(self.swipe_x1.text()) if self.swipe_x1.text() else None,
                "y1": int(self.swipe_y1.text()) if self.swipe_y1.text() else None,
                "x2": int(self.swipe_x2.text()) if self.swipe_x2.text() else None,
                "y2": int(self.swipe_y2.text()) if self.swipe_y2.text() else None,
                "duration": int(self.swipe_duration.text()) if self.swipe_duration.text() else 300
            })
        elif task_type == "ocr":
            area_text = self.ocr_area.text().strip()
            area = []
            if area_text:
                try:
                    area = [int(x.strip()) for x in area_text.split(',')]
                    if len(area) != 4:
                        raise ValueError("区域必须包含4个整数")
                except ValueError as e:
                    # 可以在这里弹出一个警告
                    print(f"无效的区域格式: {e}")
                    area = [] # 格式错误则忽略
            task.update({
                "area": area,
                "variable_name": self.ocr_variable.text(),
                "lang": self.ocr_lang.text()
            })
        elif task_type == "find_and_click_one":
            items = []
            for i in range(self.find_one_list.count()):
                items.append(self.find_one_list.item(i).text())
            task["targets"] = items
            task["judge_only"] = self.find_one_judge_only_check.isChecked()
        elif task_type == "long_press":
            task.update({
                "x": int(self.long_press_x.text()) if self.long_press_x.text() else None,
                "y": int(self.long_press_y.text()) if self.long_press_y.text() else None,
                "duration": int(self.long_press_duration.text()) if self.long_press_duration.text() else 1000
            })
        elif task_type == "restart_app":
            task["package_name"] = self.restart_app_package.text()
        # LOOP 和 END_LOOP 没有额外参数
        return task

    def accept(self):
        """在保存前验证表达式"""
        import re

        # 1. 验证条件表达式
        if self.pre_cond_combo.currentText() == "变量":
            pre_cond_expr = self.pre_cond_edit.text()
            if pre_cond_expr:
                is_valid, err_msg = self.validate_expression(pre_cond_expr, 'condition')
                if not is_valid:
                    QMessageBox.warning(self, "表达式错误", f"执行条件表达式无效:\n{err_msg}")
                    return

        # 2. 验证动作表达式
        if self.post_action_combo.currentText() == "变量":
            post_action_expr = self.post_action_edit.text()
            if post_action_expr:
                is_valid, err_msg = self.validate_expression(post_action_expr, 'action')
                if not is_valid:
                    QMessageBox.warning(self, "表达式错误", f"执行后动作表达式无效:\n{err_msg}")
                    return
        
        # 3. 验证失败时动作表达式
        if self.fail_action_combo.currentText() == "变量":
            fail_action_expr = self.fail_action_edit.text()
            if fail_action_expr:
                is_valid, err_msg = self.validate_expression(fail_action_expr, 'action')
                if not is_valid:
                    QMessageBox.warning(self, "表达式错误", f"失败时动作表达式无效:\n{err_msg}")
                    return

        # 4. 验证 'set_variable' 任务的变量名
        if self.type_combo.currentText() == "set_variable":
            var_name = self.var_name.text()
            if not var_name.isidentifier():
                 QMessageBox.warning(self, "变量名错误", "变量名必须是有效的Python标识符（例如，'my_var'，不能以数字开头，不能包含空格或特殊字符）。")
                 return
        
        super().accept()

    def validate_expression(self, expression, expr_type):
        """
        验证表达式的语法是否基本正确
        expr_type: 'condition' 或 'action'
        返回 (is_valid, error_message)
        """
        import re
        
        guidance = ""
        try:
            if expr_type == 'condition':
                guidance = "条件表达式指南:\n- 使用 `变量名 == 值` 进行比较 (例如, `count == 5`)。\n- 支持的逻辑运算符: `&&` (与), `||` (或), `!` (非)。\n- 支持的比较运算符: `==`, `!=`, `>`, `<`, `>=`, `<=`。\n- 多个条件可以用分号 `;` 分隔，所有条件都必须满足。"
                
                # 模拟 task_engine 的处理方式
                processed_expr = expression.replace("&&", " and ").replace("||", " or ").replace("!", " not ")
                processed_expr = re.sub(r'(?<![=<>!])=(?![=])', '==', processed_expr)
                
                conditions = [cond.strip() for cond in processed_expr.split(';')]
                for cond in conditions:
                    if not cond: continue
                    # 尝试编译，检查语法错误
                    compile(cond, '<string>', 'eval')
                
                return True, ""

            elif expr_type == 'action':
                guidance = "动作表达式指南:\n- 使用 `变量名 = 表达式` 格式 (例如, `count = count + 1`)。\n- 表达式可以是数字、字符串(用引号)或其他变量。\n- 多个赋值语句可以用分号 `;` 分隔。"

                statements = [stmt.strip() for stmt in expression.split(';')]
                for stmt in statements:
                    if not stmt: continue
                    
                    # 检查赋值语句是否合法
                    parts = stmt.split('=', 1)
                    if len(parts) != 2:
                         raise ValueError("赋值语句必须包含一个等号。")
                    
                    var_name, expr = [s.strip() for s in parts]
                    
                    if not var_name.isidentifier():
                        raise NameError(f"无效的变量名: '{var_name}'。变量名只能包含字母、数字和下划线，且不能以数字开头。")
                    
                    # 检查表达式是否可编译
                    compile(expr, '<string>', 'eval')

                return True, ""

        except Exception as e:
            error_message = f"{e}\n\n{guidance}"
            return False, error_message
        
        return False, "未知的表达式类型。"

class Worker(QThread):
    """后台工作线程"""
    progress = pyqtSignal(int, int)
    finished = pyqtSignal(str)
    log = pyqtSignal(str)

    def __init__(self, task_engine: TaskEngine):
        super().__init__()
        self.task_engine = task_engine
        self.is_running = True

    def run(self):
        try:
            self.task_engine.run(self.progress.emit, lambda: self.is_running)
            if self.is_running:
                self.finished.emit("所有任务执行完成")
            else:
                self.finished.emit("任务已停止")
        except Exception as e:
            self.finished.emit(f"任务执行失败: {str(e)}")

    def stop(self):
        self.is_running = False
        self.task_engine.stop()


from core.image_processor import ImageProcessor

class MainWindow(QMainWindow):
    def __init__(self, task_engine: TaskEngine, adb_controller: ADBController, img_processor: ImageProcessor):
        super().__init__()
        self.task_engine = task_engine
        self.adb_controller = adb_controller
        self.img_processor = img_processor
        self.worker = None

        # 获取配置文件的路径
        self.settings_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "config", "settings.json"
        )
        self.settings = self._load_settings()

        self.init_ui()
        self.load_devices()
        self.load_tasks()
        self.setup_scheduler()
        
    def init_ui(self):
        """初始化界面"""
        self.setWindowTitle('屏幕自动化工具')
        self.setGeometry(100, 100, 800, 600)
        
        # 主控件
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        
        # 主布局
        layout = QVBoxLayout()
        main_widget.setLayout(layout)
        
        # 设备选择
        self.device_combo = QComboBox()
        layout.addWidget(QLabel('选择设备:'))
        layout.addWidget(self.device_combo)
        
        # 任务列表和进度
        layout.addWidget(QLabel('任务列表:'))
        
        task_layout = QHBoxLayout()
        self.task_list = QListWidget()
        self.task_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.task_list.setMinimumWidth(400)
        task_layout.addWidget(self.task_list, 3)

        # 创建进度显示区域的垂直布局
        progress_area_layout = QVBoxLayout()

        self.current_task_label = QLabel("当前任务: 无")
        self.current_task_label.setWordWrap(True)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setMinimumWidth(150)
        self.next_task_label = QLabel("下一任务: 无")
        self.next_task_label.setWordWrap(True)

        progress_area_layout.addWidget(self.current_task_label)
        progress_area_layout.addWidget(self.progress_bar)
        progress_area_layout.addWidget(self.next_task_label)
        
        # 将进度区域添加到主任务布局
        task_layout.addLayout(progress_area_layout, 1)
        layout.addLayout(task_layout)
        
        # 任务操作按钮
        task_btn_layout = QHBoxLayout()
        self.add_btn = QPushButton('添加任务')
        self.edit_btn = QPushButton('编辑任务')
        self.del_btn = QPushButton('删除任务')
        self.up_btn = QPushButton('上移')
        self.down_btn = QPushButton('下移')
        task_btn_layout.addWidget(self.add_btn)
        task_btn_layout.addWidget(self.edit_btn)
        task_btn_layout.addWidget(self.del_btn)
        task_btn_layout.addWidget(self.up_btn)
        task_btn_layout.addWidget(self.down_btn)
        layout.addLayout(task_btn_layout)
        
        # 控制按钮
        ctrl_btn_layout = QHBoxLayout()
        self.start_btn = QPushButton('开始')
        self.stop_btn = QPushButton('停止')
        self.settings_btn = QPushButton('设置')
        self.new_script_btn = QPushButton('新建脚本')
        self.load_tasks_btn = QPushButton('加载任务')
        self.save_btn = QPushButton('保存任务')
        self.test_screenshot_btn = QPushButton('测试截图')
        self.stop_btn.setEnabled(False)
        ctrl_btn_layout.addWidget(self.start_btn)
        ctrl_btn_layout.addWidget(self.stop_btn)
        ctrl_btn_layout.addWidget(self.settings_btn)
        ctrl_btn_layout.addWidget(self.new_script_btn)
        ctrl_btn_layout.addWidget(self.load_tasks_btn)
        ctrl_btn_layout.addWidget(self.save_btn)
        ctrl_btn_layout.addWidget(self.test_screenshot_btn)
        layout.addLayout(ctrl_btn_layout)
        
        # 日志输出
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        layout.addWidget(QLabel('运行日志:'))
        layout.addWidget(self.log_output)
        
        # 连接信号
        self.start_btn.clicked.connect(self.start_tasks)
        self.stop_btn.clicked.connect(self.stop_tasks)
        self.settings_btn.clicked.connect(self.open_settings)
        self.add_btn.clicked.connect(lambda: self.add_task())
        self.edit_btn.clicked.connect(lambda: self.edit_task())
        self.del_btn.clicked.connect(lambda: self.delete_task())
        self.up_btn.clicked.connect(self.move_task_up)
        self.down_btn.clicked.connect(self.move_task_down)
        self.save_btn.clicked.connect(self.save_tasks)
        self.new_script_btn.clicked.connect(self.new_script)
        self.load_tasks_btn.clicked.connect(self.load_tasks_from_file)
        self.test_screenshot_btn.clicked.connect(self.test_screenshot)
        self.device_combo.currentIndexChanged.connect(self.on_device_changed)
        self.task_list.itemClicked.connect(self.on_task_item_clicked)
        self.task_list.customContextMenuRequested.connect(self.show_task_context_menu)
        
    def show_task_context_menu(self, position):
        """显示任务列表的右键上下文菜单"""
        menu = QMenu()
        item = self.task_list.itemAt(position)
        index = self.task_list.row(item) if item else -1

        # 通用操作
        add_at_end_action = menu.addAction("在末尾添加新任务")
        add_at_end_action.triggered.connect(lambda: self.add_task(insert_index=self.task_list.count()))

        if index != -1:
            # 针对选中项的操作
            menu.addSeparator()
            insert_above_action = menu.addAction("在上方插入任务")
            insert_below_action = menu.addAction("在下方插入任务")
            menu.addSeparator()
            edit_action = menu.addAction("编辑任务")
            delete_action = menu.addAction("删除任务")
            
            insert_above_action.triggered.connect(lambda: self.add_task(insert_index=index))
            insert_below_action.triggered.connect(lambda: self.add_task(insert_index=index + 1))
            edit_action.triggered.connect(lambda: self.edit_task(index=index))
            delete_action.triggered.connect(lambda: self.delete_task(index=index))

        menu.exec_(self.task_list.mapToGlobal(position))

    def on_task_item_clicked(self, item):
        """当任务项被点击时，高亮显示循环范围"""
        # 首先重置所有项的背景和前景为默认色
        default_bg_color = self.palette().color(self.palette().Base)
        default_fg_color = self.palette().color(self.palette().Text)
        for i in range(self.task_list.count()):
            list_item = self.task_list.item(i)
            list_item.setBackground(default_bg_color)
            list_item.setForeground(default_fg_color)

        index = self.task_list.row(item)
        if index < 0 or index >= len(self.task_engine.task_queue):
            return

        task = self.task_engine.task_queue[index]
        task_type = task.get("type")

        start_index = -1
        end_index = -1

        # 如果点击了 LOOP，向前查找匹配的 END_LOOP
        if task_type == "LOOP":
            start_index = index
            level = 0
            for i in range(index + 1, len(self.task_engine.task_queue)):
                if self.task_engine.task_queue[i].get("type") == "LOOP":
                    level += 1
                elif self.task_engine.task_queue[i].get("type") == "END_LOOP":
                    if level == 0:
                        end_index = i
                        break
                    else:
                        level -= 1
        # 如果点击了 END_LOOP，向后查找匹配的 LOOP
        elif task_type == "END_LOOP":
            end_index = index
            level = 0
            for i in range(index - 1, -1, -1):
                if self.task_engine.task_queue[i].get("type") == "END_LOOP":
                    level += 1
                elif self.task_engine.task_queue[i].get("type") == "LOOP":
                    if level == 0:
                        start_index = i
                        break
                    else:
                        level -= 1

        # 如果找到了完整的循环对，则高亮它们
        if start_index != -1 and end_index != -1:
            highlight_bg_color = QColor("#E8E8FF")  # 更柔和的淡紫色
            highlight_fg_color = QColor(Qt.black)   # 显式的黑色字体
            for i in range(start_index, end_index + 1):
                list_item = self.task_list.item(i)
                if list_item:
                    list_item.setBackground(highlight_bg_color)
                    list_item.setForeground(highlight_fg_color)

    def update_task_list(self):
        """更新任务列表UI，显示更详细的信息和循环结构"""
        self.task_list.clear()
        indent_level = 0
        for task in self.task_engine.task_queue:
            indent = "    " * indent_level
            desc = task.get("description", "未命名任务")
            
            prefix = ""
            if task.get("wait_for_success"):
                prefix += " [阻塞]"
            if task.get("continue_on_fail"):
                prefix += " [可失败]"
            if task.get("pre_condition"):
                prefix += " [条件]"
            if task.get("post_action"):
                prefix += " [动作]"
            if task.get("on_fail_action"):
                prefix += " [失败动作]"
            if task.get("print_log"):
                prefix += " [日志]"
            if task.get("enable_timer"):
                prefix += " [计时]"

            task_type = task['type']
            details = f"类型: {task_type}"

            if task_type == 'LOOP':
                display_text = f"{indent}LOOP: {desc}{prefix}"
                indent_level += 1
            elif task_type == 'END_LOOP':
                indent_level = max(0, indent_level - 1)
                indent = "    " * indent_level
                display_text = f"{indent}END_LOOP: {desc}{prefix}"
            else:
                if task_type == 'click':
                    if task.get('target_text'):
                        details += f", 文字: '{task['target_text']}'"
                    elif task.get('target'):
                        details += f", 目标: {os.path.basename(task['target'])}"
                    else:
                        details += f", 坐标: ({task.get('x', '?')}, {task.get('y', '?')})"
                elif task_type == 'wait':
                    details += f", 时长: {task.get('duration', '?')}s"
                elif task_type == 'screenshot':
                    details += f", 保存到: {task.get('save_path', '?')}"
                elif task_type == 'swipe':
                    details += f", 从({task.get('x1', '?')},{task.get('y1', '?')})到({task.get('x2', '?')},{task.get('y2', '?')})"
                elif task_type == 'ocr':
                    details += f", 存入变量: {task.get('variable_name', '?')}"
                    if task.get('area'):
                        details += f", 区域: {task.get('area')}"
                elif task_type == 'find_and_click_one':
                    target_count = len(task.get('targets', []))
                    details += f", {target_count}个目标图片"
                elif task_type == 'long_press':
                    details += f", 坐标: ({task.get('x', '?')}, {task.get('y', '?')}), 时长: {task.get('duration', '?')}ms"
                elif task_type == 'restart_app':
                    details += f", 包名: {task.get('package_name', '?')}"

                # 修正：移除 .strip() 以保留前导缩进
                display_text = f"{indent}{prefix}{desc} [{details}]"

            self.task_list.addItem(display_text)

    def test_screenshot(self):
        """测试截图功能"""
        if not self.adb_controller.current_device:
            QMessageBox.warning(self, "错误", "请先选择一个有效的设备。")
            return

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        screenshots_dir = os.path.join(base_dir, "screenshots")
        if not os.path.exists(screenshots_dir):
            os.makedirs(screenshots_dir)
        
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        save_path = os.path.join(screenshots_dir, f"test_shot_{timestamp}.png")

        self.log_output.append(f"正在对设备 {self.adb_controller.current_device} 进行截图...")
        QApplication.processEvents() # 更新UI

        success, message = self.adb_controller.screenshot(save_path)

        if success:
            self.log_output.append(f"截图成功！已保存到: {save_path}")
            QMessageBox.information(self, "截图成功", f"截图已成功保存到:\n{save_path}")
        else:
            self.log_output.append(f"截图失败: {message}")
            QMessageBox.critical(self, "截图失败", f"无法完成截图，错误信息:\n{message}")

    def on_device_changed(self, index):
        """处理设备选择变化"""
        device_id = self.device_combo.itemData(index)
        if device_id:
            self.task_engine.device_id = device_id
            self.log_output.append(f"已选择设备: {device_id}")

    def load_devices(self):
        """加载ADB设备列表"""
        self.log_output.append("正在检测设备...")
        self.adb_controller.connect_all()
        devices = self.adb_controller.devices
        self.device_combo.clear()

        online_devices_found = False
        if not devices:
            self.log_output.append("未检测到任何ADB设备。")
            return

        for device_id, info in devices.items():
            status = info.get("status", "unknown")
            # `adb devices` for a ready device usually shows 'device'
            if status == "device":
                self.device_combo.addItem(f"{device_id} (在线)", device_id)
                online_devices_found = True
            else:
                self.log_output.append(f"检测到设备 {device_id}，但状态为 '{status}' (非在线)。")

        if online_devices_found:
            if self.device_combo.count() > 0:
                self.device_combo.setCurrentIndex(0)
                self.on_device_changed(0)
        else:
            self.log_output.append("没有找到状态为 'device' 的在线设备。请检查模拟器是否完全启动，以及是否已授权USB调试。")

    def add_task(self, insert_index=None):
        """添加新任务，可以指定插入位置"""
        dialog = TaskEditDialog(parent=self)
        if dialog.exec_() == QDialog.Accepted:
            task = dialog.get_task()
            if insert_index is None or insert_index < 0 or insert_index > len(self.task_engine.task_queue):
                # 默认在末尾添加
                self.task_engine.task_queue.append(task)
            else:
                self.task_engine.task_queue.insert(insert_index, task)
            self.update_task_list()
            
    def edit_task(self, index=None):
        """编辑选中任务，可以指定索引"""
        if index is None:
            index = self.task_list.currentRow()
        
        if 0 <= index < len(self.task_engine.task_queue):
            task = self.task_engine.task_queue[index]
            dialog = TaskEditDialog(task, self)
            if dialog.exec_() == QDialog.Accepted:
                self.task_engine.task_queue[index] = dialog.get_task()
                self.update_task_list()
                
    def delete_task(self, index=None):
        """删除选中任务，可以指定索引"""
        if index is None:
            index = self.task_list.currentRow()
            
        if 0 <= index < len(self.task_engine.task_queue):
            self.task_engine.task_queue.pop(index)
            self.update_task_list()
            
    def move_task_up(self):
        """上移任务"""
        index = self.task_list.currentRow()
        if index > 0:
            task = self.task_engine.task_queue.pop(index)
            self.task_engine.task_queue.insert(index - 1, task)
            self.update_task_list()
            self.task_list.setCurrentRow(index - 1)
            
    def move_task_down(self):
        """下移任务"""
        index = self.task_list.currentRow()
        if 0 <= index < len(self.task_engine.task_queue) - 1:
            task = self.task_engine.task_queue.pop(index)
            self.task_engine.task_queue.insert(index + 1, task)
            self.update_task_list()
            self.task_list.setCurrentRow(index + 1)

    def new_script(self):
        """创建一个新的空白任务脚本"""
        reply = QMessageBox.question(self, '确认', '您确定要创建一个新脚本吗？\n所有未保存的更改都将丢失。',
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            self.task_engine.task_queue = []
            self.update_task_list()
            self.settings['last_task_path'] = ""
            self._save_settings()
            self.log_output.append("已创建新脚本。")
            
    def save_tasks(self):
        """保存当前任务列表到文件"""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_dir = os.path.join(base_dir, "config")
        
        path, _ = QFileDialog.getSaveFileName(
            self, 
            "保存任务文件", 
            config_dir,
            "JSON 文件 (*.json)"
        )
        
        if not path:
            self.log_output.append("保存操作已取消。")
            return

        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(self.task_engine.task_queue, f, indent=2, ensure_ascii=False)
            self.log_output.append(f"任务已成功保存到: {path}")
            # 保存成功后，记录路径
            self.settings['last_task_path'] = path
            self._save_settings()
        except Exception as e:
            self.log_output.append(f"保存任务失败: {e}")
            QMessageBox.critical(self, "错误", f"无法保存任务文件:\n{e}")

    def load_tasks(self):
        """从配置文件记录的路径加载任务（程序启动时调用）"""
        last_task_path = self.settings.get('last_task_path')
        if last_task_path and os.path.exists(last_task_path):
            self.log_output.append(f"正在自动加载上次使用的脚本: {last_task_path}")
            self._load_task_file(last_task_path)
        else:
            self.log_output.append("未找到上次使用的脚本记录，请手动加载。")

    def load_tasks_from_file(self):
        """通过文件对话框加载任务"""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_dir = os.path.join(base_dir, "config")
        
        path, _ = QFileDialog.getOpenFileName(
            self, 
            "选择任务文件", 
            config_dir, 
            "JSON 文件 (*.json)"
        )
        
        if path:
            self._load_task_file(path)

    def _load_task_file(self, path: str):
        """从指定路径加载任务文件的辅助函数"""
        try:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    tasks = json.load(f)
                    self.task_engine.load_tasks(tasks)
                    self.update_task_list()
                self.log_output.append(f"已从 {path} 加载任务。")
                # 加载成功后，记录路径
                self.settings['last_task_path'] = path
                self._save_settings()
            else:
                self.log_output.append(f"任务文件不存在: {path}")
        except Exception as e:
            self.log_output.append(f"从 {path} 加载任务失败: {e}")
            QMessageBox.critical(self, "错误", f"无法加载或解析任务文件:\n{e}")
    
    def _load_settings(self):
        """从settings.json加载配置"""
        try:
            if os.path.exists(self.settings_path):
                with open(self.settings_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            self.log_output.append(f"加载设置失败: {e}")
        return {}

    def _save_settings(self):
        """将当前设置保存到settings.json"""
        try:
            with open(self.settings_path, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=4, ensure_ascii=False)
        except Exception as e:
            self.log_output.append(f"保存设置失败: {e}")
        
    def start_tasks(self):
        """开始执行任务"""
        if not self.task_engine.task_queue:
            self.log_output.append("错误：没有可执行的任务")
            return
        if not self.task_engine.device_id:
            self.log_output.append("错误：请先选择一个设备")
            return

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.log_output.append("开始执行任务...")

        # 创建并启动工作线程
        self.worker = Worker(self.task_engine)
        self.worker.progress.connect(self.update_progress_display)
        self.worker.finished.connect(self.on_task_finished)
        self.worker.log.connect(self.log_output.append)
        self.worker.start()

    def stop_tasks(self):
        """停止执行任务"""
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.log_output.append("正在停止任务...")
        # 停止时也应该清理标签
        self.current_task_label.setText("当前任务: 无")
        self.next_task_label.setText("下一任务: 无")
        self.progress_bar.setFormat("已停止")

    def on_task_finished(self, message):
        """任务完成后的处理"""
        # 获取并显示运行摘要
        summary = self.task_engine.get_run_summary()
        self.log_output.append(summary)

        self.log_output.append(message)
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.worker = None
        self.progress_bar.setValue(0)
        self.current_task_label.setText("当前任务: 无")
        self.next_task_label.setText("下一任务: 无")
        self.progress_bar.setFormat("0/0")

    def setup_scheduler(self):
        """设置或重置定时任务"""
        # 如果定时器已存在且在运行，则停止它
        if hasattr(self, 'scheduler_timer') and self.scheduler_timer.isActive():
            self.scheduler_timer.stop()

        if not self.settings.get("timer_enabled", False):
            self.log_output.append("定时器功能未启用。")
            return

        timer_time_str = self.settings.get("timer_time", "00:00:00")
        action_time = QTime.fromString(timer_time_str, "HH:mm:ss")
        current_time = QTime.currentTime()
        
        msecs_to_action = current_time.msecsTo(action_time)

        if msecs_to_action < 0:
            # 如果今天的时间已过，则安排在明天
            msecs_to_action += 24 * 60 * 60 * 1000

        self.scheduler_timer = QTimer(self)
        self.scheduler_timer.setSingleShot(True)
        self.scheduler_timer.timeout.connect(self.execute_scheduled_task)
        self.scheduler_timer.start(msecs_to_action)

        action = self.settings.get("timer_action")
        self.log_output.append(f"已设置定时任务: [{action}] 将在 {action_time.toString('HH:mm:ss')} 执行。")

    def execute_scheduled_task(self):
        """执行预定的任务"""
        # 再次检查设置，以防在等待期间被禁用
        if not self.settings.get("timer_enabled", False):
            self.log_output.append("定时任务在执行前被取消。")
            return

        action = self.settings.get("timer_action")
        self.log_output.append(f"正在执行定时任务: {action}")

        if action == "定时关机":
            self.shutdown_system()
        elif action == "定时重启":
            self.restart_system()
        elif action == "定时启动脚本":
            if not self.worker or not self.worker.isRunning():
                self.start_tasks()
        elif action == "定时停止脚本":
            if self.worker and self.worker.isRunning():
                self.stop_tasks()
        
        # 执行后自动禁用，防止重复执行
        self.settings["timer_enabled"] = False
        self._save_settings()
        self.log_output.append(f"已执行定时任务，并已自动禁用该定时器。请在设置中重新启用以供下次使用。")

    def shutdown_system(self):
        """执行系统关机命令"""
        self.log_output.append("将在1分钟后关机...")
        QMessageBox.warning(self, "定时关机", "系统将在1分钟后关机。请保存您的工作。")
        os.system("shutdown -s -t 60")

    def restart_system(self):
        """执行系统重启命令"""
        self.log_output.append("将在1分钟后重启...")
        QMessageBox.warning(self, "定时重启", "系统将在1分钟后重启。请保存您的工作。")
        os.system("shutdown -r -t 60")

    def open_settings(self):
        """打开设置对话框"""
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec_() == QDialog.Accepted:
            # 设置对话框已经保存了设置，我们只需重新加载它们
            self.settings = self._load_settings()
            self.log_output.append("设置已保存。正在应用新设置...")
            
            try:
                # 更新ADB Controller
                self.adb_controller.adb_path = self.settings.get("adb_path", "adb")
                self.adb_controller.device_addrs = self.settings.get("device_addrs", [])
                
                # 更新Image Processor的Tesseract路径
                tesseract_path = self.settings.get("tesseract_path")
                self.img_processor.tesseract_path = tesseract_path
                self.img_processor._configure_tesseract() # 重新应用配置

                # 更新Task Engine的默认OCR语言
                ocr_language = self.settings.get("ocr_language", "chi_sim+eng")
                self.task_engine.ocr_language = ocr_language
                self.log_output.append(f"默认OCR语言已更新为: {ocr_language}")

                # 更新任务延时
                task_delay = self.settings.get("task_delay", 0.01)
                self.task_engine.task_delay = task_delay
                self.log_output.append(f"任务延时已更新为: {task_delay * 1000} ms")

                self.log_output.append("设置已更新。正在重新加载设备...")
                self.load_devices()
                self.log_output.append("正在重新应用定时器设置...")
                self.setup_scheduler()
            except Exception as e:
                self.log_output.append(f"应用新设置失败: {e}")
            
    def update_progress_display(self, current_index, total):
        """更新进度条和当前/下一个任务标签"""
        if total > 0:
            # 更新进度条
            progress_value = int(((current_index + 1) / total) * 100)
            self.progress_bar.setValue(progress_value)
            self.progress_bar.setFormat(f"{current_index + 1}/{total}")

            # 更新当前任务标签
            if 0 <= current_index < len(self.task_engine.task_queue):
                current_task = self.task_engine.task_queue[current_index]
                self.current_task_label.setText(f"当前任务: {current_task.get('description', '未命名')}")
            else:
                self.current_task_label.setText("当前任务: 无")

            # 更新下一个任务标签
            next_index = current_index + 1
            if 0 <= next_index < len(self.task_engine.task_queue):
                next_task = self.task_engine.task_queue[next_index]
                self.next_task_label.setText(f"下一任务: {next_task.get('description', '未命名')}")
            else:
                self.next_task_label.setText("下一任务: 无 (已是最后一个)")

    def closeEvent(self, event):
        """关闭窗口事件"""
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait()  # 等待线程结束
        event.accept()

class SettingsDialog(QDialog):
    """设置对话框"""
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.settings_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "config", "settings.json"
        )
        self.settings = settings

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        # ADB路径
        self.adb_path_edit = QLineEdit(self.settings.get("adb_path", "adb"))
        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(self.browse_adb_path)
        adb_layout = QHBoxLayout()
        adb_layout.addWidget(self.adb_path_edit)
        adb_layout.addWidget(browse_btn)
        form_layout.addRow("ADB路径:", adb_layout)

        # Tesseract路径
        self.tesseract_path_edit = QLineEdit(self.settings.get("tesseract_path", ""))
        tesseract_browse_btn = QPushButton("浏览...")
        tesseract_browse_btn.clicked.connect(self.browse_tesseract_path)
        tesseract_layout = QHBoxLayout()
        tesseract_layout.addWidget(self.tesseract_path_edit)
        tesseract_layout.addWidget(tesseract_browse_btn)
        form_layout.addRow("Tesseract路径:", tesseract_layout)

        # OCR默认语言
        self.ocr_lang_edit = QLineEdit(self.settings.get("ocr_language", "chi_sim+eng"))
        self.ocr_lang_edit.setPlaceholderText("例如: chi_sim+eng 或 jpn")
        form_layout.addRow("OCR默认语言:", self.ocr_lang_edit)

        # 设备地址
        device_addrs = self.settings.get("device_addrs", [])
        self.device_addrs_edit = QTextEdit("\n".join(device_addrs))
        self.device_addrs_edit.setPlaceholderText("每行一个设备地址，例如:\n127.0.0.1:16384")
        form_layout.addRow("设备地址:", self.device_addrs_edit)

        # 新增：失败重试次数
        self.retry_count_edit = QLineEdit(str(self.settings.get("retry_count", 3)))
        self.retry_count_edit.setValidator(QIntValidator(0, 100))
        form_layout.addRow("失败重试次数:", self.retry_count_edit)

        # 新增：重试间隔
        self.retry_interval_edit = QLineEdit(str(self.settings.get("retry_interval", 1.0)))
        self.retry_interval_edit.setValidator(QDoubleValidator(0.1, 60.0, 2))
        form_layout.addRow("重试间隔(秒):", self.retry_interval_edit)

        # 新增：置信度
        self.confidence_edit = QLineEdit(str(self.settings.get("image_threshold", 0.8)))
        self.confidence_edit.setValidator(QDoubleValidator(0.1, 1.0, 2))
        form_layout.addRow("图像匹配置信度:", self.confidence_edit)

        # 新增：任务延时
        self.task_delay_edit = QLineEdit(str(self.settings.get("task_delay", 0.01) * 1000))
        self.task_delay_edit.setValidator(QIntValidator(10, 60000))
        form_layout.addRow("任务延时(ms):", self.task_delay_edit)

        layout.addLayout(form_layout)

        # --- 新增：定时器设置 ---
        self.timer_group = QGroupBox("定时器功能")
        self.timer_group.setCheckable(True)
        self.timer_group.setChecked(self.settings.get("timer_enabled", False))
        timer_layout = QFormLayout()

        self.timer_action_combo = QComboBox()
        self.timer_action_combo.addItems(["定时关机", "定时重启", "定时启动脚本", "定时停止脚本"])
        self.timer_action_combo.setCurrentText(self.settings.get("timer_action", "定时关机"))
        timer_layout.addRow("执行动作:", self.timer_action_combo)

        self.timer_time_edit = QTimeEdit()
        timer_time_str = self.settings.get("timer_time", "00:00:00")
        self.timer_time_edit.setTime(QTime.fromString(timer_time_str, "HH:mm:ss"))
        timer_layout.addRow("执行时间:", self.timer_time_edit)

        self.timer_group.setLayout(timer_layout)
        layout.addWidget(self.timer_group)

        # 确认按钮
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.save_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


    def browse_adb_path(self):
        """浏览ADB可执行文件"""
        path, _ = QFileDialog.getOpenFileName(self, "选择ADB可执行文件", "", "adb.exe (adb.exe)")
        if path:
            self.adb_path_edit.setText(path)

    def browse_tesseract_path(self):
        """浏览Tesseract可执行文件"""
        path, _ = QFileDialog.getOpenFileName(self, "选择Tesseract可执行文件", "", "tesseract.exe (tesseract.exe)")
        if path:
            self.tesseract_path_edit.setText(path)

    def save_and_accept(self):
        """保存设置并关闭对话框"""
        self.settings["adb_path"] = self.adb_path_edit.text()
        self.settings["tesseract_path"] = self.tesseract_path_edit.text()
        self.settings["ocr_language"] = self.ocr_lang_edit.text()
        device_addrs = self.device_addrs_edit.toPlainText().strip().split('\n')
        self.settings["device_addrs"] = [addr.strip() for addr in device_addrs if addr.strip()]
        self.settings["retry_count"] = int(self.retry_count_edit.text())
        self.settings["retry_interval"] = float(self.retry_interval_edit.text())
        self.settings["image_threshold"] = float(self.confidence_edit.text())
        self.settings["task_delay"] = float(self.task_delay_edit.text()) / 1000.0 # 转换为秒
        
        # 保存定时器设置
        self.settings["timer_enabled"] = self.timer_group.isChecked()
        self.settings["timer_action"] = self.timer_action_combo.currentText()
        self.settings["timer_time"] = self.timer_time_edit.time().toString("HH:mm:ss")

        try:
            with open(self.settings_path, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=4, ensure_ascii=False)
            
            QMessageBox.information(self, "设置已保存", "部分设置（如ADB路径）需要重启应用才能生效。")
            self.accept()
        except Exception as e:
            QMessageBox.warning(self, "错误", f"保存设置失败: {e}")
