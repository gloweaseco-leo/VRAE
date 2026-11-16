"""Owner acceptance checkpoint, not a new permission or Worker lease.

Populate only after Owner notifies the accepted main containing the performance
fix and required source pin. Merely opening/merging an unaccepted Draft cannot
enable execution. Current deliberate None prevents every real P40 submission.
"""
ACCEPTED_PERFORMANCE_MAIN = "a9604f570528e599a0b8215a8957208d76e47b89"


def enabled():
    return ACCEPTED_PERFORMANCE_MAIN is not None
