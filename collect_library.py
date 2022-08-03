import argparse
import json
import os
import utils
from mongo import mongodb


def find_specs(path: str, lib_source_info, logger):
    """
    iterate all the specs and collection the information.
    :param path:
    :param lib_source_info: collection
    :param logger:
    :return:
    """

    for root, dirs, files in os.walk(path):
        for file in files:
            lib_resource = os.path.join(root, file)
            if not lib_resource.endswith('.podspec.json'):
                continue
            try:
                with open(lib_resource, "r", encoding="UTF-8") as f:
                    data = f.read().replace("${", "_{").replace("$(", "_(")
                    lib_info = json.loads(data)
                if "name" in lib_info and "version" in lib_info:
                    lib_name, lib_version = lib_info["name"], str(lib_info["version"])
                else:
                    sp = lib_resource.split(os.sep)
                    lib_name, lib_version = sp[-3], sp[-2]
                logger.info("update! lib_name: %s, lib_version: %s." % (lib_name, lib_version))
                base_query = {"name": lib_name, "version": lib_version}
                lib_source_info.update_one(base_query, {"$set": lib_info}, True)
            except Exception as e:
                logger.error("A error occurred while updating lib_source_info: %s" % e.args[0])


def main(path, drop, loglevel):
    logger = utils.config_log(name=__name__, level=loglevel, log_path="./logs/{}.log".format(os.path.basename(__file__).replace(".py", "")))
    lib_source_info = mongodb().get_specific_col("lib_source_info")
    if drop:
        lib_source_info.drop()
    find_specs(path, lib_source_info, logger)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='collect the library information and write to mongo.')
    parser.add_argument('--path', default="../Specs/Specs", help="the path of Specs/Specs.")
    parser.add_argument('--drop', default=False, action='store_true', help="drop the clooections.")
    parser.add_argument('--loglevel', default='INFO')
    args = parser.parse_args()
    main(args.path, args.drop, args.loglevel)

