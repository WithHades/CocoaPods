import logging
import os
import re

import chardet


def config_log(name, level, log_path):
    if not os.path.exists(os.path.dirname(log_path)):
        os.makedirs(os.path.dirname(log_path))
    logger = logging.getLogger(name)
    logger.setLevel(level=level)
    handler = logging.FileHandler(log_path)
    handler.setLevel(level)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    console = logging.StreamHandler()
    console.setLevel(level)
    logger.addHandler(handler)
    logger.addHandler(console)
    return logger


def parse_file_type(source_files: str) -> [None, list]:
    """
    get the file type that source files defines.
    for example:
    source_files is "/a/b/**.{h,m}", then return ["h","m"]
    source_files is "/a/b/**.h", then return ["h"]
    return None means that the file can be of any type
    :param source_files: source file expression.
    :return: the file type that supported.
    """
    if "{" in source_files:
        types = source_files[source_files.find("{") + 1:source_files.find("}")]
        types = [type_.strip() for type_ in types.split(",")]
        return types
    if "." in source_files:
        return source_files[source_files.find(".")+1:]
    return None


def decode_oct_str(string: str) -> str:
    """
    decode a string than contains octal characters.
    for example:
    string = "\\345\\244\\247\\345\\256\\266\\345\\245\\275\\343\\200\\202"
    return "大家好。"
    :param string: result of decoding by utf-8
    :return:
    """
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
