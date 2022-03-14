"""
Gathers state of each plugin Endpoints.
"""

import json
import logging
import re
import requests
import tempfile
import time
import urllib
import re
from multiprocessing.pool import ThreadPool
import urllib3
from math import ceil
import datetime

import os.path

from ruxit.api.base_plugin import RemoteBasePlugin
from ruxit.api.exceptions import ConfigException

logger = logging.getLogger(__name__)
PLUGIN_STATE_ENDPOINT = "api/config/v1/plugins"
METRIC_INGEST_ENDPOINT = "api/v2/metrics/ingest"

class PluginState(RemoteBasePlugin):
    def initialize(self, **kwargs):
        """
        Pass on configuration parameters to the class.
        """
        self.metricid = self.config.get("metric_id")
        self.token = self.config.get("api_key")
        if not self.token:
            raise ConfigException("Please enter a valid API token")
        self.tenant_id = self.config.get("tenant_id").strip().rstrip("/")
        self.tempfile = tempfile.gettempdir() + '/' + "".join([c for c in self.activation.endpoint_name if re.match(r'\w', c)]) + ".dt"
        self.get_pluginid = self.config.get("get_pluginid", True)
        logger.info(f"Using tempfile: {self.tempfile}")
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def query(self, **kwargs):
        list_states = self.get_state()
        state_list = list_states["states"]
        payload = []
        for state in state_list:
            temp = {'pluginid': state['pluginId'], 'state': state['state'], 'statedescription': state['stateDescription'], 'endpointname': state['endpointName']}
            payload.append(temp)
        self.doPostRequest(payload)

    def request(self, url):
        headers = {"Authorization": "Api-Token " + self.token, "Content-Type": "application/json"}
        result = requests.get(url, verify=False, headers=headers)
        if result.status_code == 429:
            return self.request(url)
        if result.status_code > 300:
            raise RuntimeError(result.text)
        return result

    def concatenateJson(self, state_json, endpoint_json):
        states_list = state_json["states"]
        endpoint_list = endpoint_json["values"]
        for state in states_list:
            if state['endpointId'] != "":
                for endpoint in endpoint_list:
                    if state['endpointId'] == endpoint['id']:
                        state['endpointName'] = endpoint['name']
                        break
        return state_json

    def get_state(self):
        api_state_response = self.request(f'{self.tenant_id}/{PLUGIN_STATE_ENDPOINT}/{self.get_pluginid}/states')
        api_response_state = api_state_response.json()

        api_endpoint_response = self.request(f'{self.tenant_id}/{PLUGIN_STATE_ENDPOINT}/{self.get_pluginid}/endpoints')
        api_response_endpoint = api_endpoint_response.json()

        api_mergedjson = self.concatenateJson(api_response_state, api_response_endpoint)

        return api_mergedjson

    def doPostRequest(self, datadir):
        headers = {"Authorization": "Api-Token " + self.token, "Content-Type": "text/plain"}
        errorList = {"DISABLED", "ERROR_AUTH", "ERROR_COMMUNICATION_FAILURE", "ERROR_CONFIG", "ERROR_TIMEOUT", "ERROR_UNKNOWN", "INCOMPATIBLE", "LIMIT_REACHED", "NOTHING_TO_REPORT", "STATE_TYPE_UNKNOWN", "UNINITIALIZED", "UNSUPPORTED", "WAITING_FOR_STATE"}
        for data in datadir:
            if data['state'] in errorList:
                payload = self.metricid + ',' + 'name=' + data['pluginid'] + ',' + 'endpointname=' + '\"' + data['endpointname'] + '\"' + ',' + 'state=' + data['state'] + ',' + 'statedescription=' + data['statedescription'] + ' ' + str(0) + "\n#" + self.metricid + " gauge dt.meta.unit=\"Percent\""
                response = requests.post(f'{self.tenant_id}/{METRIC_INGEST_ENDPOINT}', data=payload.encode('utf-8'), verify=False, headers=headers)
                logger.info(f"Pushing to the API: " + payload)
                if response.status_code != 202:
                    logger.warn("MINT call failed. Input: " + '\n'.join(data) + " Output: " + response.text)
            else:
                payload = self.metricid + ',' + 'name=' + data['pluginid'] + ',' + 'endpointname=' + '\"' + data['endpointname'] + '\"' + ',' + 'state=' + data['state'] + ',' + 'statedescription=' + "\"OK\"" + ' ' + str(100) + "\n#" + self.metricid + " gauge dt.meta.unit=\"Percent\""
                response = requests.post(f'{self.tenant_id}/{METRIC_INGEST_ENDPOINT}', data=payload.encode('utf-8'), verify=False, headers=headers)
                logger.info(f"Pushing to the API: " + payload)
                if response.status_code != 202:
                    logger.warn("MINT call failed. Input: " + '\n'.join(data) + " Output: " + response.text)








