import sys
import os
import shutil
import json
import tarfile
import tempfile
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QPushButton, QLabel, QMessageBox, QStyle, QSizePolicy
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt


def find_all_installed_apps():
    base_dir = os.path.join(os.path.dirname(__file__), 'apps')
    apps = []
    if not os.path.exists(base_dir):
        return apps
    for name in os.listdir(base_dir):
        app_dir = os.path.join(base_dir, name)
        config_path = os.path.join(app_dir, 'config.json')
        if os.path.isdir(app_dir) and os.path.exists(config_path):
            try:
                with open(config_path, encoding='utf-8') as f:
                    config = json.load(f)
                apps.append({'name': config.get('app_name', name), 'path': app_dir})
            except Exception:
                continue
    return apps


def copy_self_and_tar_to_temp():
    temp_dir = os.path.join(tempfile.gettempdir(), "app_repair_temp")
    os.makedirs(temp_dir, exist_ok=True)
    exe_path = sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(__file__)
    exe_dst = os.path.join(temp_dir, os.path.basename(exe_path))
    if exe_path != exe_dst:
        shutil.copy2(exe_path, exe_dst)
    # 直接查找当前目录下的backup文件夹
    backup_dir = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "backup")
    print(f"[DEBUG] 查找包目录: {backup_dir}")
    tar_path = None
    if os.path.exists(backup_dir):
        print(f"[DEBUG] backup目录内容: {os.listdir(backup_dir)}")
        for f in os.listdir(backup_dir):
            print(f"[DEBUG] 检查文件: {f}")
            if f.lower().endswith(".antikinst"):
                tar_path = os.path.join(backup_dir, f)
                print(f"[DEBUG] 找到包: {tar_path}")
                break
    else:
        print(f"[DEBUG] backup目录不存在: {backup_dir}")
    tar_dst = None
    if tar_path:
        tar_dst = os.path.join(temp_dir, os.path.basename(tar_path))
        if tar_path != tar_dst:
            shutil.copy2(tar_path, tar_dst)
    else:
        print("[DEBUG] 未找到.ANTIKINST包")
    return temp_dir, exe_dst, tar_dst


def extract_tar_to_dir(tar_path, target_dir, overwrite=False):
    if overwrite and os.path.exists(target_dir):
        shutil.rmtree(target_dir)
        os.makedirs(target_dir, exist_ok=True)
    with tarfile.open(tar_path, 'r') as tar:
        tar.extractall(path=target_dir, filter=None)


class RepairUninstallWidget(QWidget):
    def __init__(self):
        super().__init__()

        self.setFixedSize(900, 600)
        self.setWindowTitle('修复/卸载')
        main_layout = QHBoxLayout()

        # 右侧面板
        right_container = QWidget()
        right_layout = QVBoxLayout()

        # 预留顶部空位，放图标和应用名（横排）
        # 用单独的图层（QWidget）放图标，避免主布局受影响
        top_widget = QWidget()
        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)
        # 图标
        self.icon_label = QLabel()
        self.icon_label.setMinimumSize(1, 1)
        icon_dir = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "icon")
        icon_loaded = False
        ICON_SIZE = 160  # 限制显示区域为160x160
        icon_pixmap = None
        if os.path.isdir(icon_dir):
            icon_files = [f for f in os.listdir(icon_dir) if os.path.isfile(os.path.join(icon_dir, f))]
            if icon_files:
                icon_path = os.path.join(icon_dir, icon_files[0])
                try:
                    pixmap = QPixmap(icon_path)
                    if not pixmap.isNull():
                        # 如果图片比ICON_SIZE小，放大后居中裁剪
                        if pixmap.width() < ICON_SIZE or pixmap.height() < ICON_SIZE:
                            scale = max(ICON_SIZE / pixmap.width(), ICON_SIZE / pixmap.height())
                            new_width = int(pixmap.width() * scale)
                            new_height = int(pixmap.height() * scale)
                            pixmap = pixmap.scaled(new_width, new_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                            x = max(0, (pixmap.width() - ICON_SIZE) // 2)
                            y = max(0, (pixmap.height() - ICON_SIZE) // 2)
                            cropped = pixmap.copy(x, y, ICON_SIZE, ICON_SIZE)
                            icon_pixmap = cropped
                        # 如果图片比ICON_SIZE大，缩小后铺满显示区域
                        elif pixmap.width() > ICON_SIZE or pixmap.height() > ICON_SIZE:
                            pixmap = pixmap.scaled(ICON_SIZE, ICON_SIZE, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                            x = max(0, (pixmap.width() - ICON_SIZE) // 2)
                            y = max(0, (pixmap.height() - ICON_SIZE) // 2)
                            cropped = pixmap.copy(x, y, ICON_SIZE, ICON_SIZE)
                            icon_pixmap = cropped
                        else:
                            # 正好等于ICON_SIZE
                            icon_pixmap = pixmap
                except Exception:
                    pass
        # 如果icon文件夹没有可用图片，则尝试从backup目录下的tar包里读取icon
        if icon_pixmap is None:
            import tarfile
            backup_dir = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "backup")
            tar_files = [f for f in os.listdir(backup_dir)] if os.path.exists(backup_dir) else []
            tar_path = None
            for f in tar_files:
                if f.endswith(".ANTIKINST") or f.endswith(".tar"):
                    tar_path = os.path.join(backup_dir, f)
                    break
            if tar_path:
                try:
                    with tarfile.open(tar_path, "r") as tar:
                        icon_member = None
                        for member in tar.getmembers():
                            # 只取第一个icon目录下的文件
                            if member.name.startswith("icon/") and member.isfile():
                                icon_member = member
                                break
                        if icon_member:
                            icon_file = tar.extractfile(icon_member)
                            if icon_file:
                                from PyQt5.QtCore import QByteArray
                                data = icon_file.read()
                                ba = QByteArray(data)
                                pixmap = QPixmap()
                                pixmap.loadFromData(ba)
                                if not pixmap.isNull():
                                    # 同样处理缩放和裁剪
                                    if pixmap.width() < ICON_SIZE or pixmap.height() < ICON_SIZE:
                                        scale = max(ICON_SIZE / pixmap.width(), ICON_SIZE / pixmap.height())
                                        new_width = int(pixmap.width() * scale)
                                        new_height = int(pixmap.height() * scale)
                                        pixmap = pixmap.scaled(new_width, new_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                                        x = max(0, (pixmap.width() - ICON_SIZE) // 2)
                                        y = max(0, (pixmap.height() - ICON_SIZE) // 2)
                                        cropped = pixmap.copy(x, y, ICON_SIZE, ICON_SIZE)
                                        icon_pixmap = cropped
                                    elif pixmap.width() > ICON_SIZE or pixmap.height() > ICON_SIZE:
                                        pixmap = pixmap.scaled(ICON_SIZE, ICON_SIZE, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                                        x = max(0, (pixmap.width() - ICON_SIZE) // 2)
                                        y = max(0, (pixmap.height() - ICON_SIZE) // 2)
                                        cropped = pixmap.copy(x, y, ICON_SIZE, ICON_SIZE)
                                        icon_pixmap = cropped
                                    else:
                                        icon_pixmap = pixmap
                except Exception:
                    pass
        # 如果tar包也没有，再尝试读取当前目录下的icon.ANTIK文件
        if icon_pixmap is None:
            antik_icon_path = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "icon.ANTIK")
            if os.path.isfile(antik_icon_path):
                try:
                    pixmap = QPixmap(antik_icon_path)
                    if not pixmap.isNull():
                        # 同样处理缩放和裁剪
                        if pixmap.width() < ICON_SIZE or pixmap.height() < ICON_SIZE:
                            scale = max(ICON_SIZE / pixmap.width(), ICON_SIZE / pixmap.height())
                            new_width = int(pixmap.width() * scale)
                            new_height = int(pixmap.height() * scale)
                            pixmap = pixmap.scaled(new_width, new_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                            x = max(0, (pixmap.width() - ICON_SIZE) // 2)
                            y = max(0, (pixmap.height() - ICON_SIZE) // 2)
                            cropped = pixmap.copy(x, y, ICON_SIZE, ICON_SIZE)
                            icon_pixmap = cropped
                        elif pixmap.width() > ICON_SIZE or pixmap.height() > ICON_SIZE:
                            pixmap = pixmap.scaled(ICON_SIZE, ICON_SIZE, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                            x = max(0, (pixmap.width() - ICON_SIZE) // 2)
                            y = max(0, (pixmap.height() - ICON_SIZE) // 2)
                            cropped = pixmap.copy(x, y, ICON_SIZE, ICON_SIZE)
                            icon_pixmap = cropped
                        else:
                            icon_pixmap = pixmap
                except Exception:
                    pass
        if icon_pixmap is not None:
            self.icon_label.setPixmap(icon_pixmap)
        else:
            self.icon_label.clear()
        self.icon_label.setFixedSize(ICON_SIZE, ICON_SIZE)
        self.icon_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        # 图标单独放在一个widget里，防止主布局拉伸
        icon_widget = QWidget()
        icon_widget.setFixedSize(ICON_SIZE, ICON_SIZE)
        icon_layout = QVBoxLayout()
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_layout.addWidget(self.icon_label, alignment=Qt.AlignLeft | Qt.AlignTop)
        icon_widget.setLayout(icon_layout)

        self.app_name_label = QLabel()
        self.app_name_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        font = self.app_name_label.font()
        font.setPointSize(16)
        font.setBold(True)
        self.app_name_label.setFont(font)

        top_layout.addWidget(icon_widget)
        top_layout.addSpacing(16)
        top_layout.addWidget(self.app_name_label)
        top_layout.addStretch()
        top_widget.setLayout(top_layout)
        # 彻底防止抽搐：为top_widget设置固定高度和最小高度，并且right_layout顶部不再加Spacing
        top_widget.setFixedHeight(ICON_SIZE + 0)  
        right_layout.addWidget(top_widget)

        # 修复+重置合并为一个分组
        repair_reset_group = QGroupBox('修复/重置')
        repair_reset_layout = QVBoxLayout()
        repair_reset_layout.setContentsMargins(8, 8, 8, 8)
        repair_reset_layout.setSpacing(12)
        repair_tip_label = QLabel('如果此应用无法正常运行，我们可以尝试进行修复。这不会影响应用的数据。')
        repair_tip_label.setWordWrap(True)
        repair_reset_layout.addWidget(repair_tip_label)
        reset_button = QPushButton('修复')
        reset_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        reset_button.clicked.connect(self.repair)
        repair_reset_layout.addWidget(reset_button)
        reset_data_label = QLabel('如果此应用仍无法正常运行，请重置。这会删除此应用的数据。')
        reset_data_label.setWordWrap(True)
        repair_reset_layout.addWidget(reset_data_label)
        reset_data_button = QPushButton('重置')
        reset_data_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        reset_data_button.clicked.connect(self.reset_data)
        repair_reset_layout.addWidget(reset_data_button)
        repair_reset_group.setLayout(repair_reset_layout)
        repair_reset_group.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)

        # 卸载组（适当缩小，紧贴底部）
        uninstall_group = QGroupBox('卸载')
        uninstall_layout = QVBoxLayout()
        uninstall_label = QLabel('卸载此应用及其设置。')
        uninstall_button = QPushButton('卸载')
        uninstall_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        uninstall_button.clicked.connect(self.uninstall)
        uninstall_layout.addWidget(uninstall_label)
        uninstall_layout.addWidget(uninstall_button)
        uninstall_group.setLayout(uninstall_layout)
        uninstall_group.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)

        # 让修复/重置组贴近卸载组，且两者都靠底部
        right_layout.addStretch()
        right_layout.addWidget(repair_reset_group)
        right_layout.addWidget(uninstall_group)

        right_container.setMinimumWidth(400)
        right_container.setLayout(right_layout)
        main_layout.addWidget(right_container)
        self.setLayout(main_layout)

        self.temp_dir = None
        self.temp_exe = None
        self.temp_tar = None
        self.prepare_temp_files()
        self.load_app_info()

    def prepare_temp_files(self):
        self.temp_dir, self.temp_exe, self.temp_tar = copy_self_and_tar_to_temp()

    def load_app_info(self):
        # 直接从backup目录下的ANTIKINST包读取config.json
        config = {}
        if self.temp_tar and os.path.isfile(self.temp_tar):
            try:
                with tarfile.open(self.temp_tar, 'r') as tar:
                    for member in tar.getmembers():
                        if member.name.endswith('config.json'):
                            with tar.extractfile(member) as f:
                                config = json.load(f)
                            break
            except Exception as e:
                print(f"[DEBUG] 读取config.json失败: {e}")
        app_name = config.get('app_name', '我的应用')
        self.app_name_label.setText(app_name)

    def repair(self):
        self.prepare_temp_files()
        if not self.temp_tar or not os.path.isfile(self.temp_tar):
            QMessageBox.critical(self, '错误', '未找到安装包（ANTIKINST）')
            return
        try:
            print(f"准备解包: {self.temp_tar} 到 {os.path.dirname(os.path.abspath(sys.argv[0]))}")
            extract_tar_to_dir(self.temp_tar, os.path.dirname(os.path.abspath(sys.argv[0])), overwrite=False)
            exe_name = os.path.basename(self.temp_exe)
            print(f"复制自身: {self.temp_exe} -> {os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), exe_name)}")
            shutil.copy2(self.temp_exe, os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), exe_name))
            QMessageBox.information(self, '信息', '修复完成')
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            QMessageBox.critical(self, '错误', f'修复失败: {e}\n{traceback.format_exc()}')

    def reset_data(self):
        self.prepare_temp_files()
        if not self.temp_tar or not os.path.isfile(self.temp_tar):
            QMessageBox.critical(self, '错误', '未找到安装包（ANTIKINST）')
            return
        try:
            target_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
            print(f"准备重置，删除: {target_dir}")
            for name in os.listdir(target_dir):
                path = os.path.join(target_dir, name)
                try:
                    if os.path.isdir(path):
                        shutil.rmtree(path)
                    else:
                        os.remove(path)
                except Exception as e:
                    print(f"[DEBUG] 删除失败: {path} {e}")
            os.makedirs(target_dir, exist_ok=True)
            print(f"解包: {self.temp_tar} 到 {target_dir}")
            extract_tar_to_dir(self.temp_tar, target_dir, overwrite=False)
            exe_name = os.path.basename(self.temp_exe)
            print(f"复制自身: {self.temp_exe} -> {os.path.join(target_dir, exe_name)}")
            shutil.copy2(self.temp_exe, os.path.join(target_dir, exe_name))
            QMessageBox.information(self, '信息', '重置完成')
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            QMessageBox.critical(self, '错误', f'重置失败: {e}\n{traceback.format_exc()}')

    def uninstall(self):
        reply = QMessageBox.question(self, '确认卸载', '确定要卸载并删除当前应用及其所有文件吗？', QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        app_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        if os.path.exists(app_dir):
            try:
                shutil.rmtree(app_dir)
                QMessageBox.information(self, '信息', '应用已卸载')
                self.close()
            except Exception as e:
                # 尝试逐个删除
                try:
                    for root, dirs, files in os.walk(app_dir, topdown=False):
                        for name in files:
                            try:
                                os.remove(os.path.join(root, name))
                            except Exception:
                                pass
                        for name in dirs:
                            try:
                                shutil.rmtree(os.path.join(root, name))
                            except Exception:
                                pass
                    try:
                        os.rmdir(app_dir)
                    except Exception:
                        pass
                    QMessageBox.information(self, '信息', '应用已卸载（部分文件可能需手动删除）')
                    self.close()
                except Exception as e2:
                    QMessageBox.critical(self, '错误', f'卸载失败: {e}\n{e2}')
        else:
            QMessageBox.warning(self, '警告', '安装目录不存在')


if __name__ == '__main__':
    app = QApplication(sys.argv)
    wizard = RepairUninstallWidget()
    wizard.show()
    sys.exit(app.exec_())