import sys
import os
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QPushButton, QVBoxLayout, QWidget
from PyQt5.QtCore import Qt

def main():
    print("测试窗口显示...")
    
    # 创建应用程序实例
    app = QApplication(sys.argv)
    
    # 创建主窗口
    window = QMainWindow()
    window.setWindowTitle("测试窗口")
    window.setGeometry(300, 300, 400, 200)
    
    # 创建中央部件
    central_widget = QWidget()
    window.setCentralWidget(central_widget)
    
    # 创建布局
    layout = QVBoxLayout(central_widget)
    
    # 添加标签
    label = QLabel("如果看到这个窗口，说明PyQt5工作正常！")
    label.setAlignment(Qt.AlignCenter)
    layout.addWidget(label)
    
    # 添加按钮
    button = QPushButton("关闭程序")
    button.clicked.connect(window.close)
    layout.addWidget(button)
    
    # 显示窗口
    window.show()
    print("窗口已显示，请查看屏幕...")
    
    # 运行应用程序
    result = app.exec_()
    print(f"测试完成，返回值: {result}")
    return result

if __name__ == "__main__":
    sys.exit(main())