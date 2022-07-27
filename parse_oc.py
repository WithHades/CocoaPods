import argparse
import json
import os
import re
import subprocess
import sys

import chardet
import pymongo

import logging

from clang.cindex import Index, CursorKind, Config

import utils
from ALibFileParser import parse


class global_var:
    file_path = None

    def __init__(self, logger, lib_source_info, feature_string, feature_method, feature_lib, compiler, libclang):
        self.logger = logger
        self.lib_source_info = lib_source_info
        self.feature_string = feature_string
        self.feature_method = feature_method
        self.feature_lib = feature_lib
        self.compiler = compiler
        self.libclang = libclang


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


def update_library_lib(lib_name, lib_version, subspecs_name, method_signs, strings, global_vals):
    base_query = {"name": lib_name, "version": lib_version}
    if subspecs_name is not None:
        base_query.update({"subspecs_name": subspecs_name})
    for method_sign in method_signs:
        if len(list(global_vals.feature_lib.find({**base_query, "method": method_sign}))) > 0:
            continue
        global_vals.feature_lib.update_one(base_query, {'$push': {'method': method_sign}}, True)

    for string in strings:
        if len(list(global_vals.feature_lib.find({**base_query, "string": string}))) > 0:
            continue
        global_vals.feature_lib.update_one(base_query, {'$push': {'string': string}}, True)


def update_library_mtd(lib_name, lib_version, subspecs_name, method_signs, global_vals):
    lib_info = {"name": lib_name, "version": lib_version}
    if subspecs_name is not None:
        lib_info.update({"subspecs_name": subspecs_name})
    for method_sign in method_signs:
        if len(list(global_vals.feature_method.find({"method": method_sign, "library": lib_info}))) > 0:
            continue
        global_vals.feature_method.update_one({"method": method_sign}, {"$push": {"library": lib_info}}, True)


def update_library_str(lib_name, lib_version, subspecs_name, strings, global_vals):
    lib_info = {"name": lib_name, "version": lib_version}
    if subspecs_name is not None:
        lib_info.update({"subspecs_name": subspecs_name})
    for string in strings:
        if len(list(global_vals.feature_string.find({"string": string, "library": lib_info}))) > 0:
            continue
        global_vals.feature_string.update_one({"string": string}, {"$push": {"library": lib_info}}, True)


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
    cmd = global_vals.compiler + " -fsyntax-only -fno-color-diagnostics -ferror-limit=0 -Xclang -ast-dump=json {} >> ast_result.txt".format(code_file)
    subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE).wait()
    if not os.path.exists("ast_result.txt"):
        global_vals.logger.error("Could not generate ast. file_path: %s, error code is 0." % code_file)
        return
    with open("ast_result.txt", "r", encoding="UTF-8") as f:
        data = f.read()
        data_len = f.seek(0, 2) - f.seek(0)
    if "StringLiteral" not in data and "ObjCMethodDecl" not in data:
        global_vals.logger.error("Could not find StringLiteral or ObjCMethodDecl in ast file. file_path: %s." % code_file)
        return
    method_signs, strings = parse_ast(data, data_len, global_vals, code_file)
    os.remove("ast_result.txt")

    cmd = global_vals.compiler + " -fsyntax-only -fno-color-diagnostics -ferror-limit=0 -Xclang -dump-tokens {} >> tokens_result.txt 2>&1".format(code_file)
    subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE).wait()
    if not os.path.exists("tokens_result.txt"):
        global_vals.logger.error("Could not generate tokens. file_path: %s, error code is 2." % code_file)
    else:
        with open("tokens_result.txt", "r", encoding="UTF-8") as f:
            data = f.read()
        ret = re.findall(r"string_literal '\"([\s\S]*?)\"'.*Loc=<", data)
        strings += ret
        os.remove("tokens_result.txt")
    update_library_lib(lib_name, lib_version, subspecs_name, method_signs, strings, global_vals)
    update_library_mtd(lib_name, lib_version, subspecs_name, method_signs, global_vals)
    update_library_str(lib_name, lib_version, subspecs_name, strings, global_vals)
    os.chdir(pwd)


def traverse_libclang_ast(lib_name, lib_version, subspecs_name, global_vals, cursor):
    if cursor.kind == CursorKind.STRING_LITERAL:
        string = cursor.displayname[1:-1]
        string = decode_oct_str(string)
        update_library_lib(lib_name, lib_version, subspecs_name, [], [string], global_vals)
        update_library_str(lib_name, lib_version, subspecs_name, [string], global_vals)
        return
    if cursor.kind == CursorKind.OBJC_CLASS_METHOD_DECL or cursor.kind == CursorKind.OBJC_INSTANCE_METHOD_DECL:
        method_sign = "+" if cursor.kind == CursorKind.OBJC_CLASS_METHOD_DECL else "-"
        method_sign += "[{} {}]".format(cursor.lexical_parent.displayname, cursor.displayname)
        update_library_lib(lib_name, lib_version, subspecs_name, [method_sign], [], global_vals)
        update_library_mtd(lib_name, lib_version, subspecs_name, [method_sign], global_vals)
    for cur in cursor.get_children():
        traverse_libclang_ast(lib_name, lib_version, subspecs_name, global_vals, cur)


def libclang(lib_name, lib_version, subspecs_name, global_vals, code_file):
    index = Index.create()
    tu = index.parse(code_file)
    traverse_libclang_ast(lib_name, lib_version, subspecs_name, global_vals, tu.cursor)


def parse_code_files(lib_name, lib_version, subspecs_name, global_vals, code_file):
    if code_file.endswith(".h") or code_file.endswith(".m") or code_file.endswith(".c"):
        if global_vals.libclang is not None:
            libclang(lib_name, lib_version, subspecs_name, global_vals, code_file)
        else:
            clang(lib_name, lib_version, subspecs_name, global_vals, code_file)


def parse_source_files(lib_name, lib_version, source_files, global_vals, subspecs_name=None):
    if isinstance(source_files, str):
        source_files = [source_files]
    for source_file in source_files:
        source_file_re = source_file.replace(".", r"\.").replace("**", r".*?").replace("*", r".*?")
        source_file_re = source_file_re.replace("{", r"[").replace("}", r"]")
        source_file_re = source_file_re.replace(",", "").replace(" ", "")
        for root, dirs, files in os.walk(global_vals.file_path):
            for file in files:
                code_file = os.path.join(root, file)
                try:
                    if len(re.findall(source_file_re, code_file)) <= 0: continue
                except Exception as e:
                    print(e)
                    print(source_file_re)
                    print(code_file)
                parse_code_files(lib_name, lib_version, subspecs_name, global_vals, code_file)


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


def parse_a_file(lib_name, lib_version, vendored_libraries, global_vals, subspecs_name=None):
    if isinstance(vendored_libraries, str):
        vendored_libraries = [vendored_libraries]
    for vendored_library in vendored_libraries:
        vendored_library_re = vendored_library.replace(".", r"\.").replace("**", r".*?").replace("*", r".*?")
        vendored_library_re = vendored_library_re.replace("{", r"[").replace("}", r"]")
        vendored_library_re = vendored_library_re.replace(",", "").replace(" ", "")

        for root, dirs, files in os.walk(global_vals.file_path):
            for file in files:
                code_file = os.path.join(root, file)
                if len(re.findall(vendored_library_re, code_file)) <= 0: continue
                if not code_file.endswith(".a"): continue
                method_signs_dict, strings = parse(code_file)
                method_signs = []
                for key in method_signs_dict:
                    method_signs = list(set(method_signs).union(set(method_signs_dict[key])))
                update_library_lib(lib_name, lib_version, subspecs_name, method_signs, strings, global_vals)
                update_library_mtd(lib_name, lib_version, subspecs_name, method_signs, global_vals)
                update_library_str(lib_name, lib_version, subspecs_name, strings, global_vals)


def parse_libraries(lib_name, lib_version, source_info, global_vals, subspecs_name=None):
    if "vendored_libraries" not in source_info and "subspecs" not in source_info:
        return
    if "vendored_libraries" in source_info:
        parse_a_file(lib_name, lib_version, source_info["vendored_libraries"], global_vals, subspecs_name)
    else:
        for subspec in source_info["subspecs"]:
            space_name = subspec["name"] if "name" in subspec else "unknown"
            parse_libraries(lib_name, lib_version, subspec, global_vals, space_name)


def main(compiler, drop, libclang):

    lib_path = "../libraries"
    if not os.path.exists(lib_path):
        return
    if libclang is not None:
        Config.set_library_file(libclang)
    logger = utils.config_log(name=__name__, level=logging.INFO, log_path="./logs/{}.log".format(os.path.basename(__file__).replace(".py", "")))
    lib_source_info, feature_string, feature_method, feature_lib = get_db_collecttions()
    if drop:
        feature_string.drop()
        feature_method.drop()
        feature_lib.drop()

    global_vals = global_var(logger, lib_source_info, feature_string, feature_method, feature_lib, compiler, libclang)

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
        parse_libraries(lib_name, lib_version, ret, global_vals)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='The parser for libraries.')
    parser.add_argument('--compiler', default="clang", help="the path of clang compiler.")
    parser.add_argument('--drop', default=False, action='store_true', help="Does drop the clooections of feature_method, feature_string and feature_lib.")
    parser.add_argument('--libclang', help="the path of libclang.so.")
    args = parser.parse_args()
    main(args.compiler, args.drop, args.libclang)
