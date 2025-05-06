import sys
import os
import json
import tarfile
import shutil
import zipfile
import subprocess
import time
import tempfile
from PyQt5.QtWidgets import (QApplication, QWidget, QPushButton, QFileDialog,
                             QLabel, QLineEdit, QStackedWidget, QProgressBar, QCheckBox, QVBoxLayout, QMessageBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
import win32com.client


def get_install_path():
    # 修改为当前程序目录下的 apps 目录
    base_dir = os.path.join(os.path.dirname(__file__), 'apps')
    os.makedirs(base_dir, exist_ok=True)
    config_paths = [
        os.path.join(os.path.dirname(__file__), 'config.json'),
        os.path.join(base_dir, 'MyApp', 'config.json')
    ]       
    config = {'app_name': 'MyApp'}
    for path in config_paths:
        if os.path.exists(path):
            try:
                with open(path) as f:
                    config = json.load(f)
                break
            except Exception:
                continue
    app_name = config.get('app_name', 'MyApp')
    install_path = os.path.join(base_dir, app_name)
    os.makedirs(install_path, exist_ok=True)
    return install_path


def get_data_path():
    # 数据目录与安装目录分离
    install_path = get_install_path()
    return os.path.join(install_path, 'user_data')


class ExtractThread(QThread):
    progress_updated = pyqtSignal(int)
    finished = pyqtSignal()

    def __init__(self, tar_path, extract_path, overwrite=False):
        super().__init__()
        self.tar_path = tar_path
        self.extract_path = extract_path
        self.overwrite = overwrite

    def run(self):
        try:
            if self.overwrite and os.path.exists(self.extract_path):
                shutil.rmtree(self.extract_path)
                os.makedirs(self.extract_path, exist_ok=True)
            with tarfile.open(self.tar_path, 'r') as tar:
                members = tar.getmembers()
                total = len(members)
                tar.extractall(path=self.extract_path, members=members, filter=None)  # 兼容3.14+
                for i in range(total):
                    self.progress_updated.emit(int((i + 1) / total * 100))
            self.finished.emit()
        except Exception as e:
            print(str(e))


class InstallerWizard(QWidget):
    def __init__(self, repair_mode=False):
        super().__init__()
        self.stacked = QStackedWidget()
        self.tar_path = ''
        self.extract_path = ''
        self.exe_path = ''
        self.final_options = {
            'create_shortcut': False,
            'run_app': False
        }
        self.repair_mode = repair_mode
        self.temp_dir = os.path.join(tempfile.gettempdir(), 'app_install_temp')
        os.makedirs(self.temp_dir, exist_ok=True)

        # 初始化页面
        if self.repair_mode:
            self.create_repair_pages()
        else:
            self.create_install_pages()

        layout = QVBoxLayout()
        layout.addWidget(self.stacked)
        self.setLayout(layout)
        self.setWindowTitle('安装向导')
        self.resize(500, 400)

    def create_install_pages(self):
        self.install_page = InstallPage(self)
        self.page3 = self.create_page3()
        self.page4 = self.create_page4()

        self.stacked.addWidget(self.install_page)
        self.stacked.addWidget(self.page3)
        self.stacked.addWidget(self.page4)

    def create_repair_pages(self):
        self.repair_page = RepairPage(self)
        self.page3 = self.create_page3()
        self.page4 = self.create_page4()

        self.stacked.addWidget(self.repair_page)
        self.stacked.addWidget(self.page3)
        self.stacked.addWidget(self.page4)

    def create_page3(self):
        page = QWidget()
        layout = QVBoxLayout()

        self.progress_bar = QProgressBar()
        self.progress_bar.setAlignment(Qt.AlignCenter)
        self.btn_next3 = QPushButton('下一步')
        self.btn_next3.clicked.connect(lambda: self.stacked.setCurrentIndex(2))
        self.btn_next3.setEnabled(False)

        layout.addWidget(self.progress_bar)
        layout.addWidget(self.btn_next3)
        page.setLayout(layout)
        return page

    def create_page4(self):
        page = QWidget()
        layout = QVBoxLayout()

        self.cb_create_shortcut = QCheckBox('创建桌面快捷方式')
        self.cb_create_shortcut.stateChanged.connect(self.on_checkbox_changed)
        self.cb_run_app = QCheckBox('运行此软件')
        self.cb_run_app.stateChanged.connect(self.on_checkbox_changed)
        self.btn_finish = QPushButton('完成')
        self.btn_finish.clicked.connect(self.on_finish_clicked)

        layout.addWidget(self.cb_create_shortcut)
        layout.addWidget(self.cb_run_app)
        layout.addWidget(self.btn_finish)
        page.setLayout(layout)
        return page

    def on_next2_clicked(self):
        extract_path = self.temp_dir if self.repair_mode else self.extract_path
        self.extract_thread = ExtractThread(self.tar_path, extract_path, self.repair_mode)
        self.extract_thread.progress_updated.connect(self.update_progress)
        self.extract_thread.finished.connect(self.on_extract_finished)
        self.extract_thread.start()
        self.stacked.setCurrentIndex(1)

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def on_extract_finished(self):
        # 自动切换到最后一页
        self.btn_next3.setEnabled(True)
        self.stacked.setCurrentIndex(2)

    def on_checkbox_changed(self):
        self.final_options['create_shortcut'] = self.cb_create_shortcut.isChecked()
        self.final_options['run_app'] = self.cb_run_app.isChecked()

    def on_finish_clicked(self):
        backup_dir = os.path.join(self.extract_path, 'backup')
        try:
            os.makedirs(backup_dir, exist_ok=True)
        except Exception as e:
            QMessageBox.critical(self, '错误', f'创建备份目录失败: {e}')
            return
        if not os.path.isdir(backup_dir):
            raise FileNotFoundError(f'备份目录不存在: {backup_dir}')
        if not os.path.exists(self.tar_path):
            raise FileNotFoundError(f'安装包文件不存在: {self.tar_path}')
        # 复制安装包
        shutil.copy2(self.tar_path, os.path.join(backup_dir, os.path.basename(self.tar_path)))
        # 直接从安装包提取配置文件到根目录
        with tarfile.open(self.tar_path, 'r') as tar:
            try:
                config_member = None
                for member in tar.getmembers():
                    if member.name == 'config.json':
                        config_member = member
                        break
                if config_member is None:
                    QMessageBox.critical(self, '错误', '安装包缺少配置文件')
                    return
                tar.extractall(path=self.extract_path, members=[config_member], filter=None)  # 兼容3.14+
                config_path = os.path.join(self.extract_path, 'config.json')
                if not os.path.exists(config_path):
                    QMessageBox.critical(self, '错误', '配置文件提取失败')
                    return

                # 验证配置文件可读性
                try:
                    with open(config_path, encoding='utf-8') as f:
                        json.load(f)
                except Exception as e:
                    QMessageBox.critical(self, '配置错误', f'配置文件校验失败: {str(e)}')
                    return
            except KeyError:
                QMessageBox.critical(self, '错误', '安装包缺少配置文件')
                return
        # 复制修复程序到安装根目录
        repair_exe = os.path.join(os.path.dirname(__file__), '修复程序.exe')
        if os.path.exists(repair_exe):
            shutil.copy2(repair_exe, os.path.join(self.extract_path, '修复程序.exe'))
        # 复制修复_卸载.exe到安装根目录
        repair_uninstall_exe = os.path.join(os.path.dirname(__file__), '修复_卸载.exe')
        if os.path.exists(repair_uninstall_exe):
            shutil.copy2(repair_uninstall_exe, os.path.join(self.extract_path, '修复_卸载.exe'))
        # 迁移文件
        if self.repair_mode:
            for item in os.listdir(self.temp_dir):
                src = os.path.join(self.temp_dir, item)
                dst = os.path.join(get_install_path(), item)
                if os.path.exists(dst):
                    shutil.rmtree(dst) if os.path.isdir(dst) else os.remove(dst)
                shutil.move(src, dst)
        if self.final_options['create_shortcut']:
            self.create_shortcut()
        if self.final_options['run_app']:
            self.run_app()
        self.close()

    def create_shortcut(self):
        desktop = os.path.join(os.path.expanduser('~'), 'Desktop')
        print(f'桌面路径: {desktop}')
        print(f'桌面可写: {os.access(desktop, os.W_OK)}')
        if not os.access(desktop, os.W_OK):
            print('桌面路径不可写')
            return
        shortcut_name = f'程序快捷方式_{int(time.time())}.lnk'
        shortcut_path = os.path.join(desktop, shortcut_name)
        exe_abs = os.path.join(self.extract_path, self.exe_path)
        if not os.path.exists(os.path.dirname(exe_abs)):
            os.makedirs(os.path.dirname(exe_abs), exist_ok=True)
        if not os.path.exists(exe_abs):
            print(f'路径验证失败: {exe_abs}')
            return
        exe_abs = os.path.normpath(exe_abs)
        print(f'规范化后的EXE路径: {exe_abs}')
        print(f'快捷方式目标路径: {exe_abs}')
        print(f'路径存在: {os.path.exists(exe_abs)}')
        try:
            if os.path.exists(shortcut_path):
                os.remove(shortcut_path)
            shell = win32com.client.Dispatch("WScript.Shell")
            shortcut = shell.CreateShortcut(shortcut_path)
            shortcut.TargetPath = exe_abs
            shortcut.save()
        except PermissionError as e:
            print(f'权限错误: {e}')
        except FileNotFoundError as e:
            print(f'文件未找到: {e}')
        except Exception as e:
            print(f'快捷方式创建失败: {e}')

    def run_app(self):
        # 运行程序的逻辑
        exe_abs = os.path.join(self.extract_path, self.exe_path)
        if not os.path.exists(os.path.dirname(exe_abs)):
            os.makedirs(os.path.dirname(exe_abs), exist_ok=True)
        print(f'最终执行路径: {exe_abs}')
        if not os.path.exists(exe_abs):
            print(f'最终验证路径不存在: {exe_abs}')
            return
        print(f'完整路径: {exe_abs}')
        print(f'路径存在: {os.path.exists(exe_abs)}')
        if os.path.exists(exe_abs):
            try:
                subprocess.Popen([exe_abs], shell=True)
                print(f'启动程序: {exe_abs}')
            except Exception as e:
                print(f'程序启动失败: {e}')
        else:
            print(f'可执行文件不存在: {exe_abs}')


class InstallPage(QWidget):
    def __init__(self, wizard):
        super().__init__()
        self.wizard = wizard
        layout = QVBoxLayout()

        self.tar_label = QLabel('请选择安装包文件(.tar)')
        self.btn_choose_tar = QPushButton('选择包')
        self.btn_choose_tar.clicked.connect(self.choose_tar)
        self.btn_next1 = QPushButton('下一步')
        self.btn_next1.clicked.connect(lambda: self.wizard.stacked.setCurrentIndex(1))
        self.btn_next1.setEnabled(False)
        
        self.path_label = QLabel('请选择安装路径')
        self.path_input = QLineEdit()
        self.path_input.setReadOnly(False)
        self.path_input.setAlignment(Qt.AlignCenter)
        self.path_input.setPlaceholderText('请选择安装路径')
        self.path_input.textChanged.connect(self.validate_path)
        self.btn_browse = QPushButton('浏览')
        self.btn_browse.clicked.connect(self.choose_path)
        self.btn_next2 = QPushButton('下一步')
        self.btn_next2.clicked.connect(self.wizard.on_next2_clicked)
        self.btn_next2.setEnabled(False)

        layout.addWidget(self.tar_label)
        layout.addWidget(self.btn_choose_tar)
        layout.addWidget(self.path_label)
        layout.addWidget(self.path_input)
        layout.addWidget(self.btn_browse)
        layout.addWidget(self.btn_next2)
        self.setLayout(layout)

    def choose_tar(self):
        path, _ = QFileDialog.getOpenFileName(self, '选择安装包', '', 'ANTIK安装包 (*.ANTIKINST);;Tar Files (*.tar)')
        if path:
            self.wizard.tar_path = path
            self.btn_next1.setEnabled(True)
            self.tar_label.setText(f'已选择安装包: {os.path.basename(path)}')
            self.load_json_config()
    
    def choose_path(self):
        path = QFileDialog.getExistingDirectory(self, '选择安装路径')
        if path:
            self.path_input.setText(path)
            self.wizard.extract_path = path  # 确保extract_path同步

    def load_json_config(self):
        try:
            with tarfile.open(self.wizard.tar_path, 'r') as tar:
                for member in tar.getmembers():
                    if member.name.endswith('config.json'):
                        with tar.extractfile(member) as f:
                            config = json.loads(f.read().decode('utf-8'))
                            default_path = config.get('默认解压路径', '')
                            self.wizard.exe_path = config.get('主程序目录', '')
                            if not self.wizard.exe_path:
                                raise ValueError('配置文件中缺少主程序目录配置')
                            print(f'从配置加载的原始exe路径: {self.wizard.exe_path}')
                            if default_path:
                                self.path_input.setText(default_path)
                                self.wizard.extract_path = default_path  # 同步extract_path
                                self.validate_path()
                            break
        except Exception as e:
            print(str(e))
            QMessageBox.critical(self, '配置错误', f'加载配置文件失败: {str(e)}')
        print(f'完整解包路径验证: {os.path.exists(os.path.join(self.wizard.extract_path, "app"))}')

    def validate_path(self):
        current_path = os.path.normpath(self.path_input.text())
        print(f'路径验证: {current_path} 存在状态: {os.path.exists(current_path)}')
        try:
            os.makedirs(current_path, exist_ok=True)
            self.wizard.extract_path = current_path  # 确保extract_path同步
            valid = True
        except Exception as e:
            print(f'创建目录失败: {e}')
            valid = False
        self.btn_next2.setEnabled(valid)


class RepairPage(QWidget):
    def __init__(self, wizard):
        super().__init__()
        self.wizard = wizard
        layout = QVBoxLayout()

        self.tar_label = QLabel('检测到修复模式，将使用backup目录下的安装包')
        backup_dir = os.path.join(os.path.dirname(os.path.abspath(sys.executable)), 'backup')
        print(f'备份目录路径: {backup_dir}')
        print(f'备份目录存在: {os.path.exists(backup_dir)}')
        try:
            os.makedirs(backup_dir, exist_ok=True)
            print(f'备份目录创建/访问成功')
            # 支持.ANTIKINST和.tar
            tar_files = [f for f in os.listdir(backup_dir) if f.endswith('.ANTIKINST') or f.endswith('.tar')]
            print(f'找到的tar文件列表: {tar_files}')
            if tar_files:
                self.wizard.tar_path = os.path.join(backup_dir, tar_files[0])
                print(f'选择的tar文件路径: {self.wizard.tar_path}')
                print(f'tar文件存在: {os.path.exists(self.wizard.tar_path)}')
                self.btn_next1 = QPushButton('下一步')
                self.btn_next1.clicked.connect(lambda: self.wizard.stacked.setCurrentIndex(1))
                self.btn_next1.setEnabled(True)
                # 初始化path_input控件
                self.path_input = QLineEdit()
                self.path_input.setReadOnly(False)
                self.path_input.setAlignment(Qt.AlignCenter)
                self.path_input.setPlaceholderText('请选择安装路径')
                self.path_input.textChanged.connect(self.validate_path)
                # 初始化btn_next2按钮
                self.btn_next2 = QPushButton('下一步')
                self.btn_next2.clicked.connect(self.wizard.on_next2_clicked)
                self.btn_next2.setEnabled(False)
                self.load_json_config()
            else:
                print('未找到任何.tar文件')
                QMessageBox.critical(self, '错误', '未找到backup目录下的tar文件')
                self.close()
        except Exception as e:
            print(f'访问备份目录时出错: {str(e)}')
            QMessageBox.critical(self, '错误', f'无法访问backup目录: {str(e)}')
            try:
                self.close()
            except Exception as e:
                sys.exit(1)
        
        layout.addWidget(self.tar_label)
        layout.addWidget(self.path_input)
        layout.addWidget(self.btn_next1)
        self.setLayout(layout)

    def load_json_config(self):
        try:
            with tarfile.open(self.wizard.tar_path, 'r') as tar:
                for member in tar.getmembers():
                    if member.name.endswith('config.json'):
                        with tar.extractfile(member) as f:
                            config = json.loads(f.read().decode('utf-8'))
                            self.wizard.exe_path = config.get('主程序目录', '')
                            if not self.wizard.exe_path:
                                raise ValueError('配置文件中缺少主程序目录配置')
                            print(f'从配置加载的原始exe路径: {self.wizard.exe_path}')
                            exe_dir = os.path.dirname(os.path.abspath(sys.executable))
                            print(f'修复模式安装路径: {exe_dir}')
                            self.path_input.setText(exe_dir)
                            self.wizard.extract_path = exe_dir  # 确保extract_path同步
                            self.path_input.textChanged.emit(exe_dir)
                            os.makedirs(exe_dir, exist_ok=True)
                            self.validate_path()
                            self.wizard.stacked.setCurrentIndex(2)
                            QApplication.processEvents()
                            self.btn_next2.clicked.emit()
                            break
        except Exception as e:
            print(str(e))
            QMessageBox.critical(self, '配置错误', f'加载配置文件失败: {str(e)}')
        print(f'完整解包路径验证: {os.path.exists(os.path.join(self.wizard.extract_path, "app"))}')

    def validate_path(self):
        current_path = os.path.normpath(self.path_input.text())
        print(f'路径验证: {current_path} 存在状态: {os.path.exists(current_path)}')
        try:
            os.makedirs(current_path, exist_ok=True)
            self.wizard.extract_path = current_path  # 确保extract_path同步
            valid = True
        except Exception as e:
            print(f'创建目录失败: {e}')
            valid = False
        self.btn_next2.setEnabled(valid)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    wizard = InstallerWizard()
    wizard.show()
    sys.exit(app.exec_())