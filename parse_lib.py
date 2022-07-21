import os


lib_path = "../libraries"

if not os.path.exists(lib_path):
    exit(0)
os.chdir(lib_path)
cwd_path = os.getcwd()
for path in os.listdir(cwd_path):
    file_path = os.path.join(cwd_path, path)
    if not os.path.exists(file_path) or os.listdir(file_path):
        continue

