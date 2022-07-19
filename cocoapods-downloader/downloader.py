import os
import subprocess
import sys

os.chdir("./cocoapods-downloader")
cmd = "ruby " + sys.argv[1]
ret = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, encoding='gbk')
ret.wait(timeout=10 * 60)
