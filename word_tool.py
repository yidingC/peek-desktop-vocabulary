import sys
import csv
import os
import re
import json
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QLabel, 
    QFileDialog, QMessageBox, QWidget, QVBoxLayout, QHBoxLayout,
    QSpacerItem, QSizePolicy, QListWidget, QDialog, QListWidgetItem,
    QStackedWidget
)
from PyQt6.QtCore import Qt, QPropertyAnimation, QPoint, QTimer, QEasingCurve, QSize
from PyQt6.QtGui import QIcon, QFont, QCursor, QPainter, QColor, QBrush, QFontDatabase, QKeyEvent

class RoundedWindow(QMainWindow):
    """带圆角的窗口基类"""
    def __init__(self, radius=10):
        super().__init__()
        self.radius = radius
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        try:
            # 尝试从当前目录加载图标
            if os.path.exists("icon.ico"):
                self.setWindowIcon(QIcon("icon.ico"))
            elif os.path.exists("icon.png"):
                self.setWindowIcon(QIcon("icon.png"))
        except Exception as e:
             print(f"加载图标失败：{e}")
    def paintEvent(self, event):
        try:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setBrush(QBrush(QColor("#F5F5F7")))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(self.rect(), self.radius, self.radius)
        except Exception as e:
            print(f"绘制窗口出错：{e}")


class WordListDialog(QDialog):
    """单词列表对话框 - 使用系统边框"""
    def __init__(self, parent=None, words=None, system_font="Arial", title="单词列表"):
        super().__init__(parent)
        self.words = words or []
        self.selected_index = -1
        self.system_font = system_font
        
        # 使用系统边框
        self.setWindowTitle(title)
        self.setFixedSize(300, 280)
        
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # 列表区域
        self.word_list = QListWidget()
        self.word_list.setStyleSheet("""
            QListWidget {
                background-color: white;
                border-radius: 5px;
                border: 1px solid #E2E2E7;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #F0F0F0;
                font-size: 12px;
            }
            QListWidget::item:selected {
                background-color: #007AFF;
                color: white;
                border-radius: 3px;
            }
            QListWidget::item:hover {
                background-color: #F0F0F0;
                border-radius: 3px;
            }
        """)
        
        # 填充单词列表
        for i, word_data in enumerate(self.words):
            item_text = f"{i+1}. {word_data['word']} - {word_data['meaning'][:20]}{'...' if len(word_data['meaning']) > 20 else ''}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, i)  # 保存原始索引
            self.word_list.addItem(item)
        
        # 连接点击事件
        self.word_list.itemClicked.connect(self.on_item_clicked)
        
        layout.addWidget(self.word_list)
        
    def on_item_clicked(self, item):
        """当点击列表项时"""
        self.selected_index = item.data(Qt.ItemDataRole.UserRole)
        self.accept()  # 关闭对话框并返回Accepted


class WordToolWindow(RoundedWindow):
    def __init__(self):
        try:
            super().__init__(radius=10)
            self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            self.version = "1.0.1"
            self.setWindowTitle(f"单词悬浮窗 v{self.version}")
            self.setFixedSize(350, 320)
            self.dragging = False
            self.drag_start_pos = QPoint()
            self.words = []
            self.current_index = 0
            self.difficult_words = []  # 难词本，现在存储完整的单词信息
            self.current_mode = "all"  # 当前模式："all" 或 "difficult"
            self.current_difficult_index = 0  # 难词本当前索引
            self.error_mode = False  # 新增：错误页面模式标志
            
            # 初始化 title_bar 为 None，避免在 init_ui 前被访问
            self.title_bar = None
            
            # 配置文件路径
            self.config_dir = os.path.join(os.path.expanduser("~"), ".word_tool")
            print(f"配置目录: {self.config_dir}")
            self.last_path_file = os.path.join(self.config_dir, "last_csv_path.txt")
            self.current_index_file = os.path.join(self.config_dir, "current_index.txt")
            self.difficult_words_file = os.path.join(self.config_dir, "difficult_words.json")  # 改为JSON格式
            self.difficult_index_file = os.path.join(self.config_dir, "difficult_index.txt")
            self.current_mode_file = os.path.join(self.config_dir, "current_mode.txt")
            self._ensure_config_dir()
            
            # 获取系统字体
            self.system_font = self.get_system_font()
            
            # 悬停计时器
            self.hover_timer = QTimer()
            self.hover_timer.setSingleShot(True)
            self.hover_timer.timeout.connect(self.show_meaning_on_hover)
            
            # 键盘显示释义计时器
            self.key_show_timer = QTimer()
            self.key_show_timer.setSingleShot(True)
            self.key_show_timer.timeout.connect(self.hide_meaning_by_key)

            # 先加载配置，再初始化UI
            self.current_mode = self.load_current_mode()  # 加载当前模式
            self.load_difficult_words()  # 加载难词本
            self.current_difficult_index = self.load_difficult_index()  # 加载难词本索引
            self.current_index = self.load_current_index()  # 加载当前索引
            
            self.init_ui()
            self.center_window()  # 窗口居中
            self.load_last_file()  # 最后加载文件
            
        except Exception as e:
            QMessageBox.critical(None, "启动失败", f"初始化错误：{str(e)}")
            sys.exit(1)
    
    def keyPressEvent(self, event: QKeyEvent):
        """处理键盘事件"""
        if event.key() == Qt.Key.Key_F11:
            self.toggle_error_mode()
        elif event.key() in (Qt.Key.Key_A, Qt.Key.Key_Left):
            # 上一个单词
            self.show_prev_word()
        elif event.key() in (Qt.Key.Key_D, Qt.Key.Key_Right):
            # 下一个单词
            self.show_next_word()
        elif event.key() in (Qt.Key.Key_W, Qt.Key.Key_Up):
            # 显示释义3秒
            self.show_meaning_by_key()
        elif event.key() in (Qt.Key.Key_S, Qt.Key.Key_Down):
            # 加入/拿出难词本
            self.toggle_difficult_word()
        else:
            super().keyPressEvent(event)

    def toggle_error_mode(self):
        """切换错误页面模式"""
        self.error_mode = not self.error_mode
        
        if self.error_mode:
            # 切换到错误页面
            self.show_error_page()
        else:
            # 切换回正常页面
            self.show_normal_page()

    def show_error_page(self):
        """显示错误页面"""
        # 使用堆叠窗口来管理页面，避免删除问题
        if not hasattr(self, 'error_container') or not self.error_container:
            self.create_error_page()
        
        self.stacked_widget.setCurrentIndex(1)  # 切换到错误页面

    def create_error_page(self):
        """创建错误页面"""
        self.error_container = QWidget()
        self.error_container.setStyleSheet("background: #F5F5F7;")
        
        error_layout = QVBoxLayout(self.error_container)
        error_layout.setContentsMargins(20, 20, 20, 20)
        error_layout.setSpacing(15)
        
        # 错误图标
        error_icon = QLabel("⚠️")
        error_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        error_icon.setStyleSheet("font-size: 48px;")
        error_layout.addWidget(error_icon)
        
        # 错误标题
        error_title = QLabel("应用程序错误")
        error_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        error_title.setStyleSheet("""
            font-size: 18px; 
            color: #1D1D1F; 
            font-weight: bold;
            margin: 10px 0;
        """)
        error_title.setFont(QFont(self.system_font, 18, QFont.Weight.Bold))
        error_layout.addWidget(error_title)
        
        # 错误代码
        error_code = QLabel("错误代码: 0x80070005")
        error_code.setAlignment(Qt.AlignmentFlag.AlignCenter)
        error_code.setStyleSheet("font-size: 12px; color: #6E6E73;")
        error_code.setFont(QFont(self.system_font, 12, QFont.Weight.Normal))
        error_layout.addWidget(error_code)
        
        # 分隔线
        divider = QWidget()
        divider.setFixedHeight(1)
        divider.setStyleSheet("background-color: #E2E2E7;")
        error_layout.addWidget(divider)
        
        # 有趣的错误信息
        error_message = QLabel("Don't go gentle into that good night —\nbut maybe close this app first.")
        error_message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        error_message.setStyleSheet("""
            font-size: 14px; 
            color: #3A3A3C; 
            line-height: 1.5;
            margin: 15px 0;
            font-style: italic;
            min-height: 60px;
        """)
        error_message.setFont(QFont(self.system_font, 14, QFont.Weight.Normal))
        error_message.setWordWrap(True)
        error_layout.addWidget(error_message)
        
        # 添加弹性空间
        error_layout.addStretch(1)
        
        # 将错误页面添加到堆叠窗口
        self.stacked_widget.addWidget(self.error_container)

    def show_normal_page(self):
        """显示正常页面"""
        # 切换到正常页面
        self.stacked_widget.setCurrentIndex(0)

    def showEvent(self, event):
        """窗口显示事件，用于居中窗口"""
        super().showEvent(event)
        self.center_window()
        
    def center_window(self):
        """将窗口居中显示"""
        screen_geometry = QApplication.primaryScreen().availableGeometry()
        window_geometry = self.frameGeometry()
        center_point = screen_geometry.center()
        window_geometry.moveCenter(center_point)
        self.move(window_geometry.topLeft())

    def get_system_font(self):
        """获取系统默认字体"""
        try:
            # 尝试一些常见的系统字体
            common_fonts = [
                "Microsoft YaHei UI",  # Windows 中文
                "Segoe UI",            # Windows 英文
                "PingFang SC",         # macOS 中文
                "San Francisco",       # macOS 英文
                "Arial",               # 通用
                "Helvetica",           # 通用
                "SimSun",              # 宋体
                "SimHei"               # 黑体
            ]
            
            # 检查哪些字体可用
            available_fonts = QFontDatabase.families()
            for font in common_fonts:
                if font in available_fonts:
                    return font
            
            # 如果没有找到常见字体，使用第一个可用字体
            if available_fonts:
                return available_fonts[0]
            else:
                return "Arial"  # 最后的后备方案
                
        except Exception as e:
            print(f"获取系统字体出错：{e}")
            return "Arial"
    def set_window_icon(self):
        """设置窗口图标"""
        try:
            # 尝试从多个可能的位置加载图标
            possible_paths = [
                "icon.ico",  # 当前目录
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico"),  # 脚本所在目录
                os.path.join(os.getcwd(), "icon.ico"),  # 工作目录
            ]
        
            for icon_path in possible_paths:
                if os.path.exists(icon_path):
                   self.setWindowIcon(QIcon(icon_path))
                   print(f"已设置窗口图标: {icon_path}")
                   return
        
            print("未找到图标文件，使用默认图标")
        except Exception as e:
            print(f"设置窗口图标失败：{e}")

    def _ensure_config_dir(self):
        try:
            if not os.path.exists(self.config_dir):
                os.makedirs(self.config_dir, exist_ok=True)
        except PermissionError:
            temp_dir = os.path.join(os.environ.get("TEMP", "/tmp"), ".word_tool")
            self.config_dir = temp_dir
            self.last_path_file = os.path.join(self.config_dir, "last_csv_path.txt")
            self.current_index_file = os.path.join(self.config_dir, "current_index.txt")
            self.difficult_words_file = os.path.join(self.config_dir, "difficult_words.json")
            self.difficult_index_file = os.path.join(self.config_dir, "difficult_index.txt")
            self.current_mode_file = os.path.join(self.config_dir, "current_mode.txt")
            os.makedirs(self.config_dir, exist_ok=True)
            QMessageBox.warning(None, "权限提示", f"已切换到临时目录：\n{temp_dir}")
        except Exception as e:
            QMessageBox.warning(None, "目录创建失败", f"配置文件夹创建出错：{str(e)}")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # 检查 title_bar 是否存在且包含点击位置
            if hasattr(self, 'title_bar') and self.title_bar and self.title_bar.geometry().contains(event.pos()):
                self.dragging = True
                self.drag_start_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                event.accept()

    def mouseMoveEvent(self, event):
        if hasattr(self, 'dragging') and self.dragging and event.buttons() == Qt.MouseButton.LeftButton:
            new_pos = event.globalPosition().toPoint() - self.drag_start_pos
            self.move(new_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        if hasattr(self, 'dragging'):
            self.dragging = False

    def closeEvent(self, event):
        """重写关闭事件，保存当前进度"""
        print("正在保存数据...")
        print(f"当前难词本: {len(self.difficult_words)}个单词")
    
        # 确保数据一致性
        self.save_current_index()
        self.save_difficult_words()
        self.save_difficult_index()
        self.save_current_mode()
    
        print("数据保存完成")
        event.accept()
        
    def save_current_index(self):
        """保存当前单词索引到文件"""
        try:
            with open(self.current_index_file, "w", encoding="utf-8") as f:
                f.write(str(self.current_index))
        except Exception as e:
            print(f"保存进度出错：{e}")

    def load_current_index(self):
        """从文件加载当前单词索引"""
        try:
            if not os.path.exists(self.current_index_file):
                return 0
                
            with open(self.current_index_file, "r", encoding="utf-8") as f:
                index_str = f.read().strip()
                if index_str:
                    return int(index_str)
        except Exception as e:
            print(f"加载进度出错：{e}")
        return 0

    def save_difficult_words(self):
        """保存难词本到文件 - 使用JSON格式"""
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(self.difficult_words_file), exist_ok=True)
        
            print(f"保存难词本，当前难词数量: {len(self.difficult_words)}")
            with open(self.difficult_words_file, "w", encoding="utf-8") as f:
                json.dump(self.difficult_words, f, ensure_ascii=False, indent=2)
            print(f"难词本已保存到: {self.difficult_words_file}")
        except Exception as e:
            print(f"保存难词本出错：{e}")
            # 尝试使用备用路径
            try:
                backup_file = os.path.join(os.getcwd(), "difficult_words_backup.json")
                with open(backup_file, "w", encoding="utf-8") as f:
                    json.dump(self.difficult_words, f, ensure_ascii=False, indent=2)
                print(f"难词本已备份到: {backup_file}")
            except Exception as backup_e:
                print(f"难词本备份也失败: {backup_e}")

    def load_difficult_words(self):
        """从文件加载难词本 - 使用JSON格式"""
        try:
            # 优先尝试备份文件
            backup_file = os.path.join(os.getcwd(), "difficult_words_backup.json")
            if os.path.exists(backup_file):
                print("从备份文件加载难词本")
                file_to_load = backup_file
            elif os.path.exists(self.difficult_words_file):
                print("从主文件加载难词本")
                file_to_load = self.difficult_words_file
            else:
                print("难词本文件不存在")
                self.difficult_words = []
                return
                
            with open(file_to_load, "r", encoding="utf-8") as f:
                loaded_words = json.load(f)
            
            # 确保加载的是列表
            if isinstance(loaded_words, list):
                self.difficult_words = loaded_words
            else:
                print("难词本文件格式错误，重置为空列表")
                self.difficult_words = []
                
            print(f"难词本已加载，共{len(self.difficult_words)}个单词")
            
        except Exception as e:
            print(f"加载难词本出错：{e}")
            self.difficult_words = []
        
        # 确保在UI初始化前也更新按钮状态
        if hasattr(self, 'difficult_list_btn'):
            self.update_difficult_list_button()
            
    def save_difficult_index(self):
        """保存难词本当前索引到文件"""
        try:
            with open(self.difficult_index_file, "w", encoding="utf-8") as f:
                f.write(str(self.current_difficult_index))
        except Exception as e:
            print(f"保存难词本索引出错：{e}")

    def load_difficult_index(self):
        """从文件加载难词本当前索引"""
        try:
            if not os.path.exists(self.difficult_index_file):
                return 0
                
            with open(self.difficult_index_file, "r", encoding="utf-8") as f:
                index_str = f.read().strip()
                if index_str:
                    return int(index_str)
        except Exception as e:
            print(f"加载难词本索引出错：{e}")
        return 0

    def save_current_mode(self):
        """保存当前模式到文件"""
        try:
            with open(self.current_mode_file, "w", encoding="utf-8") as f:
                f.write(self.current_mode)
        except Exception as e:
            print(f"保存当前模式出错：{e}")

    def load_current_mode(self):
        """从文件加载当前模式"""
        try:
            if not os.path.exists(self.current_mode_file):
                return "all"
                
            with open(self.current_mode_file, "r", encoding="utf-8") as f:
                mode = f.read().strip()
                if mode in ["all", "difficult"]:
                    return mode
        except Exception as e:
            print(f"加载当前模式出错：{e}")
        return "all"

    def update_difficult_list_button(self):
        """更新难词本列表按钮状态"""
        if hasattr(self, 'difficult_list_btn'):
            has_difficult_words = len(self.difficult_words) > 0
            self.difficult_list_btn.setEnabled(has_difficult_words)
            # 更新按钮样式以反映状态
            if has_difficult_words:
                self.difficult_list_btn.setStyleSheet("""
                    QPushButton {
                        color: #FF9500;
                        background: transparent;
                        border-radius: 12px;
                        width: 20px;
                        height: 20px;
                        font-size: 12px;
                    }
                    QPushButton:hover {
                        background-color: #E2E2E7;
                    }
                """)
            else:
                self.difficult_list_btn.setStyleSheet("""
                    QPushButton {
                        color: #949494;
                        background: transparent;
                        border-radius: 12px;
                        width: 20px;
                        height: 20px;
                        font-size: 12px;
                    }
                    QPushButton:disabled {
                        color: #C0C0C0;
                    }
                """)
            print(f"难词本按钮状态: {'启用' if has_difficult_words else '禁用'}, 难词数量: {len(self.difficult_words)}")
            
    def init_ui(self):
        try:
            # 使用堆叠窗口来管理多个页面
            self.stacked_widget = QStackedWidget()
            self.setCentralWidget(self.stacked_widget)
            
            # 创建主容器（正常页面）
            self.main_container = QWidget()
            self.main_container.setStyleSheet("background: transparent;")
            main_layout = QVBoxLayout(self.main_container)
            main_layout.setContentsMargins(5, 5, 5, 5)
            main_layout.setSpacing(0)

            # 顶部标题栏 - 删除标题文字
            self.title_bar = QWidget()
            self.title_bar.setFixedHeight(32)
            self.title_bar.setStyleSheet("background: transparent;")
            title_layout = QHBoxLayout(self.title_bar)
            title_layout.setContentsMargins(8, 6, 8, 6)
            title_layout.setSpacing(8)
            
            title_spacer_left = QWidget()
            title_spacer_left.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            
            # 删除标题标签，只保留空白
            self.title_label = QLabel("", self)
            self.title_label.setStyleSheet("color: #1D1D1F; font-size: 13px;")
            self.title_label.setFont(QFont(self.system_font, 13, QFont.Weight.Normal))
            self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            # 右上角按钮 - 只保留两个按钮
            self.min_btn = QPushButton("", self)
            self.min_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self.min_btn.setStyleSheet("""
                QPushButton { 
                    background-color: #14CD59; 
                    border-radius: 8px; 
                    width: 16px; 
                    height: 16px; 
                }
                QPushButton:hover { 
                    background-color: #34C759; 
                }
            """)
            self.min_btn.clicked.connect(self.showMinimized)
            self.min_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            self.min_btn.setFixedSize(16, 16)
            
            self.close_btn = QPushButton("", self)
            self.close_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self.close_btn.setStyleSheet("""
                QPushButton { 
                    background-color: #FF5F58; 
                    border-radius: 8px; 
                    width: 16px; 
                    height: 16px; 
                }
                QPushButton:hover { 
                    background-color: #FF3B30; 
                }
            """)
            self.close_btn.clicked.connect(self.close)
            self.close_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            self.close_btn.setFixedSize(16, 16)
            
            title_layout.addWidget(title_spacer_left)
            title_layout.addWidget(self.title_label)
            title_layout.addWidget(self.min_btn)
            title_layout.addWidget(self.close_btn)
            main_layout.addWidget(self.title_bar)

            # 中间内容区
            content_area = QWidget()
            content_area.setStyleSheet("background: transparent;")
            content_layout = QVBoxLayout(content_area)
            content_layout.setContentsMargins(20, 10, 20, 10)
            content_layout.setSpacing(8)
            
            # 单词显示
            self.word_label = QLabel("请导入单词库", self)
            self.word_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.word_label.setStyleSheet("""
                font-size: 24px; 
                color: #1D1D1F; 
                margin: 5px 0;
                background-color: transparent;
            """)
            self.word_label.setFont(QFont(self.system_font, 24, QFont.Weight.DemiBold))
            
            # 音标
            self.phonetic_label = QLabel("", self)
            self.phonetic_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.phonetic_label.setStyleSheet("font-size: 14px; color: #6E6E73;")
            self.phonetic_label.setFont(QFont(self.system_font, 14, QFont.Weight.Normal))
            
            # 词性
            self.part_label = QLabel("", self)
            self.part_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.part_label.setStyleSheet("font-size: 14px; color: #6E6E73;")
            self.part_label.setFont(QFont(self.system_font, 14, QFont.Weight.Medium))
            
            # 释义区域 - 悬停在这里显示释义
            self.meaning_area = QWidget()
            self.meaning_area.setStyleSheet("""
                background-color: #F0F0F0;
                border-radius: 5px;
                min-height: 60px;
            """)
            self.meaning_area.setMouseTracking(True)  # 启用鼠标跟踪
            
            meaning_layout = QVBoxLayout(self.meaning_area)
            meaning_layout.setContentsMargins(5, 5, 5, 5)
            
            self.meaning_label = QLabel("", self)
            self.meaning_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.meaning_label.setStyleSheet("""
                font-size: 15px; 
                color: #3A3A3C; 
                line-height: 1.5;
                background-color: transparent;
            """)
            self.meaning_label.setWordWrap(True)
            self.meaning_label.setFont(QFont(self.system_font, 15, QFont.Weight.Normal))
            
            meaning_layout.addWidget(self.meaning_label)
            
            # 进度显示
            self.progress_label = QLabel("", self)
            self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.progress_label.setStyleSheet("font-size: 12px; color: #8E8E93;")
            self.progress_label.setFont(QFont(self.system_font, 12, QFont.Weight.Normal))
            
            # 功能按钮 - 调整顺序
            btn_area = QWidget()
            btn_layout = QHBoxLayout(btn_area)
            btn_layout.setContentsMargins(0, 5, 0, 0)
            btn_layout.setSpacing(10)
            
            self.prev_btn = QPushButton("上一个", self)
            self.prev_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self.prev_btn.setStyleSheet(self.get_btn_style())
            self.prev_btn.setEnabled(False)
            self.prev_btn.clicked.connect(self.show_prev_word)
            self.prev_btn.setFont(QFont(self.system_font, 12, QFont.Weight.Normal))
            
            # 难词本按钮 - 使用浅蓝色
            self.difficult_btn = QPushButton("加入难词本", self)
            self.difficult_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self.difficult_btn.setStyleSheet(self.get_btn_style(color="#5AC8FA"))  # 浅蓝色
            self.difficult_btn.setEnabled(False)
            self.difficult_btn.clicked.connect(self.toggle_difficult_word)
            self.difficult_btn.setFont(QFont(self.system_font, 12, QFont.Weight.Normal))
            
            self.next_btn = QPushButton("下一个", self)
            self.next_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self.next_btn.setStyleSheet(self.get_btn_style())
            self.next_btn.setEnabled(False)
            self.next_btn.clicked.connect(self.show_next_word)
            self.next_btn.setFont(QFont(self.system_font, 12, QFont.Weight.Normal))
            
            # 调整按钮顺序：上一个、难词本、下一个
            btn_layout.addWidget(self.prev_btn)
            btn_layout.addWidget(self.difficult_btn)
            btn_layout.addWidget(self.next_btn)
            
            # 添加弹性空间，确保内容区能扩展
            content_layout.addWidget(self.word_label)
            content_layout.addWidget(self.phonetic_label)
            content_layout.addWidget(self.part_label)
            content_layout.addWidget(self.meaning_area)
            content_layout.addWidget(self.progress_label)  # 添加进度显示
            content_layout.addWidget(btn_area)
            
            # 设置内容区的权重，使其占用更多空间
            main_layout.addWidget(content_area, 1)  # 权重为1，会扩展

            # 底栏 - 减小高度
            bottom_bar = QWidget()
            bottom_bar.setFixedHeight(24)
            bottom_bar.setStyleSheet("background-color: transparent;")
            bottom_layout = QVBoxLayout(bottom_bar)
            bottom_layout.setContentsMargins(0, 0, 0, 0)
            bottom_layout.setSpacing(2)
            
            # 分隔线
            divider = QWidget()
            divider.setStyleSheet("background-color: #E2E2E7;")
            divider.setFixedHeight(1)
            bottom_layout.addWidget(divider)
            
            # 按钮容器
            btn_container = QWidget()
            btn_container.setFixedHeight(20)
            btn_layout = QHBoxLayout(btn_container)
            btn_layout.setContentsMargins(0, 0, 0, 0)
            
            left_spacer = QSpacerItem(20, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
            right_spacer = QSpacerItem(20, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
            
            # 列表按钮
            self.list_btn = QPushButton("≡", self)
            self.list_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self.list_btn.setStyleSheet("""
                QPushButton {
                    color: #949494;
                    background: transparent;
                    border-radius: 12px;
                    width: 20px;
                    height: 20px;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #E2E2E7;
                }
                QPushButton:disabled {
                    color: #C0C0C0;
                }
            """)
            self.list_btn.setFont(QFont(self.system_font, 12, QFont.Weight.Normal))
            self.list_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            self.list_btn.clicked.connect(self.show_word_list)
            self.list_btn.setFixedSize(20, 20)
            self.list_btn.setEnabled(False)  # 初始禁用
            
            # 加号按钮 - 修改为支持多种文件格式
            self.import_btn = QPushButton("+", self)
            self.import_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self.import_btn.setStyleSheet("""
                QPushButton {
                    color: #949494;
                    background: transparent;
                    border-radius: 12px;
                    width: 20px;
                    height: 20px;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #E2E2E7;
                }
            """)
            self.import_btn.setFont(QFont(self.system_font, 12, QFont.Weight.Normal))
            self.import_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            self.import_btn.clicked.connect(self.import_file)
            self.import_btn.setFixedSize(20, 20)
            
            # 难词本按钮 - 新增
            self.difficult_list_btn = QPushButton("★", self)
            self.difficult_list_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self.difficult_list_btn.setStyleSheet("""
                QPushButton {
                    color: #949494;
                    background: transparent;
                    border-radius: 12px;
                    width: 20px;
                    height: 20px;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #E2E2E7;
                }
                QPushButton:disabled {
                    color: #C0C0C0;
                }
            """)
            self.difficult_list_btn.setFont(QFont(self.system_font, 12, QFont.Weight.Normal))
            self.difficult_list_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            self.difficult_list_btn.clicked.connect(self.show_difficult_words)
            self.difficult_list_btn.setFixedSize(20, 20)
            
            btn_layout.addItem(left_spacer)
            btn_layout.addWidget(self.list_btn)
            btn_layout.addWidget(self.import_btn)
            btn_layout.addWidget(self.difficult_list_btn)  # 添加难词本按钮
            btn_layout.addItem(right_spacer)
            bottom_layout.addWidget(btn_container)
            
            main_layout.addWidget(bottom_bar)

            # 安装事件过滤器以处理悬停事件 - 现在应用到释义区域
            self.meaning_area.installEventFilter(self)
            
            # 修复：初始化时更新难词本按钮状态
            self.update_difficult_list_button()
            
            # 将主容器添加到堆叠窗口
            self.stacked_widget.addWidget(self.main_container)

        except Exception as e:
            raise Exception(f"UI初始化出错：{e}")

    def toggle_difficult_word(self):
        """切换当前单词的难词本状态"""
        if self.current_mode == "difficult" and self.difficult_words:
            # 难词本模式：直接移除当前单词
            current_word = self.difficult_words[self.current_difficult_index]
            
            # 从难词本中移除
            self.difficult_words = [word for word in self.difficult_words if word["word"] != current_word["word"]]
            
            # 更新按钮状态
            self.difficult_btn.setText("加入难词本")
            self.difficult_btn.setStyleSheet(self.get_btn_style(color="#5AC8FA"))  # 浅蓝色
            
            # 更新难词本列表
            self.update_difficult_list_button()
            
            # 如果难词本不为空，显示下一个单词
            if self.difficult_words:
                self.current_difficult_index = min(self.current_difficult_index, len(self.difficult_words) - 1)
                current_word = self.difficult_words[self.current_difficult_index]
                self.show_difficult_word(current_word)
            else:
                # 如果难词本为空，切换到所有单词模式
                self.current_mode = "all"
                if self.words:
                    self.show_current_word()
                else:
                    self.word_label.setText("请导入单词库")
                    self.phonetic_label.setText("")
                    self.part_label.setText("")
                    self.meaning_label.setText("")
                    self.progress_label.setText("")
            
            # 保存状态
            self.save_difficult_words()
            self.save_current_mode()
            
        elif self.current_mode == "all" and self.words:
            # 所有单词模式：切换加入/移除状态
            current_word = self.words[self.current_index]
            
            # 检查是否已经在难词本中
            is_in_difficult = False
            for word in self.difficult_words:
                if word["word"] == current_word["word"]:
                    is_in_difficult = True
                    break
            
            if is_in_difficult:
                # 如果已经在难词本中，则移除
                self.difficult_words = [word for word in self.difficult_words if word["word"] != current_word["word"]]
                self.difficult_btn.setText("加入难词本")
                self.difficult_btn.setStyleSheet(self.get_btn_style(color="#5AC8FA"))  # 浅蓝色
            else:
                # 如果不在难词本中，则加入
                self.difficult_words.append(current_word.copy())  # 使用copy避免引用问题
                self.difficult_btn.setText("已加入")
                self.difficult_btn.setStyleSheet(self.get_btn_style(color="#34C759"))  # 绿色
            
            # 更新难词本按钮状态
            self.update_difficult_list_button()
            
            # 保存难词本
            self.save_difficult_words()

    def update_difficult_button(self):
        """更新难词本按钮状态"""
        if self.current_mode == "difficult" and self.difficult_words:
            # 难词本模式：所有单词都是已加入状态
            self.difficult_btn.setText("已加入")
            self.difficult_btn.setStyleSheet(self.get_btn_style(color="#34C759"))  # 绿色
        elif self.current_mode == "all" and self.words:
            # 所有单词模式：检查当前单词是否在难词本中
            current_word = self.words[self.current_index]
            
            # 检查是否在难词本中
            is_in_difficult = False
            for word in self.difficult_words:
                if word["word"] == current_word["word"]:
                    is_in_difficult = True
                    break
            
            if is_in_difficult:
                self.difficult_btn.setText("已加入")
                self.difficult_btn.setStyleSheet(self.get_btn_style(color="#34C759"))  # 绿色
            else:
                self.difficult_btn.setText("加入难词本")
                self.difficult_btn.setStyleSheet(self.get_btn_style(color="#5AC8FA"))  # 浅蓝色

    def show_word_list(self):
        """显示单词列表对话框"""
        if not self.words:
            QMessageBox.warning(self, "提示", "请先导入单词库")
            return
            
        dialog = WordListDialog(self, self.words, self.system_font, "单词列表")
        
        # 计算对话框位置，使其显示在主窗口中心
        main_rect = self.geometry()
        dialog_rect = dialog.geometry()
        x = main_rect.center().x() - dialog_rect.width() / 2
        y = main_rect.center().y() - dialog_rect.height() / 2
        dialog.move(int(x), int(y))
        
        # 显示对话框
        result = dialog.exec()
        
        if result == QDialog.DialogCode.Accepted and dialog.selected_index >= 0:
            # 用户选择了一个单词
            self.current_mode = "all"  # 切换到单词列表模式
            self.current_index = dialog.selected_index
            self.show_current_word()
            self.meaning_label.setText("悬停显示释义")
            self.update_progress()
            self.save_current_index()
            self.save_current_mode()  # 保存当前模式

    def show_difficult_words(self):
        """显示难词本对话框"""
        if not self.difficult_words:
            QMessageBox.warning(self, "提示", "难词本为空")
            return
            
        dialog = WordListDialog(self, self.difficult_words, self.system_font, "难词本")
        
        # 计算对话框位置，使其显示在主窗口中心
        main_rect = self.geometry()
        dialog_rect = dialog.geometry()
        x = main_rect.center().x() - dialog_rect.width() / 2
        y = main_rect.center().y() - dialog_rect.height() / 2
        dialog.move(int(x), int(y))
        
        # 显示对话框
        result = dialog.exec()
        
        if result == QDialog.DialogCode.Accepted and dialog.selected_index >= 0:
            # 用户选择了一个单词
            self.current_mode = "difficult"  # 切换到难词本模式
            self.current_difficult_index = dialog.selected_index
            
            # 在难词本中显示选中的单词
            difficult_word = self.difficult_words[dialog.selected_index]
            self.show_difficult_word(difficult_word)
            
            self.meaning_label.setText("")
            self.update_progress()
            self.save_difficult_index()
            self.save_current_mode()  # 保存当前模式

    def show_difficult_word(self, word):
        """显示难词本中的单词"""
        self.word_label.setText(word["word"])
        self.phonetic_label.setText(f"[{word['phonetic']}]")
        self.part_label.setText(f"【{word['part']}】")
        # 难词本中的单词都是已加入状态
        self.difficult_btn.setText("已加入")
        self.difficult_btn.setStyleSheet(self.get_btn_style(color="#34C759"))  # 绿色

    def eventFilter(self, obj, event):
        """处理悬停事件"""
        if obj == self.meaning_area:
            if event.type() == event.Type.Enter:
                # 鼠标进入释义区域，停止键盘计时器并立即显示释义
                self.key_show_timer.stop()
                self.show_meaning_on_hover()  # 立即显示，不延迟
            elif event.type() == event.Type.Leave:
                # 鼠标离开释义区域，立即隐藏释义
                self.hover_timer.stop()
                self.meaning_label.setText("")
        
        return super().eventFilter(obj, event)
    
    def show_meaning_on_hover(self):
        """显示悬停释义"""
        try:
            if self.current_mode == "all" and self.words:
                current_word = self.words[self.current_index]
                self.meaning_label.setText(current_word["meaning"])
            elif self.current_mode == "difficult" and self.difficult_words:
                current_word = self.difficult_words[self.current_difficult_index]
                self.meaning_label.setText(current_word["meaning"])
        except Exception as e:
            print(f"显示悬停释义出错：{e}")
    
    def show_meaning_by_key(self):
        """通过按键显示释义"""
        try:
            # 如果鼠标已经在释义区域，则不处理按键显示
            if self.meaning_area.underMouse():
                return
                
            if self.current_mode == "all" and self.words:
                current_word = self.words[self.current_index]
                self.meaning_label.setText(current_word["meaning"])
            elif self.current_mode == "difficult" and self.difficult_words:
                current_word = self.difficult_words[self.current_difficult_index]
                self.meaning_label.setText(current_word["meaning"])
            else:
                return

            # 启动计时器，3秒后隐藏释义
            self.key_show_timer.start(3000)  # 3000毫秒=3秒
        except Exception as e:
            print(f"按键显示释义出错：{e}")
    
    def hide_meaning_by_key(self):
        """隐藏通过按键显示的释义"""
        try:
            # 只有当鼠标不在释义区域时才隐藏
            if not self.meaning_area.underMouse():
                self.meaning_label.setText("")
        except Exception as e:
            print(f"隐藏释义出错：{e}")

    def get_btn_style(self, color="#E2E2E7"):
        return f"""
            QPushButton {{
                background-color: {color};
                color: #1D1D1F;
                border: none;
                border-radius: 8px;
                padding: 6px 12px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: #D1D1D6;
            }}
        """

    def update_progress(self):
        """更新进度显示"""
        if self.current_mode == "all" and self.words:
            total = len(self.words)
            current = self.current_index + 1
            percentage = (current / total) * 100
            self.progress_label.setText(f"{current}/{total} ({percentage:.1f}%)")
        elif self.current_mode == "difficult" and self.difficult_words:
            total = len(self.difficult_words)
            current = self.current_difficult_index + 1
            percentage = (current / total) * 100
            self.progress_label.setText(f"难词: {current}/{total} ({percentage:.1f}%)")
        else:
            self.progress_label.setText("")

    def show_prev_word(self):
        try:
            # 停止所有计时器
            self.key_show_timer.stop()
            self.hover_timer.stop()
            
            if self.current_mode == "all" and self.words:
                self.current_index = (self.current_index - 1) % len(self.words)
                self.show_current_word()
                self.meaning_label.setText("")  # 切换单词时恢复默认文本
                self.update_progress()  # 更新进度显示
                self.update_difficult_button()  # 更新难词本按钮状态
                self.save_current_index()  # 保存当前进度
            elif self.current_mode == "difficult" and self.difficult_words:
                self.current_difficult_index = (self.current_difficult_index - 1) % len(self.difficult_words)
                difficult_word = self.difficult_words[self.current_difficult_index]
                self.show_difficult_word(difficult_word)
                self.meaning_label.setText("")  # 切换单词时恢复默认文本
                self.update_progress()  # 更新进度显示
                self.save_difficult_index()  # 保存难词本当前进度
        except Exception as e:
            QMessageBox.warning(self, "操作失败", f"上一个单词出错：{str(e)}")

    def show_next_word(self):
        try:
            # 停止所有计时器
            self.key_show_timer.stop()
            self.hover_timer.stop()
            
            if self.current_mode == "all" and self.words:
                self.current_index = (self.current_index + 1) % len(self.words)
                self.show_current_word()
                self.meaning_label.setText("")  # 切换单词时恢复默认文本
                self.update_progress()  # 更新进度显示
                self.update_difficult_button()  # 更新难词本按钮状态
                self.save_current_index()  # 保存当前进度
            elif self.current_mode == "difficult" and self.difficult_words:
                self.current_difficult_index = (self.current_difficult_index + 1) % len(self.difficult_words)
                difficult_word = self.difficult_words[self.current_difficult_index]
                self.show_difficult_word(difficult_word)
                self.meaning_label.setText("")  # 切换单词时恢复默认文本
                self.update_progress()  # 更新进度显示
                self.save_difficult_index()  # 保存难词本当前进度
        except Exception as e:
            QMessageBox.warning(self, "操作失败", f"下一个单词出错：{str(e)}")

    def show_current_word(self):
        try:
            if not self.words:
                return
            current_word = self.words[self.current_index]
            self.word_label.setText(current_word["word"])
            self.phonetic_label.setText(f"[{current_word['phonetic']}]")
            self.part_label.setText(f"【{current_word['part']}】")
            self.update_progress()  # 更新进度显示
            self.update_difficult_button()  # 更新难词本按钮状态
        except Exception as e:
            print(f"显示单词出错：{e}")

    def load_last_file(self):
        """加载上次导入的文件"""
        try:
            if not os.path.exists(self.last_path_file):
                return
            with open(self.last_path_file, "r", encoding="utf-8") as f:
                last_path = f.read().strip()
                if not last_path or not os.path.exists(last_path):
                    return
                self.auto_import_file(last_path)
        except PermissionError:
            QMessageBox.warning(self, "权限不足", f"无法读取配置文件：\n{self.last_path_file}")
        except Exception as e:
            print(f"加载上次文件出错：{e}")

    def auto_import_file(self, file_path):
        """自动导入文件"""
        try:
            ext = os.path.splitext(file_path)[1].lower()
            if ext == '.csv':
                new_words = self.parse_csv_file(file_path)
            elif ext == '.txt':
                new_words = self.parse_txt_file(file_path)
            elif ext == '.docx':
                new_words = self.parse_docx_file(file_path)
            else:
                return
                
            if not new_words:
                return
            
            print(f"自动导入文件: {file_path}, 单词数量: {len(new_words)}")
            
            self.words = new_words
            
            # 不再需要迁移难词本，因为难词本是独立存储的
            print(f"难词本独立存储，无需迁移，当前难词数量: {len(self.difficult_words)}")
            
            # 根据当前模式显示正确的单词
            if self.current_mode == "difficult" and self.difficult_words:
                # 如果当前模式是难词本且难词本不为空
                if 0 <= self.current_difficult_index < len(self.difficult_words):
                    difficult_word = self.difficult_words[self.current_difficult_index]
                    self.show_difficult_word(difficult_word)
                else:
                    # 如果索引无效，重置为0
                    self.current_difficult_index = 0
                    if self.difficult_words:
                        difficult_word = self.difficult_words[0]
                        self.show_difficult_word(difficult_word)
            else:
                # 如果是all模式，确保当前索引有效
                if self.current_index >= len(self.words):
                    self.current_index = 0
                self.show_current_word()
            
            self.prev_btn.setEnabled(True)
            self.next_btn.setEnabled(True)
            self.difficult_btn.setEnabled(True)
            self.list_btn.setEnabled(True)
            
            # 更新难词本按钮状态
            self.update_difficult_list_button()
            
            print(f"自动导入完成，当前难词本: {len(self.difficult_words)}个单词")
        except Exception as e:
            print(f"自动导入错误：{e}")

    def parse_csv_file(self, file_path):
        """解析CSV文件"""
        new_words = []
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for row_num, row in enumerate(csv.reader(f), 1):
                    if len(row) < 4:
                        continue
                    word, phonetic, part, meaning = [col.strip() for col in row[:4]]
                    if word:
                        new_words.append({"word": word, "phonetic": phonetic, "part": part, "meaning": meaning})
        except Exception as e:
            raise Exception(f"CSV文件解析错误：{str(e)}")
        return new_words

    def parse_txt_file(self, file_path):
        """解析TXT文件"""
        new_words = []
        try:
            # 尝试多种编码打开文件
            encodings = ['utf-8', 'gbk', 'gb2312', 'latin-1']
            content = None
            
            for encoding in encodings:
                try:
                    with open(file_path, "r", encoding=encoding) as f:
                        content = f.readlines()
                    break
                except UnicodeDecodeError:
                    continue
            
            if content is None:
                raise Exception("无法识别文件编码")
                
            for line_num, line in enumerate(content, 1):
                line = line.strip()
                if not line or line.startswith('#'):  # 跳过空行和注释行
                    continue
                
                # 尝试多种分隔符：制表符、逗号、竖线、分号
                separators = ['\t', ',', '|', ';']
                parts = None
                
                for sep in separators:
                    if sep in line:
                        parts = line.split(sep)
                        # 如果分割后部分数量不足，尝试下一个分隔符
                        if len(parts) >= 2:
                            break
                        else:
                            parts = None
                
                # 如果没有找到合适的分隔符，尝试按空格分割（但要注意释义中可能有空格）
                if parts is None:
                    parts = line.split(' ', 3)  # 最多分割成4部分
                
                # 确保有4个部分，不足的用空字符串填充
                while len(parts) < 4:
                    parts.append("")
                
                word, phonetic, part, meaning = [part.strip() for part in parts[:4]]
                if word:
                    new_words.append({
                        "word": word, 
                        "phonetic": phonetic, 
                        "part": part, 
                        "meaning": meaning
                    })
                    
        except Exception as e:
            raise Exception(f"TXT文件解析错误：{str(e)}")
        
        return new_words

    def parse_docx_file(self, file_path):
        """解析Word文档"""
        try:
            # 尝试导入python-docx库
            try:
                from docx import Document
            except ImportError:
                # 如果python-docx未安装，提示用户安装
                QMessageBox.information(self, "需要安装依赖", 
                    "要导入Word文档，需要安装python-docx库。\n\n"
                    "请在命令行中运行：\n"
                    "pip install python-docx")
                return []
                
            new_words = []
            doc = Document(file_path)
            
            for para in doc.paragraphs:
                line = para.text.strip()
                if not line:
                    continue
                
                # 尝试多种分隔符：制表符、逗号、竖线、分号
                separators = ['\t', ',', '|', ';']
                parts = None
                
                for sep in separators:
                    if sep in line:
                        parts = line.split(sep)
                        # 如果分割后部分数量不足，尝试下一个分隔符
                        if len(parts) >= 2:
                            break
                        else:
                            parts = None
                
                # 如果没有找到合适的分隔符，尝试按空格分割
                if parts is None:
                    parts = line.split(' ', 3)  # 最多分割成4部分
                
                # 确保有4个部分，不足的用空字符串填充
                while len(parts) < 4:
                    parts.append("")
                
                word, phonetic, part, meaning = [part.strip() for part in parts[:4]]
                if word:
                    new_words.append({"word": word, "phonetic": phonetic, "part": part, "meaning": meaning})
                    
        except Exception as e:
            raise Exception(f"Word文档解析错误：{str(e)}")
        return new_words

    def import_file(self):
        """导入文件 - 支持CSV、TXT和Word格式"""
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self, 
                "选择单词文件", 
                os.path.expanduser("~"), 
                "单词文件 (*.csv *.txt *.docx);;CSV文件 (*.csv);;文本文件 (*.txt);;Word文档 (*.docx);;所有文件 (*.*)"
            )
            if not file_path:
                return
                
            # 根据文件扩展名选择解析方法
            ext = os.path.splitext(file_path)[1].lower()
            if ext == '.csv':
                new_words = self.parse_csv_file(file_path)
            elif ext == '.txt':
                new_words = self.parse_txt_file(file_path)
            elif ext == '.docx':
                new_words = self.parse_docx_file(file_path)
            else:
                QMessageBox.warning(self, "不支持的文件格式", "请选择CSV、TXT或Word文件")
                return
                
            if not new_words:
                QMessageBox.warning(self, "提示", "无有效单词")
                return
                
            try:
                with open(self.last_path_file, "w", encoding="utf-8") as f:
                    f.write(file_path)
            except PermissionError:
                QMessageBox.warning(self, "权限不足", f"无法保存配置文件：\n{self.last_path_file}")
                
            self.words = new_words
            
            # 不再需要迁移难词本，因为难词本是独立存储的
            
            self.current_index = 0  # 导入新词库时重置进度
            self.current_difficult_index = 0  # 重置难词本索引
            self.current_mode = "all"  # 重置为单词列表模式
            
            self.show_current_word()
            self.prev_btn.setEnabled(True)
            self.next_btn.setEnabled(True)
            self.difficult_btn.setEnabled(True)  # 启用难词本按钮
            self.list_btn.setEnabled(True)  # 启用列表按钮
            
            # 修复：导入后更新难词本按钮状态
            self.update_difficult_list_button()
            
            self.save_current_index()  # 保存重置后的进度
            self.save_difficult_index()  # 保存重置后的难词本索引
            self.save_difficult_words()  # 保存难词本
            self.save_current_mode()  # 保存当前模式
            
            QMessageBox.information(self, "成功", 
                f"导入{len(new_words)}个单词\n"
                f"难词本独立存储，当前有{len(self.difficult_words)}个难词")
        except Exception as e:
            QMessageBox.critical(self, "导入失败", f"解析失败：{str(e)}")


if __name__ == "__main__":
    try:
        app = QApplication(sys.argv)
        
        # 设置应用程序图标（影响任务栏图标）
        try:
            # 优先使用程序目录中的相对路径，避免依赖开发者本机目录
            icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")
            if os.path.exists(icon_path):
                app.setWindowIcon(QIcon(icon_path))
                print(f"已设置应用程序图标: {icon_path}")
            else:
                # 尝试其他路径
                possible_paths = [
                    os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico"),
                    "icon.ico",
                    os.path.join(os.getcwd(), "icon.ico")
                ]
                
                for path in possible_paths:
                    if os.path.exists(path):
                        app.setWindowIcon(QIcon(path))
                        print(f"已设置应用程序图标: {path}")
                        break
                else:
                    print("未找到图标文件")
        except Exception as e:
            print(f"设置应用程序图标失败：{e}")
        
        window = WordToolWindow()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        print(f"程序崩溃：{e}")
        input("按回车退出...")
        sys.exit(1)

    def show_meaning_by_key(self):
        """通过按键显示释义"""
        # 如果鼠标已经在释义区域，则不处理按键显示（因为鼠标悬停已经显示）
        if self.meaning_area.underMouse():
            return
            
        if self.current_mode == "all" and self.words:
            current_word = self.words[self.current_index]
            self.meaning_label.setText(current_word["meaning"])
        elif self.current_mode == "difficult" and self.difficult_words:
            current_word = self.difficult_words[self.current_difficult_index]
            self.meaning_label.setText(current_word["meaning"])
        else:
            return

        # 启动计时器，3秒后隐藏释义
        self.key_show_timer.start(3000)  # 3000毫秒=3秒

    def hide_meaning_by_key(self):
        """隐藏通过按键显示的释义"""
        # 只有当鼠标不在释义区域时才隐藏
        if not self.meaning_area.underMouse():
            self.meaning_label.setText("")
