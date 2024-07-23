#!/usr/bin/env python3

import click
import click_log
import logging
import time
from zero_scale.app import scale_to_zero as zero

logger = logging.getLogger(__name__)
click_log.basic_config(logger)


@click.command()
@click_log.simple_verbosity_option(logger)
@click.option('-s', '--scale', 'scale',
              default=0,
              help='Sets the scale of a deployment')
@click.option('-p', '--period', 'period',
              default=60,
              help='The time (seconds) between checks')
@click.option('--success-threshold', 'success_threshold',
              default=5,
              help='Number of positive results before action is taken')
@click.option('-n', '--namespace', 'namespace',
              default='default',
              help='The k8 namespace')
@click.option('-h', '--hpa', 'hpa_name',
              default='default',
              help='The HPA name')
@click.option('-m', '--metric-name', 'metric_name',
              default='default',
              help='The metric name')
@click.option('-d', '--deployment', 'deployment_name',
              default='default',
              help='The deployment to modify')
@click.option('-po', '--part-of', 'part_of',
              help='The part_of value to filter against',
              required=True)
def run(scale, period, success_threshold, namespace, hpa_name, metric_name, deployment_name, part_of):


    params = click.get_current_context().params
    scaler = zero.ScaleToZero(params)
    successes = 0

    while True:
        try:
            time.sleep(period)
            logger.debug(f'successes: %s', successes)

            # Only call these once per iteration, saves overloading the API
            current_metric_value = scaler.current_metric_value()
            current_scale = scaler.current_scale()

            # Skip current iteration if scale is already 0
            if  (current_metric_value == 0 and current_scale == 0):
                logger.info(f'Scale already 0 - skipping')
                continue

            # Scale to 0 if number of positive results are hit
            if successes == success_threshold:
                logger.info(f'Metric is zero: Scaling %s to 0', deployment_name)
                scaler.scale_deployment(0)
                successes = 0
                continue

            # HPA is disabled when target deployment scale is zero.
            # Force scale to be 1 if metrics > 1
            if  (current_metric_value > 1 and current_scale == 0):
                logger.info(f'Non zero metric detected: Scaling to 1')
                scaler.scale_deployment(1)
                continue

            # Keep track of positive results
            if current_metric_value == 0:
                successes += 1
            else:
                logger.info('Metric not zero: Letting the HPA do its thing')
                successes = 0


        except Exception as e:
            logger.info(e)
            pass

if __name__ == '__main__':
    run()
