#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
屏幕区域选择工具
创建一个覆盖层，允许用户通过拖动鼠标选择一个矩形区域，
然后将该区域的坐标复制到剪贴板。
"""

from PyQt5.QtWidgets import QWidget, QApplication
from PyQt5.QtCore import Qt, QRect, QPoint
from PyQt5.QtGui import QPainter, QPen, QColor

class SelectionOverlay(QWidget):
    """屏幕选择覆盖层"""
    def __init__(self):
        super().__init__()
        # 设置窗口属性：无边框、总在最前、工具窗口类型
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        # 设置背景透明
        self.setAttribute(Qt.WA_TranslucentBackground)
        # 设置鼠标样式为十字准星
        self.setCursor(Qt.CrossCursor)

        # 获取所有屏幕的几何信息，并设置为全屏
        screen_geometry = QApplication.desktop().geometry()
        self.setGeometry(screen_geometry)

        self.begin = QPoint()
        self.end = QPoint()
        self.is_selecting = False

    def paintEvent(self, event):
        """绘制事件，用于画选择框"""
        if self.is_selecting:
            painter = QPainter(self)
            # 半透明黑色背景
            painter.fillRect(self.rect(), QColor(0, 0, 0, 100))
            
            # 绘制选区
            selection_rect = QRect(self.begin, self.end).normalized()
            # 清除选区内的半透明背景，使其变亮
            painter.setCompositionMode(QPainter.CompositionMode_Clear)
            painter.fillRect(selection_rect, Qt.transparent)
            
            # 重新设置绘制模式并画红色边框
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
            pen = QPen(Qt.red, 2, Qt.SolidLine)
            painter.setPen(pen)
            painter.drawRect(selection_rect)

    def mousePressEvent(self, event):
        """鼠标按下事件"""
        if event.button() == Qt.LeftButton:
            self.begin = event.pos()
            self.end = self.begin
            self.is_selecting = True
            self.update()

    def mouseMoveEvent(self, event):
        """鼠标移动事件"""
        if self.is_selecting:
            self.end = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        """鼠标释放事件"""
        if event.button() == Qt.LeftButton:
            self.is_selecting = False
            
            selection_rect = QRect(self.begin, self.end).normalized()
            x1, y1 = selection_rect.left(), selection_rect.top()
            x2, y2 = selection_rect.right(), selection_rect.bottom()
            
            # 确保不是一个无效的点击
            if x1 != x2 and y1 != y2:
                coords_text = f"{x1},{y1},{x2},{y2}"
                clipboard = QApplication.clipboard()
                clipboard.setText(coords_text)
                print(f"坐标已复制到剪贴板: {coords_text}")
            
            # 完成后关闭窗口
            self.close()

    def keyPressEvent(self, event):
        """按键事件，允许按ESC取消"""
        if event.key() == Qt.Key_Escape:
            self.close()

if __name__ == '__main__':
    # 用于独立测试
    import sys
    app = QApplication(sys.argv)
    overlay = SelectionOverlay()
    overlay.show()
    sys.exit(app.exec_())
