import os
from concurrent.futures import ThreadPoolExecutor

import pymongo

import mongo
if os.path.exists("secret.py"):
    import secret


def get_db_collecttions():
    client = pymongo.MongoClient("mongodb://%s:%s@code-analysis.org:%s" % (os.environ.get("MONGOUSER"), os.environ.get("MONGOPASS"), os.environ.get("MONGOPORT")))
    db = client["lib"]
    feature_string = db["feature_string"]
    feature_method = db["feature_method"]
    feature_lib = db["feature_lib"]
    feature_weight = db["feature_weight"]
    return feature_string, feature_method, feature_lib, feature_weight


def main():
    feature_string, feature_method, feature_lib, feature_weight = get_db_collecttions()
    ret = feature_lib.find(no_cursor_timeout=True)
    with ThreadPoolExecutor(1) as threadPool:
        for lib in ret:
            def get_weights(field, lib, collection):
                base_query = {"name": lib["name"], "version": lib["version"]}
                if "subspecs_name" in lib:
                    base_query.update({"subspecs_name": lib["subspecs_name"]})
                if field not in lib:
                    return {}
                # 根据方法在整个数据库中出现的次数进行分组
                count_col = {}
                for field_ in lib[field]:
                    field_info = collection.find_one({field: field_})
                    if field_info is None:
                        print(field_, base_query)

                    length = len(field_info["library"])
                    if length not in count_col:
                        count_col[length] = []
                    count_col[length].append(field_info[field])

                # 组间根据频率设置权重
                lengths = list(count_col.keys())
                weight_lengths = [1/length for length in lengths]
                sums_ = sum(weight_lengths)
                weight_lengths = [length/sums_ for length in weight_lengths]

                weight_fields = []
                for length, weight_length in zip(lengths, weight_lengths):
                    # 计算组内权重
                    field_weight = weight_length / len(count_col[length])
                    for field_ in count_col[length]:
                        if len(field_) > 3:
                            weight_fields.append({"key": field_, "weight": field_weight})

                feature_weight.update_one(base_query, {"$set": {field: weight_fields}}, True)

            threadPool.submit(get_weights, "method", lib, feature_method)
            threadPool.submit(get_weights, "string", lib, feature_method)

    ret.close()


if __name__ == "__main__":
    main()



