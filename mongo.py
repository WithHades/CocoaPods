import os

import pymongo


class mongodb:
    def __init__(self):
        self._lib_name = ""
        self._lib_version = ""
        self._subspecs_name = ""
        self._get_db_collecttions()

    def set_lib(self, lib_name, lib_version, subspecs_name):
        self._lib_name = lib_name
        self._lib_version = lib_version
        self._subspecs_name = subspecs_name


    def _get_db_collecttions(self) -> None:
        """
        get the collections from the mongodb."""
        client = pymongo.MongoClient("mongodb://%s:%s@code-analysis.org:%s" % (os.environ.get("MONGOUSER"), os.environ.get("MONGOPASS"), os.environ.get("MONGOPORT")))
        self._db = client["lib"]
        self._lib_source_info = self._db["lib_source_info"]
        self._feature_string = self._db["feature_string"]
        self._feature_method = self._db["feature_method"]
        self._feature_lib = self._db["feature_lib"]


    def update_library_lib(self, method_signs: set, strings: set) -> None:
        """
        update the library_lib collection.
        :param method_signs: A set of method signatures.
        :param strings: A set of strings.
        """
        base_query = {"name": self._lib_name, "version": self._lib_version}
        if self._subspecs_name is not None and self._subspecs_name != "":
            base_query.update({"subspecs_name": self._subspecs_name})

        for method_sign in method_signs:
            if len(list(self._feature_lib.find({**base_query, "method": method_sign}))) > 0:
                continue
            self._feature_lib.update_one(base_query, {'$push': {'method': method_sign}}, True)

        for string in strings:
            if len(list(self._feature_lib.find({**base_query, "string": string}))) > 0:
                continue
            self._feature_lib.update_one(base_query, {'$push': {'string': string}}, True)


    def update_library_mtd(self, method_signs: set) -> None:
        """
        update the feature_method collection.
        :param method_signs: A set of method signatures.
        :return:
        """
        lib_info = {"name": self._lib_name, "version": self._lib_version}
        if self._subspecs_name is not None and self._subspecs_name != "":
            lib_info.update({"subspecs_name": self._subspecs_name})
        for method_sign in method_signs:
            if len(list(self._feature_method.find({"method": method_sign, "library": lib_info}))) > 0:
                continue
            self._feature_method.update_one({"method": method_sign}, {"$push": {"library": lib_info}}, True)


    def update_library_str(self, strings: set) -> None:
        """
        update the feature_string collection.
        :param strings: A set of strings.
        """
        lib_info = {"name": self._lib_name, "version": self._lib_version}
        if self._subspecs_name is not None and self._subspecs_name != "":
            lib_info.update({"subspecs_name": self._subspecs_name})
        for string in strings:
            if len(list(self._feature_string.find({"string": string, "library": lib_info}))) > 0:
                continue
            self._feature_string.update_one({"string": string}, {"$push": {"library": lib_info}}, True)


    def update_all(self, method_signs, strings) -> None:
        """
        update the method signatures and strings to feature_lib/feature_method/feature_string
        :param method_signs: A set of method signatures.
        :param strings: A set of strings.
        :return:
        """
        self.update_library_lib(method_signs, strings)
        self.update_library_mtd(method_signs)
        self.update_library_str(strings)


    def drop(self) -> None:
        """
        drop the collentions: feature_string/feature_method/feature_lib.
        :return:
        """
        self._feature_string.drop()
        self._feature_method.drop()
        self._feature_lib.drop()


    def find_source_info(self, lib_name, lib_version):
        """
        find the library source info from the db by its name and version.
        :param lib_name:
        :param lib_version:
        :return:
        """
        return self._lib_source_info.find_one({"name": lib_name, "version": lib_version})
