#
# Copyright (c) 2020 Seagate Technology LLC and/or its Affiliates
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# For any questions about this software or licensing,
# please email opensource@seagate.com or cortx-questions@seagate.com.
#

"""
ObjectRecoveryValidator acts as object validator which performs necessary action for object oid to be deleted.
"""
import logging
import json
from datetime import datetime

from s3backgrounddelete.cortx_s3_kv_api import CORTXS3KVApi
from s3backgrounddelete.cortx_s3_object_api import CORTXS3ObjectApi
from s3backgrounddelete.cortx_s3_index_api import CORTXS3IndexApi
from s3backgrounddelete.cortx_s3_constants import CONNECTION_TYPE_CONSUMER
from s3backgrounddelete.cortx_s3_constants import CONNECTION_TYPE_PRODUCER
import math

#zero/null object oid in base64 encoded format
NULL_OBJ_OID = "AAAAAAAAAAA=-AAAAAAAAAAA="

class ObjectRecoveryValidator:
    """This class is implementation of Validator for object recovery."""

    def __init__(self, config, probable_delete_records,
                 logger=None, objectapi=None, kvapi=None, indexapi=None):
        """Initialise Validator"""
        self.config = config
        self.current_obj_in_VersionList = None
        self.probable_delete_records = probable_delete_records
        if(logger is None):
            self._logger = logging.getLogger("ObjectRecoveryValidator")
        else:
            self._logger = logger
        if(objectapi is None):
            self._objectapi = CORTXS3ObjectApi(self.config, connectionType=CONNECTION_TYPE_CONSUMER, logger=self._logger)
        else:
            self._objectapi = objectapi
        if(kvapi is None):
            self._kvapi = CORTXS3KVApi(self.config, connectionType=CONNECTION_TYPE_CONSUMER, logger=self._logger)
        else:
            self._kvapi = kvapi
        if(indexapi is None):
            self._indexapi = CORTXS3IndexApi(self.config, connectionType=CONNECTION_TYPE_CONSUMER, logger=self._logger)
        else:
            self._indexapi = indexapi

    def isVersionEntryOlderThan(self, versionInfo, older_in_mins = 15):
        if (versionInfo is None):
            return False

        object_version_time = versionInfo["create_timestamp"]
        now = datetime.utcnow()
        date_time_obj = datetime.strptime(object_version_time, "%Y-%m-%dT%H:%M:%S.000Z")
        timedelta = now - date_time_obj
        timedelta_mns = math.floor(timedelta.total_seconds()/60)
        return (timedelta_mns >= older_in_mins)

    def delete_object_from_storage(self, obj_oid, layout_id, pvid_str):
        status = False
        self._logger.info("pvid_str : " + pvid_str)
        ret, response = self._objectapi.delete(obj_oid, layout_id, pvid_str)
        if (ret):
            status = ret
            self._logger.info("Deleted obj " + obj_oid + " from motr store")
        elif (response.get_error_status() == 404):
            self._logger.info("The specified object " + obj_oid + " does not exist")
            status = True
        else:
            self._logger.info("Failed to delete obj " + obj_oid + " from motr store")
            self.logAPIResponse("VERSION DEL", "", obj_oid, response)
        return status

    def delete_index(self, index_id):
        ret, response = self._indexapi.delete(index_id)
        if (ret):
            self._logger.info("Deleted index: " + index_id)
        elif (response.get_error_status() == 404):
            # Index not found
            self._logger.info("Index " + index_id + " does not exist")
            ret = True
        else:
            self._logger.info("Failed to delete index " + index_id)
            self.logAPIResponse("DEL INDEX", index_id, "", response)
        return ret

    def delete_key_from_index(self, index_id, key_id, api_prefix):
        ret, response = self._kvapi.delete(index_id, key_id)
        if (ret):
            self._logger.info("Deleted Key " + key_id + " from index " + index_id)
        elif (response.get_error_status() == 404):
            # Item not found
            self._logger.info("key " + key_id + " does not exist in index " + index_id)
            ret = True
        else:
            self._logger.info("Failed to delete key " + key_id + " from index " + index_id)
            self.logAPIResponse(api_prefix, index_id, key_id, response)
        return ret

    def get_key_from_index(self, index_id, key):
        ret, response_data = self._kvapi.get(index_id, key)
        if (ret):
            # Found key in index
            self._logger.info("Key "+ str(key) + " exists in index " + str(index_id))
            return ret, response_data
        elif (response_data.get_error_status() == 404):
            self._logger.info("Key "+ str(key) + " does not exist in index " + str(index_id))
            return True, None
        else:
            self._logger.info("Failed to retrieve key " + str(key) + " from index " + str(index_id))
            self.logAPIResponse("GET INDEX", index_id, key, response_data)
            return ret, None

    #get_object_versionEntry
    def get_object_Entry(self, indx_id, key_in_index):
        objInfo = None
        status = False
        ret, response_data = self.get_key_from_index(indx_id, key_in_index)
        if (ret):
            status = ret
            if (response_data is not None):
                # Found key in index
                self._logger.info("Key: " + str(key_in_index) + " exists in index " + str(indx_id))
                self._logger.info("Version details: " + str(response_data.get_value()))
                objInfo = json.loads(response_data.get_value())
            else:
                self._logger.info("Key: " + str(key_in_index) + " does not exist in index " + str(indx_id))
        else:
            self._logger.info("Key: " + str(key_in_index) + " does not exist in index " + str(indx_id))

        return status, objInfo

    def get_object_metadata(self, index_id, key):
        obj_metadata = None
        status, response = self.get_key_from_index(index_id, key)
        if (status and response is not None):
            obj_metadata = json.loads(response.get_value())
        return status, obj_metadata

    def logAPIResponse(self, resAPI, oid, key, response):
        if (response.get_error_status() != 200):
            self._logger.info("Failed API " + resAPI + " on Oid= " + str(oid) + ", Key= " + str(key) +
                              " Response: " + str(response.get_error_status()) + " " +
                              str(response.get_error_message()))

    def process_probable_delete_record(self, delete_entry = False, delete_obj_from_store = False):
        self._logger.info("process_probable_delete_record Entry")
        object_version_list_index_id = self.object_leak_info["objects_version_list_index_oid"]
        object_extended_md_index_id = None
        status = False
        obj_ver_key = None
        obj_ext_key = None
        ver_motr_oid_key = "motr_oid"
        ver_layout_id_key = "layout_id"
        ver_api_prefix = "VERSION LIST DEL"
        ext_motr_oid_key = "OID"
        ext_layout_id_key = "layout-id"
        ext_api_prefix = "EXTENDED MD LIST DEL"
        pvid_key = "PVID"
        part_no = 0
        frag_no = 0
        ext_ver_id = "0"
        # parent oid available only for parts of multipart object (i.e extended object)
        parent_oid = NULL_OBJ_OID
        if "parent_oid" in self.object_leak_info:
            parent_oid = self.object_leak_info["parent_oid"]

        # We dont remove entries from part table, since the table will have
        # the latest entry that we want to keep. the old oid that we want to 
        # delete is present in the key of PDI and deleting it is sufficient
        # TODO : there will come a time when we would want to delete the part
        # index table, currently its being handled by s3server, but incase
        # there is a failure in s3server then bgdel should be able to do it.
        if "version_key_in_index" in self.object_leak_info:
            obj_ver_key = self.object_leak_info["version_key_in_index"]

        if "part" in self.object_leak_info:
            part_no = self.object_leak_info["part"]

        if "fno" in self.object_leak_info :
            frag_no = self.object_leak_info["fno"]

        self._logger.info("frag_no : " + str(frag_no))
        self._logger.info("part_no : " + str(part_no))

        if (parent_oid != NULL_OBJ_OID and part_no != 0):
            # This is part of a multipart object
            if len(self.object_leak_info["ext_version_id"]) != 0 :
                ext_ver_id = str(self.object_leak_info["ext_version_id"])

            try:
                object_extended_md_index_id = self.object_leak_info["extended_md_idx_oid"]
            except Exception as e:
                self._logger.error("Exception : " + str(e))
                object_extended_md_index_id = None

            if object_extended_md_index_id is not None:
                obj_ext_key = self.object_leak_info["object_key_in_index"] + "|" + \
                            ext_ver_id + "|" + "P" + \
                            str(part_no) + "|" + "F" + \
                            str(frag_no)
                self._logger.info("obj_ext_key : " + obj_ext_key)


        if (delete_obj_from_store):
            index_key_list = [(object_version_list_index_id, obj_ver_key, \
                                ver_motr_oid_key, ver_layout_id_key, ver_api_prefix)]

            if object_extended_md_index_id is not None and \
                    object_extended_md_index_id != NULL_OBJ_OID:
                self._logger.info("Extended Metadata Index is present.")
                index_key_list.clear()
                index_key_list.append((object_extended_md_index_id, obj_ext_key, \
                                ext_motr_oid_key, ext_layout_id_key, ext_api_prefix))

            for (index, key_in_index, oid_key, layout_id_key, api_prefix) in index_key_list:
                if ((index is None) or (key_in_index is None) or (len(key_in_index) == 0)):
                    self._logger.info("Either key: " + str(key_in_index) +
                                      " or index: " + str(index) + " is Empty")
                    continue

                self._logger.info("key: " + key_in_index +
                                      " index: " + index )
                if api_prefix == ext_api_prefix:
                    # Leak entry is probably the extended object of multipart
                    status = self.del_obj_from_extended_index(index, key_in_index, \
                                                oid_key, layout_id_key, pvid_key, api_prefix)
                    if (not status):
                        self._logger.info("Failed to delete object using " + key_in_index +
                                        " from extended index " + index)
                    # Break from here: Single version entry for all extended objects
                    # will be removed separately using multipart parent leak entry
                    break
                else:
                    #Leak entry is normal object
                    status = self.del_obj_from_ver_index(index, key_in_index, \
                                                oid_key, layout_id_key, pvid_key, api_prefix)
                if (not status):
                    self._logger.info("Failed to delete object using " + key_in_index +
                                      " from version index " + index)
        else:
             status = True
  
        leak_rec_key = self.probable_delete_records["Key"]
        # If 'delete_entry = True', then delete record from probable delete index, iff
        # previous status is True
        if (status and delete_entry):
            probable_index_id = self.config.get_probable_delete_index_id()
            self._logger.info("Deleting Entry from PDI with Key : " + leak_rec_key + \
                                "from index : " + probable_index_id)
            if (delete_entry and leak_rec_key is not None):
                status = self.delete_key_from_index(probable_index_id, leak_rec_key, "PROBABALE INDEX DEL")

        return status

    def del_obj_from_extended_index(self, index_id, key_in_index, \
                            obj_oid_key_in_value, layout_id_key_in_value, \
                            pvid_key_in_value, api_prefix):
        status = False
        if all(v is not None for v in [index_id, key_in_index]):
            # Fetch entry from extended index list
            status, keyInfo = self.get_object_Entry(index_id, key_in_index)
            if (not status):
                self._logger.info("Error! Failed to get object with key " + key_in_index +
                    " from index" + index_id)
                return status

            if (keyInfo is not None):
                obj_oid = keyInfo[obj_oid_key_in_value]
                layout_id = keyInfo[layout_id_key_in_value]
                pvid = keyInfo[pvid_key_in_value]
                # Delete extended object from motr store
                status = self.delete_object_from_storage(obj_oid, layout_id, pvid)
                if (status):
                    self._logger.info("Deleted object with oid " + obj_oid + " from motr store")
                else:
                    self._logger.info("Failed to delete object with oid [" + obj_oid + "] from motr store")
            else:
                self._logger.info("The key: " + key_in_index + " does not exist.")
                # status = self.delete_object_from_storage(self.object_leak_id, self.object_leak_layout_id, self.pvid_str)

            if (status):
                #EXTENDED LIST ENTRY DEL
                status = self.delete_key_from_index(index_id, key_in_index, api_prefix)
                if (status):
                    self._logger.info("Deleted key " + key_in_index + " from index " + index_id)
        return status

    def del_obj_from_ver_index(self, index_id, key_in_index, \
                            obj_oid_key_in_value, layout_id_key_in_value, \
                            pvid_key_in_value, api_prefix):
        status = False
        if all(v is not None for v in [index_id, key_in_index]):
            # Fetch version from version list
            status, keyInfo = self.get_object_Entry(index_id, key_in_index)
            if (not status):
                self._logger.info("Error! Failed to get object with key " + key_in_index +
                    " from index" + index_id)
                return status

            if (keyInfo is not None):
                # obj_oid = versionInfo["motr_oid"]
                # layout_id = versionInfo["layout_id"]
                obj_oid = keyInfo[obj_oid_key_in_value]
                layout_id = keyInfo[layout_id_key_in_value]
                pvid = keyInfo[pvid_key_in_value]
                # Delete version object from motr store
                # self.pvid is wrong, it either need to be found like above layout id
                # or needs to be passed to this function. 
                status = self.delete_object_from_storage(obj_oid, layout_id, pvid)
                if (status):
                    self._logger.info("Deleted object with oid " + obj_oid + " from motr store")
                else:
                    self._logger.info("Failed to delete object with oid [" + obj_oid + "] from motr store")
            else:
                self._logger.info("The key: " + key_in_index + " does not exist. Delete motr object")
                status = self.delete_object_from_storage(self.object_leak_id, self.object_leak_layout_id, self.pvid_str)

            if (status):
                #"VERSION LIST DEL"
                status = self.delete_key_from_index(index_id, key_in_index, api_prefix)
                if (status):
                    self._logger.info("Deleted key " + key_in_index + " from index " + index_id)

        return status

    def check_instance_is_nonactive(self, instance_id, marker=None):
        """Checks for existence of instance_id inside global instance index"""

        result, instance_response = self._indexapi.list(
                    self.config.get_global_instance_index_id(), self.config.get_max_keys(), marker)
        if(result):
            # List global instance index is success.
            self._logger.info("Index listing result :" +
                             str(instance_response.get_index_content()))
            global_instance_json = instance_response.get_index_content()
            global_instance_list = global_instance_json["Keys"]
            is_truncated = global_instance_json["IsTruncated"]

            if(global_instance_list is not None):
                for record in global_instance_list:
                    if(record["Value"] == instance_id):
                        # instance_id found. Skip entry and retry for delete oid again.
                        self._logger.info("S3 Instance is still active. Skipping delete operation")
                        return False

                if(is_truncated == "true"):
                    self.check_instance_is_nonactive(instance_id, global_instance_json["NextMarker"])

            # List global instance index results is empty hence instance_id not found.
            return True

        else:
            # List global instance index is failed.
            self._logger.error("Failed to list global instance index")
            return False

    def process_results(self):
        # Execute object leak algorithm by processing each of the entries from message_bus
        probable_delete_oid = self.probable_delete_records["Key"]
        probable_delete_value = self.probable_delete_records["Value"]
        
        self._logger.info(
            "Probable object id to be deleted : " +
            probable_delete_oid)
        try:
            self.object_leak_info = json.loads(probable_delete_value)
            # Object size based prefix
            self.oid_prefix = probable_delete_oid[:1]
            self.object_leak_id = probable_delete_oid[1:]
            self.object_leak_layout_id = self.object_leak_info["object_layout_id"]
            self.pvid_str = self.object_leak_info["pv_id"]

        except ValueError as error:
            self._logger.error(
                "Failed to parse JSON data for: " + probable_delete_value + " due to: " + error)
            return
        self.is_multipart = True if self.object_leak_info["is_multipart"] == "true" else False
        # Assumption: Key = <current oid>-<new oid> for
        # an old object of PUT overwrite request
        if (self.object_leak_info["old_oid"] == NULL_OBJ_OID):
            # In general, this record is for old object
            # For old object of PUT overwrite request, the key of probable leak record contains 4 '-'
            #   Each object oid has 1 '-', seperating high and low values
            # e.g., variable 'probable_delete_oid' contains: "Tgj8AgAAAAA=-kwAAAAAABCY=-Tgj8AgAAAAA=-lgAAAAAABCY="
            # where old obj id is "Tgj8AgAAAAA=-kwAAAAAABCY=" and new obj id is "Tgj8AgAAAAA=-lgAAAAAABCY="
            old_list = self.object_leak_id.split("-")
            if (old_list is None or (len(old_list) not in [2, 4])):
                self._logger.error("The key for old object " + str(self.object_leak_id) +
                                   " is not in the required format 'oldoid-newoid'")
                return
            self.object_leak_id = old_list[0] + "-" + old_list[1]

        # Determine object leak using information in metadata
        # Below is the implementaion of leak algorithm
        self.process_object_leak()

    def version_entry_cb(self, versionEntry, current_oid, timeVersionEntry):
        """ Processes each version entry. Return false to skip the entry. True to process it by caller"""
        if (versionEntry is None or current_oid is None):
            return False

        # Check if version entry is same as the current_oid
        if (versionEntry["motr_oid"] == current_oid):
            self.current_obj_in_VersionList = versionEntry
            return False

        # Check if version entry is recent (i.e. not older than timeVersionEntry)
        if (not self.isVersionEntryOlderThan(versionEntry, timeVersionEntry)):
            return False

        if (versionEntry["motr_oid"] != current_oid):
            return True


    def del_objects_in_extendedlist(self, object_extended_list_index):
        """
        Delete objects belonging to a multipart object from an extended index list.
        """
        bStatus = False
        ext_motr_oid_key = "OID"
        ext_layout_id_key = "layout-id"
        ext_pvid_key = "PVID"
        ext_api_prefix = "EXTENDED MD LIST DEL"
        if (object_extended_list_index is None):
            return bStatus

        part_no = 0
        if "part" in self.object_leak_info:
            part_no = self.object_leak_info["part"]

        self._logger.info("Processing extended list with total parts = " + str(part_no))
        extended_key_prefix = self.object_leak_info["object_key_in_index"] + "|" + \
            self.object_leak_info["ext_version_id"] + "|" + "P"

        parent_oid = NULL_OBJ_OID
        if "parent_oid" in self.object_leak_info:
            parent_oid = self.object_leak_info["parent_oid"]

        if (parent_oid == NULL_OBJ_OID and part_no != 0):
            # This is parent multipart object. Process extended entries
            for part in range(1, part_no + 1):
                extended_key = extended_key_prefix + str(part) + "|" + "F1"
                self._logger.info("Processing extended entry with key " + extended_key)
                status = self.del_obj_from_extended_index(object_extended_list_index, extended_key, \
                                    ext_motr_oid_key, ext_layout_id_key, ext_pvid_key, ext_api_prefix)
                bStatus = status
                if (not status):
                    self._logger.info("Failed to delete object using key [" + extended_key + \
                                    "] from extended index ")

        return bStatus


    def process_objects_in_versionlist(self, object_version_list_index, current_oid, callback, timeVersionEntry=15, marker = None):
        """
        Identify object leak due to parallel PUT using the version list.
        Initial marker should be: object key name + "/"
        """
        bStatus = False
        if (object_version_list_index is None or callback is None or current_oid is None):
            return bStatus
        self._logger.info("Processing version list for object leak oid " + self.object_leak_id)
        object_key = self.object_leak_info["object_key_in_index"]
        if (object_version_list_index is not None):
            extra_qparam = {'Prefix':object_key}
            ret, response_data = self._indexapi.list(object_version_list_index,
                self.config.get_max_keys(), marker, extra_qparam)
            if (ret):
                self._logger.info("Version listing result for object " + object_key + ": " +
                                str(response_data.get_index_content()))

                object_versions = response_data.get_index_content()
                object_version_list = object_versions["Keys"]
                is_truncated = object_versions["IsTruncated"]
                bStatus = ret
                if (object_version_list is not None):
                    self._logger.info("Processing " + str(len(object_version_list)) +
                        " objects in version list = " + str(object_version_list))

                    for object_version in object_version_list:
                        self._logger.info(
                            "Fetched object version: " +
                            str(object_version))
                        obj_ver_key = object_version["Key"]
                        obj_ver_md = json.loads(object_version["Value"])
                        # Call the callback to process version entry
                        cb_status = callback(obj_ver_md, current_oid, timeVersionEntry)

                        if (cb_status == True):
                            self._logger.info("Leak detected: Delete version object and version entry for key: " + obj_ver_key)
                            # Delete object from store and delete the version entry from the version list
                            status = self.del_obj_from_ver_index(object_version_list_index, obj_ver_key, \
                                                            "motr_oid", "layout_id", "PVID", "VERSION LIST DEL")
                            if (status):
                                self._logger.info("Deleted leaked object at key: " + obj_ver_key)
                                # Delete entry from probbale delete list as well, if any
                                indx = self.config.get_probable_delete_index_id()
                                indx_key = obj_ver_md["motr_oid"]
                                self._logger.info("Deleting entry: " + indx_key + " from probbale list")
                                status = self.delete_key_from_index(indx, indx_key, "PROBABLE INDEX DEL")
                                if (status):
                                    self._logger.info("Deleted entry: " + indx_key + " from probbale list")
                            else:
                                self._logger.info("Error! Failed to delete leaked object at key: " + obj_ver_key)
                                return False
                else:
                    self._logger.info("Error: Failed to list object versions")
                    return False

                last_key = object_versions["NextMarker"]
                if (is_truncated and last_key.startswith(object_key)):
                    bStatus = self.process_objects_in_versionlist(object_version_list_index,
                        obj_ver_key, callback, timeVersionEntry, last_key)

                return bStatus

            if (ret is False):
                self._logger.info("Failed to get Object version listing for object: " + self.object_key +
                    " Error: " + str(response_data))
                if (response_data.get_error_status() == 404):
                    self._logger.info("Object " + object_key + " is Not found(404) in the version list")

        return bStatus

    def process_object_leak(self):
        self._logger.info("Processing object leak for oid: " + self.object_leak_id)

        # Object leak detection algo: Step #2
        # Check if 'forceDelete' is set on leak entry. If yes, delete object and record from probable leak table
        force_delete = self.object_leak_info["force_delete"]
        ovli_oid = self.object_leak_info["objects_version_list_index_oid"]
        ovli_key = self.object_leak_info["version_key_in_index"]

        if (force_delete == "true"):
            # Handle Multipart parent object stale entry
            part_no = 0
            if "part" in self.object_leak_info:
                part_no = self.object_leak_info["part"]

            if (self.oid_prefix == "J" and part_no > 0):
                # part_no > 0 indicates multipart object. Prefix 'J' indicates dummy object.
                # The 'and' condition helps to clearly separate it from an empty object in Motr.
                # Delete version associated with parent multipart oid entry from the version index
                version_index = self.object_leak_info["objects_version_list_index_oid"]
                version_key = self.object_leak_info["version_key_in_index"]
                status = self.delete_key_from_index(version_index, version_key, "VERSION INDEX KEY DEL")
                if (not status):
                    self._logger.info("Multipart parent: Failed to delete version entry " + version_key +
                                      " from version index")
                else:
                    # After deleting version entry, delete extended entries of multipart dummy object
                    # from extended index
                    # Note: Below call deletes motr objects associated with extended entries and then
                    # removes extended entries of multipart object.
                    status = self.del_objects_in_extendedlist(self.object_leak_info["extended_md_idx_oid"])
                    self._logger.info("Deleted version entry associated with multipart object oid =" + self.object_leak_id)
                    probable_index_id = self.config.get_probable_delete_index_id()
                    probable_rec_key = self.probable_delete_records["Key"]
                    self._logger.info("Deleting Entry from PDI with Key : " + probable_rec_key)
                    status = self.delete_key_from_index(probable_index_id, probable_rec_key, "PROBABALE INDEX DEL")
                return

            if ("true" != self.object_leak_info["is_multipart"]):
                # This is not a multipart request
                status = self.process_probable_delete_record(True, True)
                if (status):
                    self._logger.info("Leak entry " + self.object_leak_id + " processed successfully and deleted")
                else:
                    self._logger.error("Failed to process leak oid " + self.object_leak_id)
            else:
                # This is a multipart request(Post complete OR Multipart Abort).
                # Delete only object(no versions, as version does not exist yet) and then
                # delete entry from probable delete index.
                oid = self.object_leak_id
                self._logger.info("Object " + self.object_leak_id + " is for multipart request")
                layout = self.object_leak_info["object_layout_id"]
                status = self.delete_object_from_storage(oid, layout, self.pvid_str)
                if (status):
                    self._logger.info("Object for Leak entry " + self.object_leak_id + " deleted from store")
                    status = self.process_probable_delete_record(True, False)
                    if (status):
                        self._logger.info("Leak entry " + self.object_leak_id + " processed successfully and deleted")
                    else:
                        self._logger.error("Failed to process leak oid " + self.object_leak_id + " Failed to delete entry from leak index")
                else:
                    self._logger.error("Failed to process leak oid, failed to delete object  " +
                        self.object_leak_id + " Skipping entry for next run")
            return

        obj_key = self.object_leak_info["object_key_in_index"]
        obj_list_id = self.object_leak_info["object_list_index_oid"]
        current_oid = ""

        status, current_object_md = self.get_object_metadata(obj_list_id, obj_key)
        if (status):
            # Either object exists or object does not exist.
            if (current_object_md is None):
                # Object does not exist.
                self._logger.info("Object key " + obj_key + " does not exist in object list index.")
                # If this is multipart operation, there could be no object existing in object list index
                if not self.is_multipart:
                    status = self.process_probable_delete_record(True, True)
                    if (status):
                        self._logger.info("Leak oid " + self.object_leak_id + " processed successfully and deleted")
                    else:
                        self._logger.error("Failed to process leak oid " + self.object_leak_id)
                    return
            else:
                # Object exists. Continue further with leak algorithm.
                current_oid = current_object_md["motr_oid"]
        else:
            self._logger.error("Failed to process leak oid " + self.object_leak_id +
                        " Skipping entry for the next run")
            return

        if (force_delete == "false"):
            part_no = 0
            if "part" in self.object_leak_info:
                part_no = self.object_leak_info["part"]

            if (self.oid_prefix == "J" and part_no > 0):
                if (self.object_leak_info["extended_md_idx_oid"] != NULL_OBJ_OID):
                    # This condition indicates successfull S3 POST complete API.
                    # - Check for parallel S3 POST calls by checking this oid with current/live object oid
                    # If they are different, it means this multipart is stale/leak. Delete all extended/parts objects
                    # and then the version entry.
                    if (self.object_leak_id != current_oid):
                        # This is stale/leak multipart oid. Delete version entry associated with it.
                        self._logger.info("Multipart leak for multipart oid " + self.object_leak_id)
                        version_index = self.object_leak_info["objects_version_list_index_oid"]
                        version_key = self.object_leak_info["version_key_in_index"]
                        status = self.delete_key_from_index(version_index, version_key, "VERSION INDEX KEY DEL")
                        if (not status):
                            self._logger.info("Multipart parent: Failed to delete version entry " + version_key +
                                            " from version index")
                        # Delete all objects associated with this multipart.
                        status = self.del_objects_in_extendedlist(self.object_leak_info["extended_md_idx_oid"])
                        if status:
                            # Remove leak entry from probable delete list index
                            status = self.process_probable_delete_record(True, False)
                            if status:
                                self._logger.info("Processed possible multipart leak for multipart oid " + self.object_leak_id)
                        else:
                            self._logger.info("Failed to process possible multipart leak for multipart oid " + self.object_leak_id)
                    else:
                        # No leak. Remove leak entry from probable delete list index
                        status = self.process_probable_delete_record(True, False)
                        self._logger.info("No leak detected for multipart oid " + self.object_leak_id + " . Removed leak entry")
                else:
                    # This condition indicates successful Multipart PUT request API.
                    # - Check for parallel S3 Multipart PUT calls by checking this oid with current/live object oid
                    # in the part index. If they are different, it means this is stale/leak multipart PUT object
                    part_index_oid = NULL_OBJ_OID
                    if "part_list_idx_oid" in self.object_leak_info:
                        # This is possibly multipart PART operation
                        part_index_oid = self.object_leak_info["part_list_idx_oid"]

                    if part_index_oid != NULL_OBJ_OID:
                        status, part_info = self.get_object_Entry(part_index_oid, str(part_no))
                        if (not status):
                            self._logger.info("Error! Failed to get part info for part no:  " + str(part_no) +
                                " from part list index: " + part_index_oid)
                            return status

                        if (part_info is not None):
                            obj_oid = part_info["motr_oid"]
                            if (obj_oid != self.object_leak_id):
                                # Possible part leak. Delete part object from motr store
                                self._logger.info("PART leak for multipart part with oid " + self.object_leak_id)
                                status = self.delete_object_from_storage(self.object_leak_id, \
                                    self.object_leak_layout_id, self.pvid_str)
                                if (status):
                                    self._logger.info("Deleted part object with oid " + self.object_leak_id + " from motr store")
                                    # Remove leak entry from probable delete list index
                                    status = self.process_probable_delete_record(True, False)
                                else:
                                    self._logger.info("Failed to delete part with oid [" + self.object_leak_id + "] from motr store")
                            else:
                                # No leak. Remove leak entry from probable delete list index
                                status = self.process_probable_delete_record(True, False)
                                self._logger.info("No leak detected for part " + str(part_no) + ". Removed leak entry")
                        else:
                            # Remove leak entry from probable delete list index
                            status = self.process_probable_delete_record(True, False)
                            self._logger.info("The part: " + str(part_no) + " does not exist in part index. Removed leak entry")
                return status
            else:
                # This is leak check for simple PUT due to parallel PUT
                # Check if object is live/current
                if (self.object_leak_id != current_oid):
                    # This is stale/leak simple PUT; delete object from motr and remove version entry
                    self._logger.info("Simple PUT leak for oid " + self.object_leak_id)
                    status = self.process_probable_delete_record(True, True)
                    if status:
                        self._logger.info("Processed leak entry " + self.object_leak_id + " successfully")
                    else:
                        self._logger.info("Failed to process leak for oid " + self.object_leak_id)
                else:
                    # No leak. Remove leak entry from probable delete list index
                    status = self.process_probable_delete_record(True, False)
                    self._logger.info("No leak detected for simple object " + self.object_leak_id + ". Removed leak entry")
                return status

            # For multipart new object request, check if entry exists in multipart metadata
            # If entry does not exist, delete the object and associated leak entry from probabale delete list
            if ("true" == self.object_leak_info["is_multipart"]):
                multipart_indx = obj_list_id
                self._logger.info("Object " + self.object_leak_id + " is for multipart request with force_delete=False")
                #Check object exists in multipart metadata index
                status, response = self.get_key_from_index(multipart_indx, obj_key)
                if (status):
                    if (response is None):
                        self._logger.info("Leak entry " + self.object_leak_id + " does not exist in multipart index")
                        # This is a multipart request(Post complete OR Multipart Abort).
                        # Delete only object(no versions, as version does not exist yet) and then
                        # delete entry from probable delete index.
                        oid = self.object_leak_id
                        layout = self.object_leak_info["object_layout_id"]
                        status = self.delete_object_from_storage(oid, layout, self.pvid_str)
                        if (status):
                            self._logger.info("Object for Leak entry " + self.object_leak_id + " deleted from store")
                            status = self.process_probable_delete_record(True, True)
                            if (status):
                                self._logger.info("Leak entry " + self.object_leak_id + " processed successfully and deleted")
                            else:
                                self._logger.error("Failed to process leak oid " + self.object_leak_id +
                                    " Failed to delete entry from leak index")
                        else:
                            self._logger.error("Failed to process leak oid, failed to delete object " +
                                self.object_leak_id + " Skipping entry for next run")
                    else:
                        self._logger.info("Skipping leak entry " + self.object_leak_id + " as it exists in multipart index")
                else:
                    self._logger.error("Failed to process leak oid " + self.object_leak_id +
                        "Skipping entry. Failed to search multipart index")
                return

        # Object leak detection algo: Step #3 - For old object
        # If leak entry is corresponding to old object
        if (self.object_leak_info["old_oid"] == NULL_OBJ_OID):
            # If old object is different than current object in metadata
            if (self.object_leak_id != current_oid):
                # This means old object is no more current/live, delete it
                self._logger.info("Leak oid: " + self.object_leak_id + " does not match the current. "
                    + "Attempting to delete it")
                status = self.process_probable_delete_record(True, True)
                if (status):
                    self._logger.info("Leak oid {Old} " + self.object_leak_id + " processed successfully and deleted")
                else:
                    self._logger.info("Error!Failed to delete Leak oid {Old} " + self.object_leak_id)
                return
            else:
                # old object is still current/live as per metadata
                # Check if there was any server crash
                instance_id = self.object_leak_info["global_instance_id"]
                self._logger.info("Oid " + self.object_leak_id + " exists in metadata. Check if S3 instance is active")

                if(self.check_instance_is_nonactive(instance_id) and self.config.get_cleanup_enabled()):
                    self._logger.info("Old object leak oid " + str(self.object_leak_id) +
                                      " is not associated with active S3 instance. Deleting it...")
                    status = self.process_probable_delete_record(True, True)
                    if (status):
                        self._logger.info("Leak oid " + self.object_leak_id + " processed successfully and deleted")
                    else:
                        self._logger.error("Failed to discard leak oid " + self.object_leak_id)
                else:
                    # Ignore and process leak record in next cycle
                    self._logger.info("S3 instance is active or flag to cleanup_enabled is disabled")
                    self._logger.info("Skip deletion for object leak oid " + str(self.object_leak_id))
                    self._logger.info("Remove entry from probable delete index for :" + str(self.object_leak_id))
                    status = self.process_probable_delete_record(True, False)
                    if (status):
                        self._logger.info("Leak oid " + self.object_leak_id + " processed successfully and skipped")
                    else:
                        self._logger.error("Failed to skip" + self.object_leak_id)

                return

        # Object leak detection algo: Step #4 - For new object
        if (self.object_leak_info["old_oid"] != NULL_OBJ_OID):
            # If new object is same as the current object in metadata
            if (self.object_leak_id == current_oid):
                # One of the previous PUT operations is successfull. Check if this has
                # introduced any leak due to parallel PUT operations
                timeDelayVersionProcessing = self.config.get_version_processing_delay_in_mins()
                object_version_list_index_id = self.object_leak_info["objects_version_list_index_oid"]
                obj_ver_key = self.object_leak_info["version_key_in_index"]
                self._logger.info("Processing version list for new object oid " + self.object_leak_id)
                self.process_objects_in_versionlist(object_version_list_index_id, current_oid,
                    self.version_entry_cb, timeDelayVersionProcessing, obj_key + "/")
                # After processing leak due to parallel PUT, delete probable record as new object is current/live object
                status = self.process_probable_delete_record(True, False)
                if (status):
                    self._logger.info("New object oid " + self.object_leak_id +
                        " is discarded from probable delete list")
                else:
                    self._logger.info("Failed to process new object oid " + self.object_leak_id)
            else:
                # Check if the request is in progress.
                # For this, check if new object oid is present in version table
                status, versioninfo = self.get_object_Entry(ovli_oid, ovli_key)

                if (status and versioninfo is not None):
                    self._logger.info("New obj oid: " + self.object_leak_id + " with version key:" +
                        ovli_key + " exists in version table")
                    # new object is in the version table
                    # This indicates object write was complete. Check if version metadata update is in-progress
                    # Is object in version list older than 5mins
                    bCheck = self.isVersionEntryOlderThan(versioninfo, 5)
                    if (bCheck):
                        # Version table entry was done, but latest metadata update might have failed.
                        # From S3 perspective, this object was never live.
                        # Delete new-oid object, delete probable record
                        self.process_probable_delete_record(True, True)
                    else:
                        # version metadata update is likely in progress, give it some time, ignore the
                        # record and process it in next cycle
                        self._logger.info("Skipping processing of new obj oid: " + self.object_leak_id +
                            " to a later time")
                        pass
                elif (status and versioninfo is None):
                    self._logger.info("New obj oid: " + self.object_leak_id + " with version key:" +
                        ovli_key + " does not exist in version table. Check S3 instance exist")
                    # new object is not in the version table
                    # Check if LC of the record has changed, indicating server crash
                    instance_id = self.object_leak_info["global_instance_id"]
                    if (self.check_instance_is_nonactive(instance_id)):
                        # S3 process working on new-oid has died without updating metadata.
                        # new-oid can be safely deleted, delete probable record.
                        status = self.process_probable_delete_record(True, True)
                        if (status):
                            self._logger.info("New obj oid " + self.object_leak_id + " is deleted and discarded")
                    else:
                        # S3 process is working on new-oid. Ignore the record to be processed
                        # in next schedule cycle
                        self._logger.info("Skipping processing of new obj oid: " + self.object_leak_id)
                        pass
                else:
                    self._logger.info("Failed to process new obj oid: " + self.object_leak_id +
                        "Skipping to next cycle...")
                    pass
        return
