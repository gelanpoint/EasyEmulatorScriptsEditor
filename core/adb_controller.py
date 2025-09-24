#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ADB控制器模块
封装所有ADB相关操作
"""

import os
import subprocess
from typing import Optional, Tuple, Union, List

class ADBController:
    def __init__(self, adb_path: str = "adb", device_addrs: List[str] = None):
        """初始化ADB控制器"""
        self.adb_path = adb_path
        self.device_addrs = device_addrs or []
        self.devices = {}  # 设备ID: {"status": "online/offline"}
        self.current_device = None  # 当前操作的设备
        self.device_id = None  # 兼容旧版
        
    def connect(self, device_id: str) -> bool:
        """连接指定设备(兼容旧版)"""
        return self.connect_device(device_id)
        
    def connect_device(self, device_id: str) -> bool:
        """连接指定设备"""
        self.current_device = device_id
        self.device_id = device_id  # 兼容旧版
        if device_id not in self.devices:
            self.devices[device_id] = {"status": "offline"}
        return self._check_device(device_id)
        
    def connect_remote_device(self, device_addr: str) -> bool:
        """连接远程/网络设备"""
        if not device_addr:
            return False
        success, output = self._run_command(f"connect {device_addr}")
        # "already connected" 也是一种成功状态
        if success or "already connected" in output:
            print(f"成功连接到 {device_addr}")
            return True
        print(f"连接到 {device_addr} 失败: {output}")
        return False

    def connect_all(self) -> bool:
        """连接所有配置的设备和已连接的设备"""
        # 1. 连接在配置中指定的网络设备
        for addr in self.device_addrs:
            self.connect_remote_device(addr)

        # 2. 获取所有已连接设备的列表
        success, output = self._run_command("devices")
        if not success:
            print(f"获取设备列表失败: {output}")
            return False
            
        # 解析设备列表
        lines = output.strip().split('\n')[1:]  # 跳过第一行标题
        self.devices.clear() # 清空旧列表
        for line in lines:
            if not line.strip() or "List of devices" in line:
                continue
            parts = line.split('\t')
            if len(parts) == 2:
                device_id, status = parts
                self.devices[device_id] = {"status": status}
        
        return len(self.devices) > 0
        
    def _check_device(self, device_id: str) -> bool:
        """检查设备是否连接"""
        success, result = self._run_command("devices")
        if success and device_id in result:
            self.devices[device_id]["status"] = "online"
            return True
        self.devices[device_id]["status"] = "offline"
        return False
        
    def get_device_status(self, device_id: str) -> str:
        """获取设备状态"""
        return self.devices.get(device_id, {}).get("status", "unknown")
        
    def screenshot(self, save_path: str) -> Tuple[bool, Optional[str]]:
        """
        获取屏幕截图
        :return: (是否成功, 错误信息或None)
        """
        if not self.current_device:
            return False, "没有选择任何设备"
            
        # 1. 截图到设备内部存储
        screencap_cmd = "shell screencap -p /sdcard/screen.png"
        success, output = self._run_command(screencap_cmd)
        if not success:
            return False, f"截图命令(screencap)失败: {output}"
            
        # 2. 从设备拉取截图到本地
        # 使用列表传递命令，以正确处理带空格或特殊字符的路径
        pull_cmd_list = ["pull", "/sdcard/screen.png", save_path]
        success, output = self._run_command(pull_cmd_list)
        if not success:
            return False, f"拉取截图(pull)失败: {output}"
            
        return True, None
        
    def tap(self, x: int, y: int) -> Tuple[bool, Optional[str]]:
        """模拟点击操作"""
        cmd = f"shell input tap {x} {y}"
        return self._run_command(cmd)
        
    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: int = 300) -> Tuple[bool, Optional[str]]:
        """模拟滑动操作"""
        cmd = f"shell input swipe {x1} {y1} {x2} {y2} {duration}"
        return self._run_command(cmd)

    def long_press(self, x: int, y: int, duration: int = 1000) -> Tuple[bool, Optional[str]]:
        """模拟长按操作，通过起始点和终点相同的swipe实现"""
        cmd = f"shell input swipe {x} {y} {x} {y} {duration}"
        return self._run_command(cmd)

    def restart_app(self, package_name: str) -> Tuple[bool, Optional[str]]:
        """强制停止并重启一个应用"""
        # 1. 强制停止应用
        stop_cmd = f"shell am force-stop {package_name}"
        success, output = self._run_command(stop_cmd)
        if not success:
            # force-stop 在应用未运行时可能会失败，但这不应视为致命错误
            print(f"警告: 强制停止应用 '{package_name}' 可能失败 (这在应用未运行时是正常的): {output}")

        # 2. 启动应用的主活动
        # 使用 'monkey' 来启动应用，因为它通常能找到默认的启动Activity
        start_cmd = f"shell monkey -p {package_name} -c android.intent.category.LAUNCHER 1"
        success, output = self._run_command(start_cmd)
        if not success:
            return False, f"启动应用 '{package_name}' 失败: {output}"
        
        return True, None
        
    def _run_command(self, command: Union[str, List[str]], device_id: str = None) -> Tuple[bool, str]:
        """
        执行ADB命令
        :param command: 可以是单个字符串或参数列表
        :return: (是否成功, 输出或错误信息)
        """
        target_device = device_id or self.current_device
        cmd_list = [self.adb_path]
        if target_device:
            cmd_list.extend(["-s", target_device])
        
        if isinstance(command, str):
            cmd_list.extend(command.split())
        else: # 如果是列表，直接扩展
            cmd_list.extend(command)

        try:
            result = subprocess.run(cmd_list, shell=False, check=True,
                                 capture_output=True, text=True,
                                 encoding='gbk', errors='replace')
            return True, result.stdout.strip()
        except FileNotFoundError:
            error_msg = f"命令未找到，请确认ADB路径配置是否正确: '{self.adb_path}'"
            print(f"ADB命令执行失败: {error_msg}")
            return False, error_msg
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip()
            print(f"ADB命令执行失败: {error_msg}")
            return False, error_msg
        except Exception as e:
            error_msg = str(e)
            print(f"执行ADB时发生未知错误: {error_msg}")
            return False, error_msg
