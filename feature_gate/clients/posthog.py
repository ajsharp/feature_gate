import json
import logging
import requests
import structlog
from pathlib import Path

from structlog.contextvars import (
    bind_contextvars,
    clear_contextvars,
    merge_contextvars,
    bound_contextvars,
)

class PosthogAPI:
  def __init__(self, api_key, project_id):
    self.api_key = api_key
    self.host='https://app.posthog.com'
    self.project_id = project_id

    bind_contextvars(klass="PosthogAPI", project_id=project_id)
    structlog.configure(
      processors=[
        merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.dict_tracebacks,
        structlog.processors.JSONRenderer(),
      ],
      logger_factory=structlog.WriteLoggerFactory(
        file=Path("development").with_suffix(".log").open("wt")
      ),
    )
    self.logger = structlog.get_logger()

  def api_key(self):
     return self.api_key

  def project_id(self):
    return self.project_id

  def list_features(self):
    path = f'/api/projects/{self.project_id}/feature_flags'
    with bound_contextvars(method="list_features"):
      response = self._get(path)
      return self._map_list_response(response)

  def create_feature(self, name, description, deleted=False, active=False):
    with bound_contextvars(method="create_feature"):
      path = f'/api/projects/{self.project_id}/feature_flags'
      payload = {
        'name': description,
        'key': name,
        'deleted': deleted,
        'active': active
      }
      response = self._post(path, payload)
      return self._map_single_response(response)

  def fetch_feature(self, key):
    features = self.list_features()["data"]
    for entry in features:
        if "key" in entry and entry["key"] == key:
            return entry
    return None

  def delete_feature(self, key):
    feature = self.fetch_feature(key)
    if feature == None:
      raise Exception(f"Feature {key} not found")
    else:
      path = f'/api/projects/{self.project_id}/feature_flags/{feature["id"]}'
      with bound_contextvars(method="delete_feature"):
        payload = {
          'deleted': True
        }
        response = self._patch(path, payload)
        return self._map_single_response(response)

  def _get(self, path):
    with bound_contextvars(method="get"):
      url = f"{self.host}{path}"
      headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {self.api_key}"
      }
      return requests.get(url, headers=headers)

  def _post(self, path, payload):
    url = f"{self.host}{path}"
    with bound_contextvars(method="post", url=url):
      json_payload = json.dumps(payload)
      headers = self._get_headers()
      return requests.post(url, data=json_payload, headers=headers)


  def _patch(self, path, payload):
    url = f"{self.host}{path}"
    with bound_contextvars(method="patch", url=url):
      json_payload = json.dumps(payload)
      headers = self._get_headers()
      return requests.patch(url, data=json_payload, headers=headers)

  def _get_headers(self):
    return {
      "Content-Type": "application/json",
      "Authorization": f"Bearer {self.api_key}"
    }

  def _map_single_response(self, response):
    ret = None
    if response.status_code == 200 or response.status_code == 201:
        data = response.json()
        self.logger.info("request successful", status_code=response.status_code, response=data)
        ret = self._map_single_response_success(data)
    else:
        data = response.json()
        self.logger.info("request failed", status_code=response.status_code, response=data)
        ret = self._map_error_response(response.status_code, data)
    return ret

  def _map_list_response(self, response):
    ret = None
    if response.status_code == 200 or response.status_code == 201:
        data = response.json()
        self.logger.info("request successful", status_code=response.status_code, response=data)
        ret = self._map_list_response_success(data)
    else:
        data = response.json()
        self.logger.info("request failed", status_code=response.status_code, response=data)
        ret = self._map_error_response(response.status_code, data)
    return ret

  def _map_error_response(self, code, data):
    return {
      "errors": [
        {
          "status": code,
          "detail": data.get("detail"),
          "code": data.get("code"),
          "type": data.get("type")
        }
      ]
    }

  def _map_single_response_success(self, data):
    return {
      "data": data
    }

  def _map_list_response_success(self, data):
    return {
      "data": data.get("results"),
      "pagination": {
        "next": data.get("next"),
        "previous": data.get("previous")
      }
    }