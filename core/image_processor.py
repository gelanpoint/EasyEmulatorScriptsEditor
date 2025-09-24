#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
图像处理模块
负责屏幕截图的分析和识别
"""

import cv2
import numpy as np
from PIL import Image
from typing import Optional, Tuple

import os

class ImageProcessor:
    def __init__(self, threshold: float = 0.8, base_dir: str = None, tesseract_path: str = None):
        """初始化图像处理器"""
        self.threshold = threshold  # 模板匹配阈值
        self.base_dir = base_dir or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.tesseract_path = tesseract_path
        self._configure_tesseract()
        
    def _configure_tesseract(self):
        """如果配置了路径，则设置pytesseract的路径"""
        if self.tesseract_path and os.path.exists(self.tesseract_path):
            try:
                import pytesseract
                pytesseract.pytesseract.tesseract_cmd = self.tesseract_path
            except ImportError:
                pass # 如果没有安装，后续调用会处理
        
    def load_image(self, image_path: str) -> Optional[np.ndarray]:
        """加载图像文件，支持相对和绝对路径"""
        try:
            # 如果不是绝对路径，则与基准目录拼接
            if not os.path.isabs(image_path):
                image_path = os.path.join(self.base_dir, image_path)
            
            img = cv2.imread(image_path, cv2.IMREAD_COLOR)
            if img is None:
                print(f"图像加载失败: 文件不存在或格式不支持 at {image_path}")
                return None
            return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        except Exception as e:
            print(f"图像加载失败: {e}")
            return None
            
    def find_template(self, source_img: np.ndarray, template_img: np.ndarray) -> Optional[Tuple[int, int]]:
        """
        模板匹配查找目标位置
        返回匹配位置的(x,y)坐标
        """
        try:
            res = cv2.matchTemplate(source_img, template_img, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)
            
            if max_val >= self.threshold:
                h, w = template_img.shape[:2]
                center_x = max_loc[0] + w // 2
                center_y = max_loc[1] + h // 2
                return (center_x, center_y)
            return None
        except Exception as e:
            print(f"模板匹配失败: {e}")
            return None
            
    def extract_text(self, image: np.ndarray, lang: str = 'chi_sim+eng') -> Optional[str]:
        """
        使用OCR提取图像中的文字
        需要安装pytesseract
        """
        try:
            from pytesseract import image_to_string
            pil_img = Image.fromarray(image)
            return image_to_string(pil_img, lang=lang)
        except ImportError:
            print("未安装pytesseract，无法进行OCR识别")
            return None
        except Exception as e:
            print(f"OCR识别失败: {e}")
            return None

    def find_text_location(self, image: np.ndarray, target_text: str, lang: str = 'chi_sim+eng') -> Tuple[Optional[Tuple[int, int]], str]:
        """
        使用OCR查找特定文本的位置，并返回识别到的所有文本。
        :param image: 源图像
        :param target_text: 要查找的文本
        :param lang: Tesseract语言包
        :return: (文本中心坐标或None, 识别到的所有文本)
        """
        try:
            from pytesseract import image_to_data, Output
            
            # 使用image_to_data获取详细的识别数据
            data = image_to_data(image, lang=lang, output_type=Output.DICT)
            
            all_recognized_text = []
            found_location = None
            
            n_boxes = len(data['level'])
            for i in range(n_boxes):
                # 我们只关心有文本的块
                text = data['text'][i].strip()
                if text:
                    all_recognized_text.append(text)

                if int(data['conf'][i]) > 60: # 置信度阈值
                    if target_text in text and found_location is None: # 找到第一个匹配的就记录
                        # 找到了包含目标文本的块
                        (x, y, w, h) = (data['left'][i], data['top'][i], data['width'][i], data['height'][i])
                        
                        # 计算中心点
                        center_x = x + w // 2
                        center_y = y + h // 2
                        print(f"找到文本 '{target_text}' 在位置: ({center_x}, {center_y})")
                        found_location = (center_x, center_y)
                        
            full_text = " ".join(all_recognized_text)
            return found_location, full_text
            
        except ImportError:
            error_msg = "未安装pytesseract，无法进行OCR识别"
            print(error_msg)
            return None, error_msg
        except Exception as e:
            error_msg = f"OCR文本定位失败: {e}"
            print(error_msg)
            return None, error_msg
            
    def compare_images(self, img1: np.ndarray, img2: np.ndarray) -> float:
        """
        比较两张图像的相似度
        返回相似度百分比(0-1)
        """
        try:
            # 转换为灰度图
            gray1 = cv2.cvtColor(img1, cv2.COLOR_RGB2GRAY)
            gray2 = cv2.cvtColor(img2, cv2.COLOR_RGB2GRAY)
            
            # 计算结构相似性
            (score, _) = cv2.compareSSIM(gray1, gray2, full=True)
            return score
        except Exception as e:
            print(f"图像比较失败: {e}")
            return 0.0
