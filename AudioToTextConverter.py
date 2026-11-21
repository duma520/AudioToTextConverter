import os
import sys
import json
import logging
import threading
from pathlib import Path
from urllib.parse import urlparse
import requests

from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QTextEdit, QFileDialog, QProgressBar,
                             QLabel, QComboBox, QCheckBox, QGroupBox, QMessageBox,
                             QSplitter, QWidget, QScrollArea, QFrame)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSettings, QTimer
from PyQt5.QtGui import QFont, QPalette, QColor

# FunASR相关导入
try:
    from funasr import AutoModel
    FUNASR_AVAILABLE = True
except ImportError:
    FUNASR_AVAILABLE = False

class FunASRWorker(QThread):
    """FunASR处理线程"""
    progress_updated = pyqtSignal(int, str)
    result_updated = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)
    
    def __init__(self, audio_path, model_dir=None, use_proxy=False):
        super().__init__()
        self.audio_path = audio_path
        self.model_dir = model_dir
        self.use_proxy = use_proxy
        self.is_running = True
        self.model = None
        
    def run(self):
        try:
            # 设置代理
            if self.use_proxy:
                os.environ['http_proxy'] = 'http://127.0.0.1:20808'
                os.environ['https_proxy'] = 'http://127.0.0.1:20808'
            
            self.progress_updated.emit(10, "正在加载FunASR模型...")
            
            # 初始化模型
            try:
                if self.model_dir and os.path.exists(self.model_dir):
                    self.model = AutoModel(
                        model=self.model_dir,
                        model_revision="v2.0.4",
                        device="cpu",  # 使用CPU
                        disable_update=True
                    )
                else:
                    self.model = AutoModel(
                        model="paraformer-zh",
                        model_revision="v2.0.4",
                        device="cpu",  # 使用CPU
                        disable_update=True
                    )
            except Exception as e:
                self.progress_updated.emit(0, f"模型加载失败: {str(e)}")
                self.finished_signal.emit(False, f"模型加载失败: {str(e)}")
                return
            
            if not self.is_running:
                return
                
            self.progress_updated.emit(30, "正在分析音频文件...")
            
            # 检查音频文件是否存在
            if not os.path.exists(self.audio_path):
                self.finished_signal.emit(False, "音频文件不存在")
                return
            
            if not self.is_running:
                return
                
            self.progress_updated.emit(50, "正在进行语音识别...")
            
            # 执行语音识别
            try:
                result = self.model.generate(
                    input=self.audio_path,
                    batch_size_s=300,
                    hotword='魔搭社区'
                )
                
                if not self.is_running:
                    return
                    
                self.progress_updated.emit(80, "正在处理识别结果...")
                
                # 处理识别结果
                if result and len(result) > 0:
                    text_result = ""
                    for res in result:
                        if 'text' in res:
                            text_result += res['text'] + "\n"
                    
                    if text_result.strip():
                        self.result_updated.emit(text_result.strip())
                        self.progress_updated.emit(100, "识别完成")
                        self.finished_signal.emit(True, "识别完成")
                    else:
                        self.finished_signal.emit(False, "未识别到有效文本")
                else:
                    self.finished_signal.emit(False, "识别结果为空")
                    
            except Exception as e:
                self.finished_signal.emit(False, f"识别过程出错: {str(e)}")
                
        except Exception as e:
            self.finished_signal.emit(False, f"处理失败: {str(e)}")
    
    def stop(self):
        self.is_running = False

class AudioTranscriber(QMainWindow):
    def __init__(self):
        super().__init__()
        self.worker = None
        self.settings = QSettings("FunASR", "AudioTranscriber")
        self.init_ui()
        self.load_settings()
        
    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle("FunASR 音频转文字工具")
        self.setMinimumSize(1000, 700)
        
        # 设置图标
        if os.path.exists("icon.ico"):
            from PyQt5.QtGui import QIcon
            self.setWindowIcon(QIcon("icon.ico"))
        
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        # 创建顶部控制区域
        self.create_control_area(main_layout)
        
        # 创建分割器
        splitter = QSplitter(Qt.Vertical)
        
        # 创建文本显示区域
        self.create_text_area(splitter)
        
        # 创建进度区域
        self.create_progress_area(splitter)
        
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        main_layout.addWidget(splitter)
        
        # 创建底部按钮区域
        self.create_button_area(main_layout)
        
        # 设置样式
        self.apply_styles()
        
    def create_control_area(self, layout):
        """创建控制区域"""
        control_group = QGroupBox("控制设置")
        control_layout = QVBoxLayout(control_group)
        
        # 第一行：文件选择和模型设置
        file_layout = QHBoxLayout()
        
        # 文件选择
        file_select_layout = QVBoxLayout()
        file_select_layout.addWidget(QLabel("音频文件:"))
        file_btn_layout = QHBoxLayout()
        self.file_path_label = QLabel("未选择文件")
        self.file_path_label.setStyleSheet("background-color: #f0f0f0; padding: 5px; border: 1px solid #ccc;")
        self.file_path_label.setMinimumHeight(30)
        self.browse_btn = QPushButton("浏览...")
        self.browse_btn.clicked.connect(self.browse_audio_file)
        file_btn_layout.addWidget(self.file_path_label, 4)
        file_btn_layout.addWidget(self.browse_btn, 1)
        file_select_layout.addLayout(file_btn_layout)
        file_layout.addLayout(file_select_layout, 3)
        
        # 模型设置
        model_layout = QVBoxLayout()
        model_layout.addWidget(QLabel("模型路径:"))
        model_btn_layout = QHBoxLayout()
        self.model_path_label = QLabel("使用默认模型")
        self.model_path_label.setStyleSheet("background-color: #f0f0f0; padding: 5px; border: 1px solid #ccc;")
        self.model_path_label.setMinimumHeight(30)
        self.model_browse_btn = QPushButton("选择...")
        self.model_browse_btn.clicked.connect(self.browse_model_dir)
        model_btn_layout.addWidget(self.model_path_label, 4)
        model_btn_layout.addWidget(self.model_browse_btn, 1)
        model_layout.addLayout(model_btn_layout)
        file_layout.addLayout(model_layout, 3)
        
        control_layout.addLayout(file_layout)
        
        # 第二行：选项设置
        option_layout = QHBoxLayout()
        
        # 代理设置
        self.proxy_checkbox = QCheckBox("使用代理 (http://127.0.0.1:20808)")
        option_layout.addWidget(self.proxy_checkbox)
        
        # 实时显示
        self.realtime_checkbox = QCheckBox("实时显示识别结果")
        self.realtime_checkbox.setChecked(True)
        option_layout.addWidget(self.realtime_checkbox)
        
        option_layout.addStretch()
        control_layout.addLayout(option_layout)
        
        layout.addWidget(control_group)
    
    def create_text_area(self, splitter):
        """创建文本显示区域"""
        text_group = QGroupBox("识别结果")
        text_layout = QVBoxLayout(text_group)
        
        # 创建文本编辑框
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("识别结果将显示在这里...")
        self.text_edit.setAcceptRichText(False)
        
        # 设置字体
        font = QFont("Microsoft YaHei", 10)
        self.text_edit.setFont(font)
        
        text_layout.addWidget(self.text_edit)
        splitter.addWidget(text_group)
    
    def create_progress_area(self, splitter):
        """创建进度显示区域"""
        progress_group = QGroupBox("处理进度")
        progress_layout = QVBoxLayout(progress_group)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        
        # 状态标签
        self.status_label = QLabel("准备就绪")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("padding: 5px; background-color: #e8f4fd; border: 1px solid #b8daff;")
        
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.status_label)
        splitter.addWidget(progress_group)
    
    def create_button_area(self, layout):
        """创建按钮区域"""
        button_layout = QHBoxLayout()
        
        # 开始识别按钮
        self.start_btn = QPushButton("开始识别")
        self.start_btn.clicked.connect(self.start_transcription)
        self.start_btn.setMinimumHeight(35)
        
        # 停止按钮
        self.stop_btn = QPushButton("停止")
        self.stop_btn.clicked.connect(self.stop_transcription)
        self.stop_btn.setMinimumHeight(35)
        self.stop_btn.setEnabled(False)
        
        # 导出按钮
        self.export_btn = QPushButton("导出结果")
        self.export_btn.clicked.connect(self.export_result)
        self.export_btn.setMinimumHeight(35)
        self.export_btn.setEnabled(False)
        
        # 清空按钮
        self.clear_btn = QPushButton("清空结果")
        self.clear_btn.clicked.connect(self.clear_result)
        self.clear_btn.setMinimumHeight(35)
        
        button_layout.addWidget(self.start_btn)
        button_layout.addWidget(self.stop_btn)
        button_layout.addWidget(self.export_btn)
        button_layout.addWidget(self.clear_btn)
        
        layout.addLayout(button_layout)
    
    def apply_styles(self):
        """应用样式表"""
        style = """
        QMainWindow {
            background-color: #f5f5f5;
        }
        QGroupBox {
            font-weight: bold;
            font-size: 12px;
            border: 2px solid #cccccc;
            border-radius: 5px;
            margin-top: 1ex;
            padding-top: 10px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px 0 5px;
        }
        QPushButton {
            background-color: #4CAF50;
            border: none;
            color: white;
            padding: 8px 16px;
            text-align: center;
            text-decoration: none;
            font-size: 14px;
            margin: 4px 2px;
            border-radius: 4px;
            min-width: 80px;
        }
        QPushButton:hover {
            background-color: #45a049;
        }
        QPushButton:pressed {
            background-color: #3d8b40;
        }
        QPushButton:disabled {
            background-color: #cccccc;
            color: #666666;
        }
        QTextEdit {
            border: 1px solid #cccccc;
            border-radius: 4px;
            padding: 8px;
            font-family: "Microsoft YaHei", sans-serif;
        }
        QProgressBar {
            border: 1px solid #cccccc;
            border-radius: 4px;
            text-align: center;
            height: 20px;
        }
        QProgressBar::chunk {
            background-color: #4CAF50;
            border-radius: 3px;
        }
        QLabel {
            font-size: 12px;
        }
        """
        self.setStyleSheet(style)
    
    def browse_audio_file(self):
        """浏览音频文件"""
        file_filter = "音频文件 (*.wav *.mp3 *.m4a *.aac *.flac *.ogg *.wma *.amr *.aiff *.au);;所有文件 (*.*)"
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择音频文件", "", file_filter)
        
        if file_path:
            self.file_path_label.setText(file_path)
            self.settings.setValue("last_audio_dir", os.path.dirname(file_path))
    
    def browse_model_dir(self):
        """浏览模型目录"""
        model_dir = QFileDialog.getExistingDirectory(
            self, "选择模型目录", "", QFileDialog.ShowDirsOnly)
        
        if model_dir:
            self.model_path_label.setText(model_dir)
            self.settings.setValue("model_dir", model_dir)
        else:
            self.model_path_label.setText("使用默认模型")
            self.settings.remove("model_dir")
    
    def start_transcription(self):
        """开始语音识别"""
        if not FUNASR_AVAILABLE:
            QMessageBox.critical(self, "错误", "未安装FunASR库。请使用以下命令安装：\npip install funasr")
            return
        
        audio_file = self.file_path_label.text()
        if not audio_file or audio_file == "未选择文件":
            QMessageBox.warning(self, "警告", "请先选择音频文件")
            return
        
        if not os.path.exists(audio_file):
            QMessageBox.critical(self, "错误", "音频文件不存在")
            return
        
        # 更新按钮状态
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.export_btn.setEnabled(False)
        
        # 获取模型目录
        model_dir = None
        if self.model_path_label.text() != "使用默认模型":
            model_dir = self.model_path_label.text()
        
        # 创建并启动工作线程
        self.worker = FunASRWorker(
            audio_file, 
            model_dir,
            self.proxy_checkbox.isChecked()
        )
        self.worker.progress_updated.connect(self.update_progress)
        self.worker.result_updated.connect(self.update_result)
        self.worker.finished_signal.connect(self.on_transcription_finished)
        self.worker.start()
    
    def stop_transcription(self):
        """停止语音识别"""
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.terminate()
            self.worker.wait()
        
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_label.setText("处理已停止")
        self.progress_bar.setValue(0)
    
    def update_progress(self, value, message):
        """更新进度"""
        self.progress_bar.setValue(value)
        self.status_label.setText(message)
    
    def update_result(self, text):
        """更新识别结果"""
        if self.realtime_checkbox.isChecked():
            self.text_edit.setText(text)
    
    def on_transcription_finished(self, success, message):
        """识别完成处理"""
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.export_btn.setEnabled(success)
        
        if success:
            self.status_label.setText("识别完成")
            QMessageBox.information(self, "完成", "音频识别完成")
        else:
            self.status_label.setText(f"识别失败: {message}")
            QMessageBox.critical(self, "错误", f"识别失败: {message}")
    
    def export_result(self):
        """导出识别结果"""
        if not self.text_edit.toPlainText().strip():
            QMessageBox.warning(self, "警告", "没有可导出的内容")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出结果", "识别结果.txt", "文本文件 (*.txt);;所有文件 (*.*)")
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.text_edit.toPlainText())
                QMessageBox.information(self, "成功", f"结果已导出到: {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导出失败: {str(e)}")
    
    def clear_result(self):
        """清空结果"""
        self.text_edit.clear()
        self.progress_bar.setValue(0)
        self.status_label.setText("准备就绪")
        self.export_btn.setEnabled(False)
    
    def load_settings(self):
        """加载设置"""
        # 窗口几何
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        
        # 最后使用的音频目录
        last_audio_dir = self.settings.value("last_audio_dir")
        if last_audio_dir:
            self.file_path_label.setToolTip(f"上次目录: {last_audio_dir}")
        
        # 模型目录
        model_dir = self.settings.value("model_dir")
        if model_dir and os.path.exists(model_dir):
            self.model_path_label.setText(model_dir)
        
        # 代理设置
        use_proxy = self.settings.value("use_proxy", False, type=bool)
        self.proxy_checkbox.setChecked(use_proxy)
        
        # 实时显示设置
        realtime = self.settings.value("realtime_display", True, type=bool)
        self.realtime_checkbox.setChecked(realtime)
    
    def save_settings(self):
        """保存设置"""
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("use_proxy", self.proxy_checkbox.isChecked())
        self.settings.setValue("realtime_display", self.realtime_checkbox.isChecked())
        
        if self.model_path_label.text() != "使用默认模型":
            self.settings.setValue("model_dir", self.model_path_label.text())
    
    def closeEvent(self, event):
        """关闭事件处理"""
        self.save_settings()
        
        # 停止正在运行的线程
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.terminate()
            self.worker.wait(3000)  # 等待3秒
        
        event.accept()

def main():
    # 设置高DPI支持
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    app = QApplication(sys.argv)
    app.setApplicationName("FunASR Audio Transcriber")
    
    # 检查FunASR是否可用
    if not FUNASR_AVAILABLE:
        reply = QMessageBox.question(
            None, 
            "依赖检查", 
            "未安装FunASR库。是否要安装？\n\n安装命令: pip install funasr\n\n点击'是'将尝试自动安装，点击'否'将退出程序。",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                import subprocess
                subprocess.check_call([sys.executable, "-m", "pip", "install", "funasr"])
                QMessageBox.information(None, "成功", "FunASR安装成功！请重新启动程序。")
            except Exception as e:
                QMessageBox.critical(None, "错误", f"安装失败: {str(e)}")
            sys.exit(0)
        else:
            sys.exit(1)
    
    # 创建并显示窗口
    window = AudioTranscriber()
    window.show()
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()