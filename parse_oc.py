import json
import os
import re
import subprocess
import sys

import chardet
import pymongo

import logging

import utils


class global_var:
    file_path = None

    def __init__(self, logger, lib_source_info, feature_string, feature_method, feature_lib, compiler):
        self.logger = logger
        self.lib_source_info = lib_source_info
        self.feature_string = feature_string
        self.feature_method = feature_method
        self.feature_lib = feature_lib
        self.compiler = compiler


def parse_file_type(source_files):
    if "{" in source_files:
        types = source_files[source_files.find("{") + 1:source_files.find("}")]
        types = [type_.strip() for type_ in types.split(",")]
        return types
    if "." in source_files:
        return source_files[source_files.find(".")+1:]
    return None


def get_db_collecttions():
    client = pymongo.MongoClient("mongodb://%s:%s@code-analysis.org:%s" % (os.environ.get("MONGOUSER"), os.environ.get("MONGOPASS"), os.environ.get("MONGOPORT")))
    db = client["lib"]
    lib_source_info = db["lib_source_info"]

    feature_string = db["feature_string"]
    feature_method = db["feature_method"]
    # 理论上只需要前面两张表就好了，测试阶段多添加一个表格
    feature_lib = db["feature_lib"]
    return lib_source_info, feature_string, feature_method, feature_lib


def update_library_lib(lib_name, lib_version, subspecs_name, method_signs, strings, feature_lib):
    base_query = {"name": lib_name, "version": lib_version}
    if subspecs_name is not None:
        base_query.update({"subspecs_name": subspecs_name})
    for method_sign in method_signs:
        if len(list(feature_lib.find(base_query.update({"method": method_sign})))) > 0:
            continue
        feature_lib.update_one(base_query, {'$push': {'method': method_sign}}, True)
    for string in strings:
        if len(list(feature_lib.find(base_query.update({"string": string})))) > 0:
            continue
        feature_lib.update_one(base_query, {'$push': {'string': string}}, True)


def update_library_mtd(lib_name, lib_version, subspecs_name, method_signs, feature_method):
    lib_info = {"name": lib_name, "version": lib_version}
    if subspecs_name is not None:
        lib_info.update({"subspecs_name": subspecs_name})
    for method_sign in method_signs:
        if len(list(feature_method.find({"method": method_sign, "library": lib_info}))) > 0:
            continue
        feature_method.update_one({"method": method_sign}, {"$push": {"library": lib_info}}, True)


def update_library_str(lib_name, lib_version, subspecs_name, strings, feature_string):
    lib_info = {"name": lib_name, "version": lib_version}
    if subspecs_name is not None:
        lib_info.update({"subspecs_name": subspecs_name})
    for string in strings:
        if len(list(feature_string.find({"string": string, "library": lib_info}))) > 0:
            continue
        feature_string.update_one({"string": string}, {"$push": {"library": lib_info}}, True)


def decode_oct_str(string):
    if len(string) != 0:
        model = re.findall(r"((\\\d{3})+)", string)
        for m in model:
            byte_m = b''
            for c in m[0].split("\\")[1:]:
                byte_m += int.to_bytes(int(c, 8), length=1, byteorder='little')
            try:
                str_m = str(byte_m, chardet.detect(byte_m).get('encoding'))
                string = string.replace(m[0], str_m)
            except Exception as e:
                print(e)
    return string


def traverse(json_data):
    method_signs = []
    strings = []
    if "kind" in json_data:
        kind = json_data["kind"]
        if kind == "ObjCMethodDecl":
            if "mangledName" in json_data:
                method_signs.append(json_data["mangledName"])
        if kind == "StringLiteral":
            if "value" in json_data:
                string = decode_oct_str(json_data["value"][1:-1])
                strings.append(string)
            return method_signs, strings
    if "inner" in json_data:
        for inner in json_data["inner"]:
            ret_method_signs, ret_strings = traverse(inner)
            method_signs = list(set(method_signs).union(set(ret_method_signs)))
            strings = list(set(strings).union(set(ret_strings)))
    return method_signs, strings


def parse_ast(data, data_len, global_vals, code_file):
    start = 0
    end = data_len
    method_signs = []
    strings = []
    while start < end:
        try:
            ast = json.loads(data[start:end])
            ret_method_signs, ret_strings = traverse(ast)
            method_signs = list(set(method_signs).union(set(ret_method_signs)))
            strings = list(set(strings).union(set(ret_strings)))
            start = end
            end = data_len
        except json.decoder.JSONDecodeError as err:
            if err.msg == 'Extra data':
                end = start + err.pos
            else:
                global_vals.logger.error("Could not generate ast. file_path: %s, error: %s" % (code_file, err.msg))
                break
    return method_signs, strings


def clang(lib_name, lib_version, subspecs_name, global_vals, code_file):
    if not code_file.endswith(".m") and not code_file.endswith(".h") and not code_file.endswith(".c"):
        return
    pwd = os.getcwd()
    os.chdir(os.path.dirname(code_file))
    cmd = global_vals.compiler + " -fsyntax-only -ferror-limit=0 -Xclang -ast-dump=json {} >> ast_result.txt".format(code_file)
    subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE).wait()
    if not os.path.exists("ast_result.txt"):
        global_vals.logger.error("Could not generate ast. file_path: %s, error code is 0." % code_file)
        return
    with open("ast_result.txt", "r", encoding="UTF-8") as f:
        data = f.read()
        data_len = f.seek(0, 2) - f.seek(0)
    if "StringLiteral" not in data and "ObjCMethodDecl" not in data:
        global_vals.logger.error("Could not generate ast. file_path: %s, error code is 1." % code_file)
        return
    method_signs, strings = parse_ast(data, data_len, global_vals, code_file)
    os.remove("ast_result.txt")

    cmd = global_vals.compiler + " -fsyntax-only -ferror-limit=0 -Xclang -dump-tokens {} >> tokens_result.txt 2>&1".format(code_file)
    subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE).wait()
    if not os.path.exists("tokens_result.txt"):
        global_vals.logger.error("Could not generate tokens. file_path: %s, error code is 2." % code_file)
    else:
        with open("tokens_result.txt", "r", encoding="UTF-8") as f:
            data = f.read()
        ret = re.findall(r"string_literal '\"([\s\S]*?)\"'.*Loc=<", data)
        strings += ret
    update_library_lib(lib_name, lib_version, subspecs_name, method_signs, strings, global_vals)
    update_library_mtd(lib_name, lib_version, subspecs_name, method_signs, global_vals)
    update_library_str(lib_name, lib_version, subspecs_name, strings, global_vals)
    os.chdir(pwd)


def parse_code_files(lib_name, lib_version, subspecs_name, global_vals, code_file, source_file_type):
    file_type = code_file[code_file.find(".")+1:] if code_file.find(".") != -1 else "None"
    if source_file_type is not None and file_type not in source_file_type:
        return
    if code_file.endswith(".h") or code_file.endswith(".m") or code_file.endswith(".c"):
        clang(lib_name, lib_version, subspecs_name, global_vals, code_file)


def parse_source_files(lib_name, lib_version, source_files, global_vals, subspecs_name=None):
    if isinstance(source_files, str):
        source_files = [source_files]
    for source_file in source_files:
        if "*" not in source_files:
            if not os.path.isdir(os.path.join(global_vals.file_path, source_file)):
                global_vals.logger.error("maybe the lib has one oc file? file_path: %s" % global_vals.file_path)
                continue
            source_file = os.path.join(global_vals.file_path, source_file)
            source_file = os.path.join(source_file, "*")
        source_file_type = parse_file_type(source_file)
        source_file_path = source_file[:source_file.find("*")]
        source_file_path = os.path.join(global_vals.file_path, source_file_path)
        for root, dirs, files in os.walk(source_file_path):
            for file in files:
                parse_code_files(lib_name, lib_version, subspecs_name, global_vals, os.path.join(root, file), source_file_type)


def parse_source_info(lib_name, lib_version, source_info, global_vals, subspecs_name=None):
    if "source_files" not in source_info and "subspecs" not in source_info:
        msg = "ERROR: Could not find source_files field in library info! file_path: %s" % global_vals.file_path
        if subspecs_name is not None:
            msg += ", subspecs: %s" % subspecs_name
        global_vals.logger.error(subspecs_name)
        return
    if "source_files" in source_info:
        parse_source_files(lib_name, lib_version, source_info["source_files"], global_vals, subspecs_name)
    else:
        for subspec in source_info["subspecs"]:
            space_name = subspec["name"] if "name" in subspec else "unknown"
            parse_source_info(lib_name, lib_version, subspec, global_vals, space_name)


def main():
    if len(sys.argv) < 1:
        print("please input compiler!")
        return

    lib_path = "../libraries"
    if not os.path.exists(lib_path):
        return

    logger = utils.config_log(name=__name__, level=logging.INFO, log_path="./logs/{}.log".format(os.path.abspath(__file__)))
    lib_source_info, feature_string, feature_method, feature_lib = get_db_collecttions()
    global_vals = global_var(logger, lib_source_info, feature_string, feature_method, feature_lib, compiler=sys.argv[1])

    os.chdir(lib_path)
    cwd_path = os.getcwd()
    for path in os.listdir(cwd_path):
        file_path = os.path.join(cwd_path, path)
        global_vals.file_path = file_path
        if os.path.isfile(file_path) or not os.listdir(file_path):
            continue
        lib_name = path[:path.rfind("_")]
        lib_version = path[path.rfind("_") + 1:]
        ret = lib_source_info.find_one({"name": lib_name, "version": lib_version})
        if not ret:
            logger.error("ERROR: Could not find library in database! file_path: %s" % file_path)
            continue
        parse_source_info(lib_name, lib_version, ret, global_vals)

