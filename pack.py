import os
import sys
import subprocess
import shutil

# 1. 自動讀取 requirements.txt 提取純套件名稱
hidden_imports = [
    'webview', 'sqlite3', 'backend',
    'backend.api', 'backend.db', 'backend.ledger_manager'
]

if os.path.exists('requirements.txt'):
    with open('requirements.txt', 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                pkg = line.split('==')[0].split('>=')[0].split('<=')[0].strip()
                if pkg and pkg not in hidden_imports:
                    hidden_imports.append(pkg)

# 2. 執行 PyArmor 加密
print("[*] 正在執行 PyArmor 加密混淆...")
if os.path.exists('pyarmor_dist'):
    shutil.rmtree('pyarmor_dist')

res = subprocess.run([sys.executable, '-m', 'pyarmor.cli', 'gen', '-O', 'pyarmor_dist', 'main.py', 'backend'])
if res.returncode == 0:
    print("[V] 加密完成！")
    entry_point = os.path.join('pyarmor_dist', 'main.py')
    search_paths = ['pyarmor_dist', '.']
else:
    print("[!] PyArmor 混淆略過，改用原碼打包。")
    entry_point = 'main.py'
    search_paths = ['.']

# 3. 組裝 PyInstaller 指令
cmd = [
    sys.executable, '-m', 'PyInstaller',
    '--noconfirm',
    '--onedir',
    '--windowed',
    '--collect-all', 'backend',
    '--collect-all', 'pywebview',
    '--add-data', 'frontend;frontend',
    '--add-data', 'templates;templates',
    '--name', 'MyApp_Windows'
]

for p in search_paths:
    cmd.extend(['--paths', p])

for h in hidden_imports:
    cmd.extend(['--hidden-import', h])

# 檢查是否有圖示
if os.path.exists('icon.ico'):
    cmd.extend(['--icon', 'icon.ico'])

cmd.append(entry_point)

print("[*] 正在執行 PyInstaller 封裝...")
subprocess.run(cmd)

# 4. 清理暫存目錄
if os.path.exists('pyarmor_dist'):
    shutil.rmtree('pyarmor_dist')
if os.path.exists('build'):
    shutil.rmtree('build')
if os.path.exists('MyApp_Windows.spec'):
    os.remove('MyApp_Windows.spec')

print("[V] 本機打包作業完成！執行檔位於 dist/MyApp_Windows/MyApp_Windows.exe")