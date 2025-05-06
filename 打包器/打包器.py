import sys
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout, QFileDialog, QLabel, QLineEdit
from PyQt5.QtGui import QRegExpValidator
from PyQt5.QtCore import QRegExp
import tarfile, os, json
from PyInstaller.__main__ import run


class Installer(QWidget):
    def __init__(self):
        super().__init__()
        self.selected_folder = ''
        self.default_extract_path = ''
        self.exe_path = ''
        self.app_name = ''

        layout = QVBoxLayout()

        label_choose_folder = QLabel('选择要被打包的文件夹')
        self.folder_input = QLineEdit()
        self.folder_input.setPlaceholderText('请输入或选择要打包的文件夹路径')
        btn_choose = QPushButton('选择文件夹')
        btn_choose.clicked.connect(self.choose_folder)

        label_exe_path = QLabel('主程序目录')
        self.exe_input = QLineEdit()
        self.exe_input.setPlaceholderText('请输入或选择主程序exe路径')
        btn_exe = QPushButton('选择EXE')
        btn_exe.clicked.connect(self.choose_exe)

        label_extract_path = QLabel('默认解压路径')
        self.lineedit_extract_path = QLineEdit()
        self.lineedit_extract_path.setValidator(QRegExpValidator(QRegExp(r'[^"]*')))
        btn_extract_path = QPushButton('选择路径')
        btn_extract_path.clicked.connect(self.choose_extract_path)

        label_app_name = QLabel('应用名称')
        self.app_name_input = QLineEdit()
        btn_pack = QPushButton('打包')
        btn_pack.clicked.connect(self.pack_to_tar)
        self.status_label = QLabel()

        layout.addWidget(label_choose_folder)
        layout.addWidget(self.folder_input)
        layout.addWidget(btn_choose)
        layout.addWidget(label_exe_path)
        layout.addWidget(self.exe_input)
        layout.addWidget(btn_exe)
        layout.addWidget(label_extract_path)
        layout.addWidget(self.lineedit_extract_path)
        layout.addWidget(btn_extract_path)
        layout.addWidget(label_app_name)    
        layout.addWidget(self.app_name_input)
        layout.addWidget(btn_pack)
        layout.addWidget(self.status_label)

        self.setLayout(layout)
        self.setWindowTitle('打包程序')
        self.resize(900, 600)
        screen_geometry = app.primaryScreen().availableGeometry()
        self.move(
            (screen_geometry.width() - self.width()) // 2,
            (screen_geometry.height() - self.height()) // 2
        )

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(None, '选择文件夹')
        if folder:
            self.selected_folder = folder
            self.folder_input.setText(folder)
            self.status_label.setText(f'已选择: {os.path.basename(folder)}')

    def choose_exe(self):
        file_name, _ = QFileDialog.getOpenFileName(None, '选择主程序', '', 'EXE文件 (*.exe)')
        if file_name:
            self.exe_input.setText(file_name)
            self.exe_path = file_name

    def choose_extract_path(self):
        path = QFileDialog.getExistingDirectory(None, '选择默认解压路径')
        if path:
            self.lineedit_extract_path.setText(os.path.normpath(path))
            self.default_extract_path = os.path.normpath(path)

    def pack_to_tar(self):
        self.selected_folder = self.folder_input.text().strip()
        if not self.selected_folder or not os.path.isdir(self.selected_folder):
            self.status_label.setText('请先选择或输入有效的文件夹!')
            return

        self.exe_path = self.exe_input.text().strip()
        if not self.exe_path or not os.path.isfile(self.exe_path):
            self.status_label.setText('请选择或输入有效的主程序exe路径!')
            return

        # 判断主程序是否在被打包文件夹内部
        exe_abs = os.path.abspath(self.exe_path)
        folder_abs = os.path.abspath(self.selected_folder)
        if not exe_abs.startswith(folder_abs):
            self.status_label.setText('主程序必须在被打包的文件夹路径内部!')
            return

        self.default_extract_path = self.lineedit_extract_path.text().strip('"')
        self.default_extract_path = os.path.normpath(self.default_extract_path)
        if not self.default_extract_path:
            self.status_label.setText('请输入默认解压路径!')
            return

        self.app_name = self.app_name_input.text()
        if not self.app_name:
            self.status_label.setText('请输入应用名称!')
            return

        save_path, _ = QFileDialog.getSaveFileName(None, '保存ANTIK安装包', '', 'ANTIK安装包 (*.ANTIKINST)')
        if save_path:
            # 修正：只在没有任何后缀时才加 .ANTIKINST
            base, ext = os.path.splitext(save_path)
            if not ext:
                save_path += '.ANTIKINST'
            elif ext.lower() != '.antkinst':
                save_path = base + '.ANTIKINST'
            try:
                with tarfile.open(save_path, 'w') as tar:
                    for root, dirs, files in os.walk(self.selected_folder):
                        if 'backup' in dirs:
                            dirs.remove('backup')
                        for file in files:
                            full_path = os.path.join(root, file)
                            arcname = os.path.join('app', os.path.relpath(full_path, self.selected_folder))
                            tar.add(full_path, arcname=arcname)

                    rel_exe_path = os.path.join('app', os.path.relpath(self.exe_path, self.selected_folder))
                    print(f'生成的exe_path: {rel_exe_path}')
                    config = {'默认解压路径': os.path.normpath(self.default_extract_path), '主程序目录': rel_exe_path, 'app_name': self.app_name}
                    with open('config.json', 'w', encoding='utf-8') as f:
                        json.dump(config, f, ensure_ascii=False)
                    tar.add('config.json', arcname='config.json')
                    os.remove('config.json')

                    # 自动提取主程序exe的图标并打包到icon/icon.ico
                    try:
                        import tempfile
                        import shutil
                        from PyQt5.QtWinExtras import QtWin
                        import ctypes

                        ico_temp = os.path.join(tempfile.gettempdir(), "main_icon.ico")
                        hicon = ctypes.windll.shell32.ExtractIconW(0, self.exe_path, 0)
                        if hicon:
                            pixmap = QtWin.fromHICON(hicon)
                            pixmap.save(ico_temp, "ICO")
                            ctypes.windll.user32.DestroyIcon(hicon)
                            tar.add(ico_temp, arcname='icon/icon.ico')
                            os.remove(ico_temp)
                    except Exception as e:
                        print(f"提取exe图标失败: {e}")

                    # 继续打包icon文件夹（如有）
                    icon_dir = os.path.join(self.selected_folder, "icon")
                    icon_found = False
                    for root, dirs, files in os.walk(self.selected_folder):
                        for file in files:
                            if root.endswith("icon"):
                                full_icon_path = os.path.join(root, file)
                                arcname = os.path.join('icon', file)
                                tar.add(full_icon_path, arcname=arcname)
                                icon_found = True
                    # 如果没有icon文件夹，尝试打包icon.ANTIK
                    if not icon_found:
                        antik_icon = os.path.join(self.selected_folder, "icon.ANTIK")
                        if os.path.isfile(antik_icon):
                            tar.add(antik_icon, arcname='icon/icon.ANTIK')

                self.status_label.setText(f'打包完成: {os.path.basename(save_path)}')
            except Exception as e:
                self.status_label.setText(f'错误: {str(e)}')


app = QApplication(sys.argv)
window = Installer()
window.show()
sys.exit(app.exec_())
