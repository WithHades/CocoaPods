import logging


def config_log(name, level, log_path):
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