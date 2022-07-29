import logging
import os


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



