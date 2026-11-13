"""Default fixture remains inert; explicit PG profile is not browser authority."""
import pytest

from apps.operator_console.pg_read import PgReadSettings


def test_pg_profile_rejects_admin_or_remote():
    with pytest.raises(ValueError):
        PgReadSettings('127.0.0.1', 5432, 'vrae_p2a_012345abcdef', 'postgres', 'not-authority')
