import click
import click_log
import logging
import json
import os
from numify.numify import numify
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from tenacity import retry, retry_if_exception_type


class ScaleToZero:

    def __init__(self, params):

        self.logger = logging.getLogger('zero_scale.cli')

        self.scale = params['scale']
        self.period = params['period']
        self.success_threshold = params['success_threshold']
        self.namespace = params['namespace']
        self.hpa_name = params['hpa_name']
        self.metric_name = params['metric_name']
        self.deployment_name = params['deployment_name']
        self.part_of = params['part_of']

        self.logger.debug(f'Initialized with params: %s', params)

        # Figure out if we are running in a k8 cluster and load the appropriate config
        if os.getenv('KUBERNETES_SERVICE_HOST'):
            self.logger.info("Using in cluster config")
            config.load_incluster_config()
        else:
            self.logger.info("Not in cluster - Loading kube config")
            config.load_kube_config()

        self.client_api = client.ApiClient()
        self.apps_api = client.AppsV1Api()

    @retry(retry=retry_if_exception_type(ApiException))
    def current_metric_value(self):
        metrics_url='/apis/custom.metrics.k8s.io/v1beta1/namespaces/{}/pods/*/{}?labelSelector=app.kubernetes.io/part-of={}' .format(self.namespace, self.metric_name , self.part_of)
        try:
            res = json.loads(self.client_api.call_api(metrics_url, 'GET', auth_settings=['BearerToken'], _preload_content=False)[0].data.decode('utf-8'))
            value = [element for element in res['items'] if element["metricName"] == self.metric_name][0]['value']
            self.logger.debug(f'current_metric_value: %s', value)
            try:
                # Numbers can be returned in abbriviated k/m/g format - convert it- 1k=1000 etc
                return int(value)
            except ValueError as ve:
                return(numify(value))

        except ApiException as ae:
            self.logger.info(f'current_metric_value: ApiClient exeption')
            self.logger.debug(f'current_metric_value: %s', ae)

    @retry(retry=retry_if_exception_type(ApiException))
    def scale_deployment(self, scale):

        self.logger.info(f'Scaling %s:%s to %s', self.namespace, self.deployment_name, self.scale)
        try:
            api_response = self.apps_api.patch_namespaced_deployment_scale(name=self.deployment_name, namespace=self.namespace, body={'spec': {'replicas': scale}})
        except ApiException as ae:
            self.logger.info(f'scale_deployment: AppsV1Api exeption')
            self.logger.debug(f'scale_deployment: %s', ae)
        except ValueError as ve:
            self.logger.info(f'scale_deployment: ValueError exeption')
            self.logger.debug(f'scale_deployment: %s', ve)

    @retry(retry=retry_if_exception_type(ApiException))
    def current_scale(self):

        try:
            res = self.apps_api.read_namespaced_deployment_scale(name=self.deployment_name, namespace=self.namespace)
            value = res.status.replicas
            if value == None:
                value = 0

            self.logger.debug(f'current_scale: %s', value)
            return value

        except ApiException as ae:
            self.logger.info(f'current_scale: AppsV1Api exeption')
            self.logger.debug(f'current_scale: %s', ae)
        except ValueError as ve:
            self.logger.info(f'current_scale: ValueError exeption')
            self.logger.debug(f'current_scale: %s', ve)
