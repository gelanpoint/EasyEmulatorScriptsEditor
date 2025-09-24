#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
任务引擎模块
负责自动化任务的执行和管理
"""

import json
import time
import os
from typing import Dict, Any, List
from core.adb_controller import ADBController
from core.image_processor import ImageProcessor

class TaskEngine:
    def __init__(self, adb: ADBController, img_processor: ImageProcessor, settings: Dict[str, Any]):
        """初始化任务引擎"""
        self.adb = adb
        self.img_processor = img_processor
        self.settings = settings
        # 获取项目根目录，用于处理临时文件
        self.base_dir = self.img_processor.base_dir
        self.variables = {}  # 存储任务变量
        self.watched_variables = set()  # 存储被监控的变量名
        self.task_queue = []  # 任务队列
        self.current_task = None
        self.is_running = False
        self.last_success_time = None # 用于计时器功能
        self.run_start_time = None # 用于统计总时长
        self.success_counts = {} # 用于统计各任务成功次数
        
        self.device_id = self.settings.get("device_id")
        self.ocr_language = self.settings.get("ocr_language", "chi_sim+eng")
        
        # 从设置加载参数，提供默认值
        self.max_retries = self.settings.get("retry_count", 3)
        self.retry_delay = self.settings.get("retry_interval", 1.0)
        self.timeout = self.settings.get("timeout", 30)
        self.task_delay = self.settings.get("task_delay", 0.01) # 任务延时，最低10ms
        self.img_processor.threshold = self.settings.get("image_threshold", 0.8)
        
    def load_tasks(self, tasks_config: List[Dict[str, Any]]):
        """加载任务配置"""
        self.task_queue = tasks_config

    def _build_jump_map(self) -> Dict[int, int]:
        """构建LOOP和END_LOOP之间的跳转映射"""
        jump_map = {}
        stack = []
        for i, task in enumerate(self.task_queue):
            if task.get("type") == "LOOP":
                stack.append(i)
            elif task.get("type") == "END_LOOP":
                if not stack:
                    raise ValueError(f"任务 {i}: 找到没有匹配的 'LOOP' 的 'END_LOOP'")
                loop_index = stack.pop()
                jump_map[loop_index] = i
                jump_map[i] = loop_index
        
        if stack:
            raise ValueError(f"任务 {stack[-1]}: 'LOOP' 没有匹配的 'END_LOOP'")
            
        return jump_map

    def run(self, progress_callback=None, is_running_callable=lambda: True):
        """执行任务队列"""
        self.is_running = True
        self.last_success_time = None # 重置计时器
        self.run_start_time = time.time() # 记录任务流开始时间
        self.success_counts = {} # 重置成功次数计数器
        if self.device_id and not self.adb.connect_device(self.device_id):
            raise Exception(f"无法连接设备: {self.device_id}")

        try:
            jump_map = self._build_jump_map()
        except ValueError as e:
            raise Exception(f"任务结构错误: {e}")

        total_tasks = len(self.task_queue)
        i = 0
        while i < total_tasks and self.is_running and is_running_callable():
            task = self.task_queue[i]
            self.current_task = task
            
            task_type = task.get("type")

            if task_type == "LOOP":
                # 检查进入循环的条件
                if "pre_condition" in task and not self._evaluate_expression(task["pre_condition"]):
                    i = jump_map[i] + 1 # 条件不满足，跳到END_LOOP之后
                    continue
            elif task_type == "END_LOOP":
                # 检查停止循环的条件
                # 如果没有设置条件，或者条件不满足，则继续循环
                if "pre_condition" not in task or not self._evaluate_expression(task["pre_condition"]):
                    i = jump_map[i] + 1  # 继续循环，跳回LOOP之后
                    continue
                else:
                    # 如果条件满足，则停止循环，跳出到END_LOOP之后
                    self._log(task, f"满足停止条件 '{task['pre_condition']}'，正在退出循环。")
                    i += 1 
                    continue
            
            try:
                self._execute_task(task)
            except Exception as e:
                # 检查是否设置了“失败时继续”
                if task.get("continue_on_fail", False):
                    self._log(task, f"任务 '{task.get('description')}' 失败，但已设置为继续。错误: {e}")
                else:
                    # 默认行为：抛出异常，终止整个任务流
                    raise e
            
            if progress_callback:
                progress_callback(i + 1, total_tasks)

            # 执行任务后延时
            if self.task_delay > 0:
                time.sleep(self.task_delay)
            
            i += 1
        
        if not self.is_running:
            self._log(None, "任务被用户停止")

    def stop(self):
        """停止任务执行"""
        self.is_running = False
            
    def _log(self, task: Dict[str, Any], message: str):
        """根据任务设置打印日志"""
        # 如果没有任务上下文（例如在循环结束时），或者任务明确要求打印日志
        if task is None or task.get("print_log", False):
            print(message)

    def _execute_task(self, task: Dict[str, Any]):
        """执行单个任务"""
        # 1. 检查前置条件
        if "pre_condition" in task:
            try:
                if not self._evaluate_expression(task["pre_condition"]):
                    self._log(task, f"任务 '{task.get('description')}' 因前置条件不满足而被跳过。")
                    return
            except Exception as e:
                raise Exception(f"评估前置条件失败: {e}")

        task_type = task.get("type")
        wait_for_success = task.get("wait_for_success", False)
        retries = task.get("retries", self.max_retries)

        # 重新定义超时逻辑
        if wait_for_success:
            # 阻塞任务：只有在任务中明确定义了timeout时才使用，否则为None（无限）
            timeout = task.get("timeout") 
        else:
            # 非阻塞任务：使用任务定义或全局设置
            timeout = task.get("timeout", self.timeout)

        start_time = time.time()
        last_error = None
        
        attempt = 0
        while True: # 改为无限循环，由内部逻辑控制退出
            # 检查是否被外部停止
            if not self.is_running:
                self._log(task, "任务被用户手动停止。")
                return

            attempt += 1
            try:
                # 检查超时（仅当timeout不为None时）
                if timeout is not None and time.time() - start_time > timeout:
                    raise TimeoutError(f"任务执行超时({timeout}秒)")
                
                # 2. 执行核心任务逻辑
                if task_type == "screenshot":
                    self._handle_screenshot(task)
                elif task_type == "click":
                    self._handle_click(task)
                elif task_type == "long_press":
                    self._handle_long_press(task)
                elif task_type == "wait":
                    self._handle_wait(task)
                elif task_type == "set_variable":
                    self._handle_set_variable(task)
                elif task_type == "swipe":
                    self._handle_swipe(task)
                elif task_type == "ocr":
                    self._handle_ocr(task)
                elif task_type == "find_and_click_one":
                    self._handle_find_and_click_one(task)
                elif task_type == "restart_app":
                    self._handle_restart_app(task)
                elif task_type not in ["LOOP", "END_LOOP"]:
                    self._log(task, f"未知任务类型: {task_type}")
                
                # 3. 执行成功后，处理后置动作
                if "post_action" in task:
                    try:
                        self._execute_action(task["post_action"])
                    except Exception as e:
                        raise Exception(f"执行后置动作失败: {e}")

                # 执行成功，退出循环
                self._handle_task_success(task)
                return
                
            except Exception as e:
                last_error = e
                
                # 如果不是阻塞模式，检查重试次数
                if not wait_for_success:
                    if attempt >= retries:
                        # 所有重试都失败，执行失败时动作（如果存在）
                        if "on_fail_action" in task:
                            try:
                                self._log(task, f"任务失败，正在执行失败时动作: {task['on_fail_action']}")
                                self._execute_action(task["on_fail_action"])
                            except Exception as action_e:
                                # 如果失败动作也失败了，将错误信息附加到原始错误上
                                raise Exception(f"任务执行失败(重试{retries}次后): {last_error}\n并且执行失败时动作也失败了: {action_e}")
                        
                        raise Exception(f"任务执行失败(重试{retries}次后): {last_error}")
                    else:
                        self._log(task, f"任务执行失败，剩余重试次数: {retries - attempt}, 错误: {e}")
                else:
                    # 阻塞模式下，只打印日志，不减少重试次数
                    self._log(task, f"阻塞任务执行失败，将在 {self.retry_delay} 秒后重试... 错误: {e}")

                time.sleep(self.retry_delay)
            
    def _handle_screenshot(self, task: Dict[str, Any]):
        """处理截图任务"""
        save_path = task["save_path"]
        success, message = self.adb.screenshot(save_path)
        if not success:
            raise Exception(f"截图失败: {message}")

    def _handle_long_press(self, task: Dict[str, Any]):
        """处理长按任务"""
        x, y = task.get("x"), task.get("y")
        duration = task.get("duration", 1000)

        if x is None or y is None:
            raise Exception("长按任务缺少x或y坐标")

        self._log(task, f"正在执行坐标长按: ({x}, {y})，时长: {duration}ms")
        success, message = self.adb.long_press(x, y, duration)
        if not success:
            raise Exception(f"坐标长按 ({x}, {y}) 失败: {message}")

    def _handle_restart_app(self, task: Dict[str, Any]):
        """处理重启应用任务"""
        package_name = task.get("package_name")
        if not package_name:
            raise Exception("重启应用任务缺少 'package_name' 参数")
        
        self._log(task, f"正在重启应用: {package_name}")
        success, message = self.adb.restart_app(package_name)
        if not success:
            raise Exception(f"重启应用 '{package_name}' 失败: {message}")
            
    def _handle_click(self, task: Dict[str, Any]):
        """处理点击任务，优化优先级: 坐标 > 文字 > 图像"""
        x, y = task.get("x"), task.get("y")
        target_text = task.get("target_text")
        target_image_path = task.get("target")

        # 优化：最高优先级的坐标点击，无需截图
        if x is not None and y is not None and not target_text and not target_image_path:
            self._log(task, f"正在执行坐标点击: ({x}, {y})")
            success, message = self.adb.tap(x, y)
            if not success:
                raise Exception(f"坐标点击 ({x}, {y}) 失败: {message}")
            return

        # 对于需要识别的点击，先截图
        self._log(task, "需要进行图像/文字识别，正在截取屏幕...")
        temp_screenshot_path = os.path.join(self.base_dir, "temp_screen_click.png")
        success, message = self.adb.screenshot(temp_screenshot_path)
        if not success:
            raise Exception(f"获取截图以进行识别失败: {message}")
        
        source_img = self.img_processor.load_image(temp_screenshot_path)
        if source_img is None:
            raise Exception("加载用于识别的截图失败")

        # 按优先级确定点击坐标
        click_pos = None

        # 优先级1: 文字识别
        if target_text:
            self._log(task, f"正在通过OCR查找文字: '{target_text}'")
            lang = task.get("lang", self.ocr_language)
            click_pos, recognized_text = self.img_processor.find_text_location(source_img, target_text, lang=lang)
            if click_pos is None:
                error_detail = f"实际识别内容: '{recognized_text}'" if recognized_text else "未识别到任何文字。"
                raise Exception(f"未找到目标文字 '{target_text}'。{error_detail}")
        
        # 优先级2: 图像匹配
        elif target_image_path:
            self._log(task, f"正在通过模板匹配查找图像: {target_image_path}")
            template_img = self.img_processor.load_image(target_image_path)
            if template_img is None:
                raise Exception(f"加载目标图像失败: {target_image_path}")
            
            original_threshold = self.img_processor.threshold
            current_threshold = task.get("threshold", original_threshold)
            self.img_processor.threshold = current_threshold
            
            click_pos = self.img_processor.find_template(source_img, template_img)
            
            self.img_processor.threshold = original_threshold # 恢复

            if click_pos is None:
                raise Exception(f"未找到目标图像: {target_image_path} (置信度: {current_threshold})")

        # 优先级3: 指定坐标 (作为后备)
        elif x is not None and y is not None:
            click_pos = (x, y)

        # 执行点击
        if click_pos is None:
            raise Exception("点击任务缺少有效的目标(文字/图像/坐标)")
        
        final_x, final_y = click_pos
        self._log(task, f"最终确定点击坐标: ({final_x}, {final_y})")
        success, message = self.adb.tap(final_x, final_y)
        if not success:
            raise Exception(f"点击坐标 ({final_x}, {final_y}) 失败: {message}")

    def _handle_find_and_click_one(self, task: Dict[str, Any]):
        """处理'查找并点击一个'任务：依次查找多个目标，成功一个即点击并返回"""
        target_image_paths = task.get("targets")
        judge_only = task.get("judge_only", False) # 获取新参数

        if not target_image_paths or not isinstance(target_image_paths, list):
            raise Exception("find_and_click_one 任务需要一个 'targets' 列表参数。")

        self._log(task, "开始执行 'find_and_click_one' 任务，准备截图...")
        temp_screenshot_path = os.path.join(self.base_dir, "temp_screen_find_one.png")
        success, message = self.adb.screenshot(temp_screenshot_path)
        if not success:
            raise Exception(f"为 'find_and_click_one' 任务截图失败: {message}")
        
        source_img = self.img_processor.load_image(temp_screenshot_path)
        if source_img is None:
            raise Exception("为 'find_and_click_one' 加载截图失败。")

        # 保存并临时设置阈值
        original_threshold = self.img_processor.threshold
        current_threshold = task.get("threshold", original_threshold)
        self.img_processor.threshold = current_threshold

        try:
            for target_path in target_image_paths:
                self._log(task, f"正在尝试匹配图片: {target_path}")
                template_img = self.img_processor.load_image(target_path)
                if template_img is None:
                    self._log(task, f"警告: 加载目标图片失败，已跳过: {target_path}")
                    continue
                
                click_pos = self.img_processor.find_template(source_img, template_img)
                if click_pos:
                    final_x, final_y = click_pos
                    self._log(task, f"成功找到图片 '{target_path}' 在坐标: ({final_x}, {final_y})。")
                    
                    if judge_only:
                        self._log(task, "模式为“仅判断”，跳过点击操作。")
                    else:
                        self._log(task, "执行点击操作...")
                        success, message = self.adb.tap(final_x, final_y)
                        if not success:
                            raise Exception(f"点击目标 '{target_path}' 失败: {message}")
                    
                    # 成功找到（并根据模式决定是否点击）后，任务完成
                    return
            
            # 如果循环完成都没有找到任何图片
            raise Exception(f"未能在屏幕上找到任何一个目标图片 (置信度: {current_threshold})。")

        finally:
            # 确保总是恢复原始阈值
            self.img_processor.threshold = original_threshold

    def _handle_ocr(self, task: Dict[str, Any]):
        """处理文字识别(OCR)任务"""
        variable_name = task.get("variable_name")
        if not variable_name:
            raise Exception("OCR任务缺少 'variable_name' 参数")

        # 1. 获取截图
        temp_screenshot_path = os.path.join(self.base_dir, "temp_screen_ocr.png")
        success, message = self.adb.screenshot(temp_screenshot_path)
        if not success:
            raise Exception(f"OCR截图失败: {message}")

        # 2. 加载图像
        source_img = self.img_processor.load_image(temp_screenshot_path)
        if source_img is None:
            raise Exception("OCR加载截图失败")

        # 3. 提取文字
        lang = task.get("lang", self.ocr_language)
        extracted_text = self.img_processor.extract_text(source_img, lang=lang)
        if extracted_text is None:
            # extract_text 内部会打印错误，这里可以认为识别失败但不是致命错误
            self._log(task, f"OCR未能识别出任何文字 (语言: {lang})")
            extracted_text = "" # 赋值为空字符串

        # 5. 存储到变量
        self._set_variable(variable_name, extracted_text.strip())
        self._log(task, f"OCR识别结果已存入变量 '{variable_name}': '{self.variables.get(variable_name, '')}'")


    def _evaluate_expression(self, expression: str) -> bool:
        """安全地评估逻辑表达式"""
        import re
        # 替换逻辑运算符
        expression = expression.replace("&&", " and ").replace("||", " or ").replace("!", " not ")
        
        # 修正：将用户输入的 `=` 转换为 `==` 以进行比较，同时避免替换 `!=`, `>=`, `<=`
        # 使用正则表达式确保只替换单独的 `=`
        expression = re.sub(r'(?<![=<>!])=(?![=])', '==', expression)

        # 构建一个安全的局部变量环境
        local_scope = self.variables.copy()

        # 只允许安全的内置函数
        safe_globals = {
            "__builtins__": {
                "abs": abs, "max": max, "min": min, "round": round, "len": len,
                "str": str, "int": int, "float": float, "bool": bool
            }
        }
        
        # 拆分多个条件
        conditions = [cond.strip() for cond in expression.split(';')]
        for cond in conditions:
            if not cond: continue
            try:
                if not eval(cond, safe_globals, local_scope):
                    return False # 任何一个条件不满足则整体为False
            except Exception as e:
                self._log(None, f"评估表达式 '{cond}' 时出错: {e}")
                # 可以在这里决定是返回False还是抛出异常，返回False更安全
                return False
        return True

    def _execute_action(self, action: str):
        """安全地执行赋值操作"""
        # 构建一个安全的局部变量环境
        local_scope = self.variables.copy()
        safe_globals = {
            "__builtins__": {
                "abs": abs, "max": max, "min": min, "round": round, "len": len,
                "str": str, "int": int, "float": float, "bool": bool
            }
        }

        # 分割多个赋值语句
        statements = [stmt.strip() for stmt in action.split(';')]
        for stmt in statements:
            if not stmt: continue
            if '=' not in stmt:
                raise ValueError(f"无效的赋值表达式: {stmt}")
            
            var_name, expr = [s.strip() for s in stmt.split('=', 1)]
            
            # 检查变量名是否合法
            if not var_name.isidentifier():
                raise NameError(f"无效的变量名: {var_name}")

            # 计算表达式的值
            value = eval(expr, safe_globals, local_scope)
            
            # 更新到主变量字典和当前的local_scope
            self._set_variable(var_name, value)
            local_scope[var_name] = value
            
    def _handle_wait(self, task: Dict[str, Any]):
        """处理等待任务"""
        duration = task.get("duration", 1)
        time.sleep(duration)

    def _handle_swipe(self, task: Dict[str, Any]):
        """处理滑动任务"""
        x1, y1 = task["x1"], task["y1"]
        x2, y2 = task["x2"], task["y2"]
        duration = task.get("duration", 300)
        success, message = self.adb.swipe(x1, y1, x2, y2, duration)
        if not success:
            raise Exception(f"滑动操作失败: {message}")

    def _set_variable(self, name: str, value: Any):
        """
        统一的变量设置方法。
        检查变量是否被监视，并在值变化时打印日志。
        """
        old_value = self.variables.get(name)
        # 只有当值确实发生变化时才记录
        if old_value == value:
            return

        self.variables[name] = value
        if name in self.watched_variables:
            # 使用 print 而不是 self._log，因为这个日志不应受当前任务的 print_log 标志控制
            print(f"监控日志: 变量 '{name}' 的值已更新为: {value}")
            
    def _handle_set_variable(self, task: Dict[str, Any]):
        """处理 'set_variable' 任务"""
        name = task["name"]
        value = self._parse_value(task["value"])

        # 如果任务要求打印日志，将变量添加到监控列表
        if task.get("print_log", False):
            self.watched_variables.add(name)

        # 任务本身的执行日志，遵循任务的 print_log 设置
        self._log(task, f"执行 set_variable: 变量 '{name}' 被赋值为 '{value}'")
        
        # 通过统一接口设置变量，这可能会触发额外的监控日志
        self._set_variable(name, value)
        
    def _parse_value(self, value: Any) -> Any:
        """解析变量值，尝试将其转换为数字，否则保持为字符串。也支持变量引用。"""
        if isinstance(value, str):
            # 1. 处理变量引用 {{var_name}}
            if value.startswith("{{") and value.endswith("}}"):
                var_name = value[2:-2].strip()
                return self.variables.get(var_name) # 使用 .get() 更安全

            # 2. 尝试将字符串转换为数字
            try:
                # 优先尝试整数
                return int(value)
            except ValueError:
                try:
                    # 再次尝试浮点数
                    return float(value)
                except ValueError:
                    # 如果都失败，说明它就是个普通字符串
                    return value
        
        # 如果值本身就不是字符串（例如，在 post_action 中直接通过表达式生成了数字），直接返回
        return value
    
    def get_run_summary(self) -> str:
        """生成并返回当前任务运行的摘要"""
        if self.run_start_time is None:
            return "任务尚未运行，无法生成摘要。"

        total_duration = time.time() - self.run_start_time
        
        summary = []
        summary.append("--- 任务执行摘要 ---")
        summary.append(f"总耗时: {total_duration:.2f} 秒")
        
        if not self.success_counts:
            summary.append("没有启用计时的任务成功执行。")
        else:
            summary.append("各计时任务成功次数:")
            for task_name, count in self.success_counts.items():
                summary.append(f"  - {task_name}: {count} 次")
        summary.append("--------------------")
        
        return "\n".join(summary)

    def _handle_task_success(self, task: Dict[str, Any]):
        """
        处理任务成功后的通用逻辑，例如计时器。
        """
        if task.get("enable_timer", False):
            task_desc = task.get('description', '未命名任务')
            
            # 更新成功次数
            self.success_counts[task_desc] = self.success_counts.get(task_desc, 0) + 1
            
            now = time.time()
            if self.last_success_time is not None:
                duration = now - self.last_success_time
                # 使用 print 而不是 self._log，因为这个信息总是需要被看到
                print(f"计时器: 任务 '{task_desc}' 与上一个成功任务间隔 {duration:.2f} 秒")
            else:
                # 这是第一个计时的任务
                print(f"计时器: 任务 '{task_desc}' 的计时器已启动。")
            
            self.last_success_time = now
