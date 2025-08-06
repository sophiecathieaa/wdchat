
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import pyautogui
import pytesseract
import threading
import time
import json
import os
import logging
import sys
from datetime import datetime
from PIL import Image, ImageTk, ImageGrab
import pystray
from pystray import MenuItem as Item
import webbrowser
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"

class WeChatMonitorPro:
    def __init__(self):
        self.version = "1.0"
        self.monitoring = False
        self.monitor_thread = None
        self.tray_icon = None
        self.root = None
        self.is_closing = False

        # 默认配置
        self.config = {
            'region': (100, 100, 800, 600),  # 截图区域
            'reply_text': '2',  # 固定回复内容
            'check_interval': 3,  # 3秒检测间隔
            'cities': [
                '天津', '重庆', '北京', '杭州', '烟台', '郑州', '沈阳', '温州',
                '南昌', '深圳', '广州', '太原', '福州', '南宁', '呼和浩特',
                '上海', '长春', '西安', '大连', '石家庄', '青岛'
            ],
            'log_to_file': True,
            'window_title': '微信群监控工具',
            'auto_start': False,
            'ocr_confidence': 60
        }

        # 消息历史，避免重复回复
        self.message_history = set()
        self.last_screenshot_hash = None

        # 设置日志
        self.setup_logging()

        # 创建GUI
        self.create_gui()

        # 加载配置
        self.load_config()

        # 设置系统托盘
        self.setup_tray()

        self.log("程序启动完成")

    def setup_logging(self):
        """设置日志系统"""
        log_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # 文件日志
        log_filename = f"wechat_monitor_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.FileHandler(log_filename, encoding='utf-8')
        file_handler.setFormatter(log_formatter)

        # 控制台日志
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(log_formatter)

        # 配置logger
        self.logger = logging.getLogger('WeChatMonitor')
        self.logger.setLevel(logging.INFO)
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    def log(self, message, level='info'):
        """记录日志"""
        if level == 'info':
            self.logger.info(message)
        elif level == 'error':
            self.logger.error(message)
        elif level == 'warning':
            self.logger.warning(message)

        # 同时显示在GUI日志区域
        if hasattr(self, 'log_text'):
            timestamp = datetime.now().strftime('%H:%M:%S')
            log_msg = f"[{timestamp}] {message}\n"
            self.log_text.insert(tk.END, log_msg)
            self.log_text.see(tk.END)

            # 限制日志长度，避免内存占用过多
            lines = int(self.log_text.index('end-1c').split('.')[0])
            if lines > 1000:
                self.log_text.delete('1.0', '500.0')

    def create_gui(self):
        """创建GUI界面"""
        self.root = tk.Tk()
        self.root.title(f"微信群监控工具 v{self.version}")
        self.root.geometry("800x700")
        self.root.resizable(True, True)

        # 设置窗口图标（可选）
        try:
            # 如果有图标文件，可以在这里设置
            pass
        except:
            pass

        # 创建菜单栏
        self.create_menu()

        # 创建主界面
        self.create_main_interface()

        # 绑定关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_window_close)

        # 窗口居中
        self.center_window()

    def create_menu(self):
        """创建菜单栏"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # 文件菜单
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="文件", menu=file_menu)
        file_menu.add_command(label="保存配置", command=self.save_config)
        file_menu.add_command(label="加载配置", command=self.load_config)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self.quit_application)

        # 工具菜单
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="工具", menu=tools_menu)
        tools_menu.add_command(label="区域选择器", command=self.open_region_selector)
        tools_menu.add_command(label="测试截图", command=self.test_screenshot)
        tools_menu.add_command(label="测试OCR", command=self.test_ocr)
        tools_menu.add_separator()
        tools_menu.add_command(label="清空日志", command=self.clear_log)
        tools_menu.add_command(label="打开日志文件夹", command=self.open_log_folder)

        # 帮助菜单
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="帮助", menu=help_menu)
        help_menu.add_command(label="使用说明", command=self.show_help)
        help_menu.add_command(label="关于", command=self.show_about)

    def create_main_interface(self):
        """创建主界面"""
        # 创建主框架
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # 状态栏
        self.create_status_bar()

        # 控制面板
        self.create_control_panel(main_frame)

        # 配置面板
        self.create_config_panel(main_frame)

        # 日志面板
        self.create_log_panel(main_frame)

    def create_status_bar(self):
        """创建状态栏"""
        status_frame = ttk.Frame(self.root)
        status_frame.pack(fill="x", side="bottom")

        self.status_label = ttk.Label(status_frame, text="状态: 就绪")
        self.status_label.pack(side="left", padx=5)

        # 版本信息
        version_label = ttk.Label(status_frame, text=f"v{self.version}")
        version_label.pack(side="right", padx=5)

    def create_control_panel(self, parent):
        """创建控制面板"""
        control_frame = ttk.LabelFrame(parent, text="控制面板", padding=10)
        control_frame.pack(fill="x", pady=(0, 10))

        # 按钮框架
        btn_frame = ttk.Frame(control_frame)
        btn_frame.pack(fill="x")

        # 开始按钮
        self.start_btn = ttk.Button(btn_frame, text="开始监控",
                                    command=self.start_monitoring, width=15)
        self.start_btn.pack(side="left", padx=5)

        # 暂停按钮
        self.pause_btn = ttk.Button(btn_frame, text="暂停监控",
                                    command=self.pause_monitoring,
                                    state="disabled", width=15)
        self.pause_btn.pack(side="left", padx=5)

        # 停止按钮
        self.stop_btn = ttk.Button(btn_frame, text="停止监控",
                                   command=self.stop_monitoring,
                                   state="disabled", width=15)
        self.stop_btn.pack(side="left", padx=5)

        # 退出按钮
        self.quit_btn = ttk.Button(btn_frame, text="退出程序",
                                   command=self.quit_application, width=15)
        self.quit_btn.pack(side="right", padx=5)

        # 设置按钮
        settings_btn = ttk.Button(btn_frame, text="设置",
                                  command=self.open_settings, width=10)
        settings_btn.pack(side="right", padx=5)

        # 状态显示
        status_info_frame = ttk.Frame(control_frame)
        status_info_frame.pack(fill="x", pady=(10, 0))

        ttk.Label(status_info_frame, text="监控区域:").pack(side="left")
        self.region_label = ttk.Label(status_info_frame, text="未设置", foreground="red")
        self.region_label.pack(side="left", padx=(5, 20))

        ttk.Label(status_info_frame, text="检测间隔:").pack(side="left")
        self.interval_label = ttk.Label(status_info_frame, text="3秒")
        self.interval_label.pack(side="left", padx=(5, 20))

        ttk.Label(status_info_frame, text="城市数量:").pack(side="left")
        self.cities_label = ttk.Label(status_info_frame, text="21个")
        self.cities_label.pack(side="left", padx=(5, 0))

    def create_config_panel(self, parent):
        """创建配置面板"""
        config_frame = ttk.LabelFrame(parent, text="快速配置", padding=10)
        config_frame.pack(fill="x", pady=(0, 10))

        # 截图区域设置
        region_frame = ttk.Frame(config_frame)
        region_frame.pack(fill="x", pady=(0, 5))

        ttk.Label(region_frame, text="截图区域:").pack(side="left")

        ttk.Label(region_frame, text="X:").pack(side="left", padx=(10, 0))
        self.x_var = tk.StringVar(value="100")
        x_entry = ttk.Entry(region_frame, textvariable=self.x_var, width=8)
        x_entry.pack(side="left", padx=(2, 10))

        ttk.Label(region_frame, text="Y:").pack(side="left")
        self.y_var = tk.StringVar(value="100")
        y_entry = ttk.Entry(region_frame, textvariable=self.y_var, width=8)
        y_entry.pack(side="left", padx=(2, 10))

        ttk.Label(region_frame, text="宽:").pack(side="left")
        self.width_var = tk.StringVar(value="800")
        width_entry = ttk.Entry(region_frame, textvariable=self.width_var, width=8)
        width_entry.pack(side="left", padx=(2, 10))

        ttk.Label(region_frame, text="高:").pack(side="left")
        self.height_var = tk.StringVar(value="600")
        height_entry = ttk.Entry(region_frame, textvariable=self.height_var, width=8)
        height_entry.pack(side="left", padx=(2, 10))

        # 区域选择按钮
        select_btn = ttk.Button(region_frame, text="区域选择",
                                command=self.open_region_selector)
        select_btn.pack(side="left", padx=10)

        # 预览按钮
        preview_btn = ttk.Button(region_frame, text="预览",
                                 command=self.preview_region)
        preview_btn.pack(side="left", padx=5)

    def create_log_panel(self, parent):
        """创建日志面板"""
        log_frame = ttk.LabelFrame(parent, text="运行日志", padding=10)
        log_frame.pack(fill="both", expand=True)

        # 创建文本框和滚动条
        text_frame = ttk.Frame(log_frame)
        text_frame.pack(fill="both", expand=True)

        self.log_text = tk.Text(text_frame, height=15, wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)

        self.log_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # 日志控制按钮
        log_control_frame = ttk.Frame(log_frame)
        log_control_frame.pack(fill="x", pady=(5, 0))

        ttk.Button(log_control_frame, text="清空日志",
                   command=self.clear_log).pack(side="left", padx=5)
        ttk.Button(log_control_frame, text="保存日志",
                   command=self.save_log).pack(side="left", padx=5)
        ttk.Button(log_control_frame, text="打开日志文件夹",
                   command=self.open_log_folder).pack(side="right", padx=5)

    def center_window(self):
        """窗口居中"""
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def open_region_selector(self):
        """打开区域选择器"""
        RegionSelector(self.root, self.on_region_selected)

    def on_region_selected(self, region):
        """区域选择完成的回调"""
        self.x_var.set(str(region[0]))
        self.y_var.set(str(region[1]))
        self.width_var.set(str(region[2]))
        self.height_var.set(str(region[3]))
        self.update_region_config()
        self.log(f"已选择区域: {region}")

    def update_region_config(self):
        """更新区域配置"""
        try:
            x = int(self.x_var.get())
            y = int(self.y_var.get())
            width = int(self.width_var.get())
            height = int(self.height_var.get())

            self.config['region'] = (x, y, width, height)
            self.region_label.config(text=f"{x},{y} {width}x{height}", foreground="green")

        except ValueError:
            self.region_label.config(text="参数错误", foreground="red")

    def preview_region(self):
        """预览截图区域"""
        try:
            self.update_region_config()
            region = self.config['region']

            # 截图
            screenshot = pyautogui.screenshot(region=region)

            # 创建预览窗口
            preview_window = tk.Toplevel(self.root)
            preview_window.title("区域预览")
            preview_window.geometry("600x400")

            # 调整图片大小
            img = screenshot.copy()
            img.thumbnail((580, 380), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(img)

            label = tk.Label(preview_window, image=photo)
            label.image = photo  # 保持引用
            label.pack(expand=True)

            self.log("区域预览已打开")

        except Exception as e:
            self.log(f"预览失败: {str(e)}", 'error')
            messagebox.showerror("错误", f"预览失败: {str(e)}")

    def test_screenshot(self):
        """测试截图功能"""
        try:
            self.update_region_config()
            region = self.config['region']

            screenshot = pyautogui.screenshot(region=region)

            # 保存测试截图
            filename = f"test_screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            screenshot.save(filename)

            self.log(f"测试截图已保存: {filename}")
            messagebox.showinfo("成功", f"测试截图已保存: {filename}")

        except Exception as e:
            self.log(f"截图测试失败: {str(e)}", 'error')
            messagebox.showerror("错误", f"截图测试失败: {str(e)}")

    def test_ocr(self):
        """测试OCR识别"""
        try:
            self.update_region_config()
            region = self.config['region']

            # 截图
            screenshot = pyautogui.screenshot(region=region)

            # OCR识别
            text = pytesseract.image_to_string(screenshot, lang='chi_sim')

            # 显示结果
            result_window = tk.Toplevel(self.root)
            result_window.title("OCR识别结果")
            result_window.geometry("500x400")

            text_widget = tk.Text(result_window, wrap=tk.WORD)
            text_widget.pack(fill="both", expand=True, padx=10, pady=10)
            text_widget.insert("1.0", text)

            self.log("OCR测试完成")

        except Exception as e:
            self.log(f"OCR测试失败: {str(e)}", 'error')
            messagebox.showerror("错误", f"OCR测试失败: {str(e)}")

    def start_monitoring(self):
        """开始监控"""
        if self.monitoring:
            return

        try:
            self.update_region_config()

            # 验证配置
            if not self.validate_config():
                return

            self.monitoring = True
            self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
            self.monitor_thread.start()

            # 更新UI
            self.start_btn.config(state="disabled")
            self.pause_btn.config(state="normal")
            self.stop_btn.config(state="normal")
            self.status_label.config(text="状态: 监控中...")

            self.log("开始监控微信群聊")

        except Exception as e:
            self.log(f"启动监控失败: {str(e)}", 'error')
            messagebox.showerror("错误", f"启动监控失败: {str(e)}")

    def pause_monitoring(self):
        """暂停/恢复监控"""
        if hasattr(self, 'paused'):
            self.paused = not self.paused
            if self.paused:
                self.pause_btn.config(text="恢复监控")
                self.status_label.config(text="状态: 已暂停")
                self.log("监控已暂停")
            else:
                self.pause_btn.config(text="暂停监控")
                self.status_label.config(text="状态: 监控中...")
                self.log("监控已恢复")
        else:
            self.paused = True
            self.pause_btn.config(text="恢复监控")
            self.status_label.config(text="状态: 已暂停")
            self.log("监控已暂停")

    def stop_monitoring(self):
        """停止监控"""
        self.monitoring = False
        self.paused = False

        # 更新UI
        self.start_btn.config(state="normal")
        self.pause_btn.config(state="disabled", text="暂停监控")
        self.stop_btn.config(state="disabled")
        self.status_label.config(text="状态: 已停止")

        self.log("监控已停止")

    def validate_config(self):
        """验证配置"""
        try:
            region = self.config['region']
            if not all(isinstance(x, int) and x > 0 for x in region):
                messagebox.showerror("错误", "截图区域配置无效")
                return False

            if not self.config['cities']:
                messagebox.showerror("错误", "城市列表为空")
                return False

            return True

        except Exception as e:
            messagebox.showerror("错误", f"配置验证失败: {str(e)}")
            return False

    def monitor_loop(self):
        """监控主循环"""
        self.paused = False

        while self.monitoring:
            try:
                # 检查是否暂停
                if hasattr(self, 'paused') and self.paused:
                    time.sleep(1)
                    continue

                # 截图
                screenshot = self.capture_screen()
                if screenshot is None:
                    time.sleep(self.config['check_interval'])
                    continue

                # 检查截图是否变化（优化性能）
                screenshot_hash = hash(screenshot.tobytes())
                if screenshot_hash == self.last_screenshot_hash:
                    time.sleep(self.config['check_interval'])
                    continue

                self.last_screenshot_hash = screenshot_hash

                # OCR识别
                text = self.extract_text(screenshot)
                if not text:
                    time.sleep(self.config['check_interval'])
                    continue

                # 检查城市名称
                found_cities = self.check_cities_in_text(text)

                if found_cities:
                    self.log(f"检测到城市: {', '.join(found_cities)}")
                    self.send_reply()
                    time.sleep(2)  # 发送后延迟

            except Exception as e:
                self.log(f"监控过程出错: {str(e)}", 'error')

            time.sleep(self.config['check_interval'])

    def capture_screen(self):
        """截取屏幕"""
        try:
            region = self.config['region']
            screenshot = pyautogui.screenshot(region=region)
            return screenshot
        except Exception as e:
            self.log(f"截图失败: {str(e)}", 'error')
            return None

    def extract_text(self, image):
        """OCR文字识别"""
        try:
            # 预处理图像以提高识别率
            # 可以添加灰度化、二值化等处理
            text = pytesseract.image_to_string(image, lang='chi_sim')
            return text.strip()
        except Exception as e:
            self.log(f"OCR识别失败: {str(e)}", 'error')
            return ""

    def check_cities_in_text(self, text):
        """检查文本中是否包含城市名称"""
        found_cities = []

        for city in self.config['cities']:
            if city in text:
                # 生成消息哈希，避免重复处理
                context_lines = [line.strip() for line in text.split('\n') if city in line]
                for line in context_lines:
                    msg_hash = hash(line)
                    if msg_hash not in self.message_history:
                        self.message_history.add(msg_hash)
                        found_cities.append(city)
                        break

        return found_cities

    def send_reply(self):
        """发送回复"""
        try:
            # 模拟键盘输入
            pyautogui.typewrite(self.config['reply_text'])
            pyautogui.press('enter')

            self.log(f"已发送回复: {self.config['reply_text']}")

        except Exception as e:
            self.log(f"发送回复失败: {str(e)}", 'error')

    def open_settings(self):
        """打开设置窗口"""
        SettingsWindow(self.root, self.config, self.on_settings_changed)

    def on_settings_changed(self, new_config):
        """设置更改的回调"""
        self.config.update(new_config)
        self.update_ui_from_config()
        self.log("配置已更新")

    def update_ui_from_config(self):
        """根据配置更新UI"""
        region = self.config['region']
        self.x_var.set(str(region[0]))
        self.y_var.set(str(region[1]))
        self.width_var.set(str(region[2]))
        self.height_var.set(str(region[3]))

        self.region_label.config(text=f"{region[0]},{region[1]} {region[2]}x{region[3]}",
                                 foreground="green")
        self.interval_label.config(text=f"{self.config['check_interval']}秒")
        self.cities_label.config(text=f"{len(self.config['cities'])}个")

    def save_config(self):
        """保存配置"""
        try:
            self.update_region_config()
            with open('config.json', 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            self.log("配置已保存")
            messagebox.showinfo("成功", "配置已保存")
        except Exception as e:
            self.log(f"保存配置失败: {str(e)}", 'error')
            messagebox.showerror("错误", f"保存配置失败: {str(e)}")

    def load_config(self):
        """加载配置"""
        try:
            if os.path.exists('config.json'):
                with open('config.json', 'r', encoding='utf-8') as f:
                    saved_config = json.load(f)
                    self.config.update(saved_config)

                self.update_ui_from_config()
                self.log("配置已加载")
            else:
                self.log("配置文件不存在，使用默认配置")
        except Exception as e:
            self.log(f"加载配置失败: {str(e)}", 'error')

    def clear_log(self):
        """清空日志"""
        self.log_text.delete('1.0', tk.END)
        self.log("日志已清空")

    def save_log(self):
        """保存日志"""
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")],
                initialname=f"monitor_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            )

            if filename:
                content = self.log_text.get('1.0', tk.END)
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(content)
                self.log(f"日志已保存: {filename}")
                messagebox.showinfo("成功", f"日志已保存: {filename}")

        except Exception as e:
            self.log(f"保存日志失败: {str(e)}", 'error')
            messagebox.showerror("错误", f"保存日志失败: {str(e)}")

    def open_log_folder(self):
        """打开日志文件夹"""
        try:
            import subprocess
            import platform

            if platform.system() == "Windows":
                os.startfile(".")
            elif platform.system() == "Darwin":
                subprocess.run(["open", "."])
            else:
                subprocess.run(["xdg-open", "."])

        except Exception as e:
            self.log(f"打开文件夹失败: {str(e)}", 'error')

    def setup_tray(self):
        """设置系统托盘"""
        try:
            # 创建托盘菜单
            menu = pystray.Menu(
                Item("显示窗口", self.show_window),
                Item("开始监控", self.start_monitoring),
                Item("停止监控", self.stop_monitoring),
                pystray.Menu.SEPARATOR,
                Item("退出", self.quit_application)
            )

            # 创建简单图标（可以替换为实际图标文件）
            image = self.create_tray_icon()

            self.tray_icon = pystray.Icon("WeChatMonitor", image, "微信群监控工具", menu)

            # 在单独线程中运行托盘
            tray_thread = threading.Thread(target=self.tray_icon.run, daemon=True)
            tray_thread.start()

        except Exception as e:
            self.log(f"托盘设置失败: {str(e)}", 'error')

    def create_tray_icon(self):
        """创建托盘图标"""
        from PIL import Image, ImageDraw

        # 创建一个简单的图标
        width = height = 64
        image = Image.new('RGB', (width, height), color='white')
        draw = ImageDraw.Draw(image)

        # 绘制一个简单的图标
        draw.ellipse([16, 16, 48, 48], fill='blue', outline='darkblue', width=2)
        draw.text((26, 26), "监", fill='white')

        return image

    def show_window(self, icon=None, item=None):
        """显示窗口"""
        if self.root:
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()

    def hide_window(self):
        """隐藏窗口到托盘"""
        if self.root:
            self.root.withdraw()

    def on_window_close(self):
        """窗口关闭事件"""
        if messagebox.askyesno("确认", "是否最小化到系统托盘？\n选择'否'将退出程序"):
            self.hide_window()
        else:
            self.quit_application()

    def quit_application(self, icon=None, item=None):
        """退出程序"""
        if self.monitoring:
            if not messagebox.askyesno("确认", "监控正在运行中，确定要退出吗？"):
                return

        self.is_closing = True
        self.monitoring = False

        # 停止托盘图标
        if self.tray_icon:
            self.tray_icon.stop()

        # 保存配置
        try:
            self.save_config()
        except:
            pass

        self.log("程序退出")

        if self.root:
            self.root.quit()
            self.root.destroy()

        sys.exit(0)

    def show_help(self):
        """显示帮助信息"""
        help_text = """
微信群监控工具使用说明

1. 基本使用步骤：
   • 打开微信群聊窗口
   • 使用"区域选择"功能选择聊天区域
   • 点击"开始监控"按钮
   • 程序将自动检测城市名称并回复"2"

2. 功能说明：
   • 自动监控：每3秒检测一次聊天内容
   • 智能识别：使用OCR技术识别文本
   • 防重复：避免对同一消息重复回复
   • 系统托盘：可最小化到托盘后台运行

3. 监控的城市列表：
   天津、重庆、北京、杭州、烟台、郑州、沈阳、温州、
   南昌、深圳、广州、太原、福州、南宁、呼和浩特、
   上海、长春、西安、大连、石家庄、青岛

4. 注意事项：
   • 确保微信窗口可见且未被遮挡
   • 截图区域应准确覆盖聊天内容区域
   • 程序需要安装pytesseract和Tesseract-OCR

5. 快捷键：
   • Ctrl+S：保存配置
   • F1：帮助信息
        """

        help_window = tk.Toplevel(self.root)
        help_window.title("使用说明")
        help_window.geometry("600x500")
        help_window.resizable(False, False)

        text_widget = tk.Text(help_window, wrap=tk.WORD, padx=10, pady=10)
        text_widget.pack(fill="both", expand=True)
        text_widget.insert("1.0", help_text)
        text_widget.config(state="disabled")

        # 居中显示
        help_window.transient(self.root)
        help_window.grab_set()

    def show_about(self):
        """显示关于信息"""
        about_text = f"""
微信群监控工具 v{self.version}

专业的微信群聊自动回复工具

功能特点：
• 智能OCR文字识别
• 自动检测城市名称
• 防重复回复机制
• 系统托盘后台运行
• 详细运行日志记录

技术支持：
• Python + tkinter
• pytesseract OCR
• pyautogui 自动化

作者：AI Assistant
版本：{self.version}
        """

        messagebox.showinfo("关于", about_text)

    def run(self):
        """运行程序"""
        try:
            # 绑定快捷键
            self.root.bind('<Control-s>', lambda e: self.save_config())
            self.root.bind('<F1>', lambda e: self.show_help())

            self.root.mainloop()

        except KeyboardInterrupt:
            self.quit_application()
        except Exception as e:
            self.log(f"程序运行错误: {str(e)}", 'error')


class RegionSelector:
    """区域选择器"""
    def __init__(self, parent, callback):
        self.parent = parent
        self.callback = callback
        self.start_x = 0
        self.start_y = 0
        self.end_x = 0
        self.end_y = 0

        self.create_selection_window()

    def create_selection_window(self):
        """创建选择窗口"""
        # 隐藏父窗口
        self.parent.withdraw()

        # 创建全屏透明窗口
        self.selection_window = tk.Toplevel()
        self.selection_window.attributes('-fullscreen', True)
        self.selection_window.attributes('-alpha', 0.3)
        self.selection_window.attributes('-topmost', True)
        self.selection_window.configure(bg='black')

        # 创建画布
        self.canvas = tk.Canvas(self.selection_window,
                                highlightthickness=0,
                                bg='black')
        self.canvas.pack(fill="both", expand=True)

        # 绑定事件
        self.canvas.bind('<Button-1>', self.on_click)
        self.canvas.bind('<B1-Motion>', self.on_drag)
        self.canvas.bind('<ButtonRelease-1>', self.on_release)

        # 绑定键盘事件
        self.selection_window.bind('<Escape>', self.cancel_selection)
        self.selection_window.focus_set()

        # 显示提示
        self.canvas.create_text(
            self.selection_window.winfo_screenwidth() // 2,
            50,
            text="拖拽鼠标选择区域，按ESC取消",
            fill='white',
            font=('Arial', 16)
        )

    def on_click(self, event):
        """鼠标按下"""
        self.start_x = event.x
        self.start_y = event.y

    def on_drag(self, event):
        """鼠标拖拽"""
        # 清除之前的矩形
        self.canvas.delete("selection")

        # 绘制新矩形
        self.canvas.create_rectangle(
            self.start_x, self.start_y, event.x, event.y,
            outline='red', width=2, tags="selection"
        )

    def on_release(self, event):
        """鼠标释放"""
        self.end_x = event.x
        self.end_y = event.y

        # 计算区域
        x = min(self.start_x, self.end_x)
        y = min(self.start_y, self.end_y)
        width = abs(self.end_x - self.start_x)
        height = abs(self.end_y - self.start_y)

        # 关闭选择窗口
        self.selection_window.destroy()
        self.parent.deiconify()

        # 调用回调函数
        if width > 10 and height > 10:  # 最小区域限制
            self.callback((x, y, width, height))

    def cancel_selection(self, event):
        """取消选择"""
        self.selection_window.destroy()
        self.parent.deiconify()


class SettingsWindow:
    """设置窗口"""
    def __init__(self, parent, config, callback):
        self.parent = parent
        self.config = config.copy()
        self.callback = callback

        self.create_window()

    def create_window(self):
        """创建设置窗口"""
        self.window = tk.Toplevel(self.parent)
        self.window.title("设置")
        self.window.geometry("500x600")
        self.window.resizable(False, False)
        self.window.transient(self.parent)
        self.window.grab_set()

        # 创建笔记本控件
        notebook = ttk.Notebook(self.window)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        # 基本设置页
        self.create_basic_tab(notebook)

        # 城市设置页
        self.create_cities_tab(notebook)

        # 高级设置页
        self.create_advanced_tab(notebook)

        # 按钮区域
        self.create_buttons()

        # 居中显示
        self.center_window()

    def create_basic_tab(self, notebook):
        """创建基本设置页"""
        basic_frame = ttk.Frame(notebook)
        notebook.add(basic_frame, text="基本设置")

        # 检测间隔
        ttk.Label(basic_frame, text="检测间隔(秒):").grid(row=0, column=0, sticky="w", padx=10, pady=5)
        self.interval_var = tk.StringVar(value=str(self.config['check_interval']))
        ttk.Entry(basic_frame, textvariable=self.interval_var, width=10).grid(row=0, column=1, padx=10, pady=5)

        # 回复内容
        ttk.Label(basic_frame, text="回复内容:").grid(row=1, column=0, sticky="w", padx=10, pady=5)
        self.reply_var = tk.StringVar(value=self.config['reply_text'])
        ttk.Entry(basic_frame, textvariable=self.reply_var, width=20).grid(row=1, column=1, padx=10, pady=5)

        # 日志设置
        ttk.Label(basic_frame, text="日志设置:").grid(row=2, column=0, sticky="w", padx=10, pady=5)
        self.log_to_file_var = tk.BooleanVar(value=self.config.get('log_to_file', True))
        ttk.Checkbutton(basic_frame, text="保存到文件", variable=self.log_to_file_var).grid(row=2, column=1, sticky="w", padx=10, pady=5)

        # 自动启动
        ttk.Label(basic_frame, text="启动设置:").grid(row=3, column=0, sticky="w", padx=10, pady=5)
        self.auto_start_var = tk.BooleanVar(value=self.config.get('auto_start', False))
        ttk.Checkbutton(basic_frame, text="程序启动时自动开始监控", variable=self.auto_start_var).grid(row=3, column=1, sticky="w", padx=10, pady=5)

    def create_cities_tab(self, notebook):
        """创建城市设置页"""
        cities_frame = ttk.Frame(notebook)
        notebook.add(cities_frame, text="城市设置")

        ttk.Label(cities_frame, text="监控城市列表 (每行一个城市):").pack(anchor="w", padx=10, pady=5)

        # 城市列表文本框
        text_frame = ttk.Frame(cities_frame)
        text_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.cities_text = tk.Text(text_frame, height=20, width=40)
        scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=self.cities_text.yview)
        self.cities_text.configure(yscrollcommand=scrollbar.set)

        self.cities_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # 填入当前城市列表
        cities_text = '\n'.join(self.config['cities'])
        self.cities_text.insert("1.0", cities_text)

        # 按钮区域
        btn_frame = ttk.Frame(cities_frame)
        btn_frame.pack(fill="x", padx=10, pady=5)

        ttk.Button(btn_frame, text="恢复默认", command=self.restore_default_cities).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="清空列表", command=self.clear_cities).pack(side="left", padx=5)

    def create_advanced_tab(self, notebook):
        """创建高级设置页"""
        advanced_frame = ttk.Frame(notebook)
        notebook.add(advanced_frame, text="高级设置")

        # OCR置信度
        ttk.Label(advanced_frame, text="OCR置信度:").grid(row=0, column=0, sticky="w", padx=10, pady=5)
        self.ocr_confidence_var = tk.StringVar(value=str(self.config.get('ocr_confidence', 60)))
        ttk.Entry(advanced_frame, textvariable=self.ocr_confidence_var, width=10).grid(row=0, column=1, padx=10, pady=5)
        ttk.Label(advanced_frame, text="(0-100)").grid(row=0, column=2, sticky="w", padx=5, pady=5)

        # 窗口标题
        ttk.Label(advanced_frame, text="窗口标题:").grid(row=1, column=0, sticky="w", padx=10, pady=5)
        self.window_title_var = tk.StringVar(value=self.config.get('window_title', '微信群监控工具'))
        ttk.Entry(advanced_frame, textvariable=self.window_title_var, width=30).grid(row=1, column=1, columnspan=2, sticky="w", padx=10, pady=5)

    def create_buttons(self):
        """创建按钮区域"""
        btn_frame = ttk.Frame(self.window)
        btn_frame.pack(fill="x", padx=10, pady=10)

        ttk.Button(btn_frame, text="确定", command=self.save_settings).pack(side="right", padx=5)
        ttk.Button(btn_frame, text="取消", command=self.cancel_settings).pack(side="right", padx=5)
        ttk.Button(btn_frame, text="应用", command=self.apply_settings).pack(side="right", padx=5)

    def restore_default_cities(self):
        """恢复默认城市列表"""
        default_cities = [
            '天津', '重庆', '北京', '杭州', '烟台', '郑州', '沈阳', '温州',
            '南昌', '深圳', '广州', '太原', '福州', '南宁', '呼和浩特',
            '上海', '长春', '西安', '大连', '石家庄', '青岛'
        ]

        self.cities_text.delete("1.0", tk.END)
        self.cities_text.insert("1.0", '\n'.join(default_cities))

    def clear_cities(self):
        """清空城市列表"""
        self.cities_text.delete("1.0", tk.END)

    def get_cities_from_text(self):
        """从文本框获取城市列表"""
        cities_text = self.cities_text.get("1.0", tk.END).strip()
        cities = [city.strip() for city in cities_text.split('\n') if city.strip()]
        return cities

    def apply_settings(self):
        """应用设置"""
        try:
            # 更新配置
            self.config['check_interval'] = float(self.interval_var.get())
            self.config['reply_text'] = self.reply_var.get()
            self.config['cities'] = self.get_cities_from_text()
            self.config['log_to_file'] = self.log_to_file_var.get()
            self.config['auto_start'] = self.auto_start_var.get()
            self.config['ocr_confidence'] = int(self.ocr_confidence_var.get())
            self.config['window_title'] = self.window_title_var.get()

            # 验证配置
            if self.config['check_interval'] < 1:
                raise ValueError("检测间隔不能小于1秒")

            if not self.config['cities']:
                raise ValueError("城市列表不能为空")

            if not (0 <= self.config['ocr_confidence'] <= 100):
                raise ValueError("OCR置信度必须在0-100之间")

            # 调用回调函数
            self.callback(self.config)

            messagebox.showinfo("成功", "设置已应用")

        except ValueError as e:
            messagebox.showerror("错误", f"设置无效: {str(e)}")
        except Exception as e:
            messagebox.showerror("错误", f"应用设置失败: {str(e)}")

    def save_settings(self):
        """保存设置并关闭"""
        self.apply_settings()
        self.window.destroy()

    def cancel_settings(self):
        """取消设置"""
        self.window.destroy()

    def center_window(self):
        """窗口居中"""
        self.window.update_idletasks()
        width = self.window.winfo_width()
        height = self.window.winfo_height()
        x = (self.window.winfo_screenwidth() // 2) - (width // 2)
        y = (self.window.winfo_screenheight() // 2) - (height // 2)
        self.window.geometry(f"{width}x{height}+{x}+{y}")


def main():
    """主函数"""
    print("=" * 60)
    print("微信群监控工具 - 专业版")
    print("功能：自动检测微信群中的城市名称并回复'2'")
    print("=" * 60)

    # 检查依赖
    try:
        import pyautogui
        import pytesseract
        import pystray
        from PIL import Image
        print("✓ 所有依赖库已安装")
    except ImportError as e:
        print(f"✗ 缺少依赖库: {e}")
        print("请安装所需依赖:")
        print("pip install pyautogui pytesseract pillow pystray")
        return


    print("启动程序...")

    try:
        # 创建并运行应用
        app = WeChatMonitorPro()
        app.run()
    except KeyboardInterrupt:
        print("程序被用户中断")
    except Exception as e:
        print(f"程序运行错误: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()