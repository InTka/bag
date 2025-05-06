import os
import sys
import shutil
import PyInstaller.__main__
from PIL import Image

base_dir = os.path.dirname(os.path.abspath(__file__))

def clean_build(name):
    build_dir = os.path.join(base_dir, "build")
    spec_file = os.path.join(base_dir, f"{name}.spec")
    dist_dir = os.path.join(base_dir, "dist")
    exe_file = os.path.join(dist_dir, f"{name}.exe")
    if os.path.exists(build_dir):
        shutil.rmtree(build_dir)
    if os.path.exists(spec_file):
        os.remove(spec_file)
    if os.path.exists(exe_file):
        os.remove(exe_file)

def convert_png_to_ico(png_path, ico_path):
    try:
        img = Image.open(png_path)
        img.save(ico_path, format='ICO', sizes=[(256,256)])
        print(f"成功生成ICO文件: {ico_path}")
    except Exception as e:
        print(f"PNG转ICO失败: {e}\n请安装pillow库: pip install pillow")
        sys.exit(1)

# 自动转换PNG为ICO
png_path = os.path.join(base_dir, "修复_卸载", "此程序exe图标.png")
ico_path = os.path.splitext(png_path)[0] + ".ico"
if not os.path.exists(ico_path):
    convert_png_to_ico(png_path, ico_path)

# 1. 打包修复卸载程序（修复_卸载\修复_卸载.py）
clean_build("修复_卸载")
PyInstaller.__main__.run([
    "--name=修复_卸载",
    "--onefile",
    # "--windowed",  # 注释掉此行以启用控制台窗口
    f"--paths={base_dir}",
    # 修改后
    # 建议将PNG转换为ICO格式以获得最佳效果
    "--icon", ico_path,
    os.path.join(base_dir, "修复_卸载", "修复_卸载.py"),
])

# 复制修复_卸载.exe到根目录，供下一个步骤用
dist_exe = os.path.join(base_dir, "dist", "修复_卸载.exe")
target_exe = os.path.join(base_dir, "修复_卸载.exe")
if os.path.exists(dist_exe):
    shutil.copy2(dist_exe, target_exe)
else:
    print("ERROR: 未找到dist/修复_卸载.exe，打包流程中断。")
    sys.exit(1)

# 2. 打包解包器（解包器_安装器\解包器_安装器.py，把修复_卸载.exe作为数据文件而不是脚本）
clean_build("解包器_安装器")
png_path = os.path.join(base_dir, "解包器_安装器", "此程序exe图标.png")
if not os.path.exists(png_path):
    raise FileNotFoundError(f"找不到图标文件: {png_path}")
ico_path = os.path.splitext(png_path)[0] + ".ico"
if not os.path.exists(ico_path):
    convert_png_to_ico(png_path, ico_path)

PyInstaller.__main__.run([
    "--name=解包器_安装器",
    "--onefile",
    "--windowed",
    f"--paths={base_dir}",
    "--icon", ico_path,
    "--add-data", f"{target_exe};.",
    "--add-data", os.path.join(base_dir, "解包器_安装器", "被解包的ANTIKINS文件图标.png") + ';.',
    os.path.join(base_dir, "解包器_安装器", "解包器_安装器.py"),
])

# 打包完成后删除根目录的修复_卸载.exe
if os.path.exists(target_exe):
    try:
        os.remove(target_exe)
    except Exception as e:
        print(f"警告: 删除 {target_exe} 失败: {e}")

# 3. 打包打包器（打包器\打包器.py）
clean_build("打包器")
PyInstaller.__main__.run([
    "--name=打包器",
    "--onefile",
    "--windowed",
    f"--paths={base_dir}",
    os.path.join(base_dir, "打包器", "打包器.py"),
])

# 删除所有spec文件和build文件夹
for name in ["修复_卸载", "解包器_安装器", "打包器"]:
    spec_file = os.path.join(base_dir, f"{name}.spec")
    build_dir = os.path.join(base_dir, "build")
    if os.path.exists(spec_file):
        try:
            os.remove(spec_file)
        except Exception as e:
            print(f"警告: 删除 {spec_file} 失败: {e}")
    if os.path.exists(build_dir):
        try:
            shutil.rmtree(build_dir)
        except Exception as e:
            print(f"警告: 删除 {build_dir} 失败: {e}")

print("全部打包完成。")
