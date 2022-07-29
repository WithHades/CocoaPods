import time

import idc
import idautils

import json


if len(idc.ARGV) < 2:
    print("Usage: %s <the path of result file>")
    exit(1)

result_path = idc.ARGV[1]
print("result_path: " + result_path)
print("time" + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time())))
idc.auto_wait()

sc = idautils.Strings()
strings = set()
for s in sc:
    strings.add(str(s).strip())

method_signs = set()
for ea in idautils.Functions():
    if idc.get_func_flags(ea) & (idc.FUNC_LIB | idc.FUNC_THUNK):
        continue
    func_name = idc.get_func_name(ea)
    if func_name.startswith("+[") or func_name.startswith("-["):
        method_signs.add(func_name)

with open(result_path, "w") as f:
    json.dump([list(method_signs), list(strings)], f)

idc.qexit(0)
