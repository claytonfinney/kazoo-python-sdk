import base64
import json
from kazoo import exceptions
import hashlib
import re
import requests

class KazooRequest(object):
    http_methods = ["get", "post", "put", "delete"]

    def __init__(self, path, auth_required=True):
        """An object which takes a path and determines required
        parameters from it, these parameters must be passed to the execute
        method of the object
        """
        self.path = path
        self._required_param_names = self._get_params_from_path(self.path)
        self.auth_required = auth_required

    def _get_params_from_path(self, path):
        param_regex = re.compile("{([a-zA-Z0-9_]+)}")
        param_names = param_regex.findall(path)
        return param_names

    def _get_headers(self, token=None):
        headers = {"Content-Type":"application/json"}
        if self.auth_required:
            headers["X-Auth-Token"] = token
        return headers


    def execute(self, base_url, method='get', data=None, token=None, **kwargs):
        if self.auth_required and token is None:
            raise exceptions.AuthenticationRequiredError("This method requires "
                                                         "an auth token")
        if method.lower() not in self.http_methods:
            raise exceptions.InvalidHttpMethodError("method {0} is not a valid"
                                                    " http method".format(
                                                        method))
        for param_name in self._required_param_names:
            if param_name not in kwargs:
                raise ValueError("keyword argument {0} is required".format(
                    param_name))
        subbed_path = self.path.format(**kwargs)
        full_url = base_url + subbed_path
        headers = self._get_headers(token=token)
        req_func = getattr(requests, method)
        if data:
            raw_response = req_func(full_url, data=json.dumps({"data": data}), headers=headers)
        else:
            raw_response = req_func(full_url, headers=headers)
        if raw_response.status_code == 500:
            raise exceptions.KazooApiError("Internal Server Error")
        response = raw_response.json
        if response["status"] == "error":
            raise exceptions.KazooApiError(response["message"])
        return response


class UsernamePasswordAuthRequest(KazooRequest):

    def __init__(self, username, password, account_name):
        super(UsernamePasswordAuthRequest, self).__init__("/user_auth",
                                                          auth_required=False)
        self.username = username
        self.password = password
        self.account_name = account_name

    def execute(self, base_url):
        data = {
            "credentials": self._get_hashed_credentials(),
            "account_name": self.account_name,
        }
        return super(UsernamePasswordAuthRequest, self).execute(base_url, method="put", data=data)

    def _get_hashed_credentials(self):
        m = hashlib.md5()
        m.update("{0}:{1}".format(self.username, self.password))
        return m.hexdigest()


class ApiKeyAuthRequest(KazooRequest):

    def __init__(self, api_key):
        super(ApiKeyAuthRequest, self).__init__("/api_auth",
                                                auth_required=False)
        self.api_key = api_key

    def execute(self, base_url):
        data = {
            "api_key": self.api_key
        }
        return super(ApiKeyAuthRequest, self).execute(base_url, data=data, method="put")


