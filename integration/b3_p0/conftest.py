import os
import uuid

import pytest
from psycopg import sql

from .lab import Lab
from .support import Case, bootstrap


@pytest.fixture(scope="session")
def lab():
    value = Lab(os.environ["B3_RUN_LABEL"])
    try:
        value.start()
        bootstrap(value)
        yield value
    finally:
        value.stop()


@pytest.fixture
def case(lab):
    name = "vrae_p2b1_" + uuid.uuid4().hex[:12]
    with lab.connect(dbname="postgres") as c:
        c.execute(
            sql.SQL("CREATE DATABASE {} TEMPLATE {}").format(
                sql.Identifier(name), sql.Identifier(lab.dbname)
            )
        )
    try:
        with lab.connect(dbname=name) as c:
            yield Case(lab, name, c)
    finally:
        with lab.connect(dbname="postgres") as c:
            c.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
