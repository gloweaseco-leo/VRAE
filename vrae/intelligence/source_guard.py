"""Select the explicit source profile; never mutate the legacy Guard module."""
from vrae.interpretation import guard
from vrae.interpretation import disc_report_v1


def for_evaluator(version):
    return disc_report_v1 if version in ('ra2b6-1.0.2', 'ra2b6-1.0.3', 'ra2b6-1.0.4') else guard
