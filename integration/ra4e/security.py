"""Independent privilege planes and real restricted SQL, never authority from ACL text."""
from psycopg import sql

from .lab import RecoveryDenied, digest, encode

TABLE_ACL_SCOPE = frozenset(
    [('ra4a_bytes', n) for n in ['events', 'graphs', 'objects']]
    + [('ra4a_private', n) for n in ['assignments', 'migrations', 'principals']]
    + [('ra4a_review_test', n) for n in ['assignments', 'audit', 'claims', 'outbox', 'proposals', 'sections', 'states']]
)
SCHEMAS = ['ra4a', 'ra4a_private', 'ra4a_bytes', 'ra4a_review_test', 'public']
PRIVILEGES = ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'TRUNCATE', 'REFERENCES', 'TRIGGER']


def table_acl_entries(c, raw, owner):
    # Empty ACL is NOT NULL; COALESCE must not replace an empty explicit ACL.
    # PG16 aclexplode rejects zero-dimensional empty arrays. Inspect actual SQL
    # cardinality first: explicit zero entries stay zero, never owner defaults.
    is_null, cardinality = c.execute('SELECT %s::aclitem[] IS NULL,cardinality(%s::aclitem[])', (raw, raw)).fetchone()
    if not is_null and cardinality == 0:
        return []
    return c.execute("SELECT CASE WHEN a.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee)::text END,pg_get_userbyid(a.grantor)::text,a.privilege_type,a.is_grantable FROM aclexplode(coalesce(%s::aclitem[],acldefault('r',%s::regrole))) a ORDER BY 1,2,3,4", (raw, owner)).fetchall()


def independent_planes(c):
    # Names, not cluster-specific role/OID numbers, form every compared identity.
    return {
        'default_acls': c.execute("SELECT pg_get_userbyid(d.defaclrole),coalesce(n.nspname,'<GLOBAL>'),d.defaclobjtype,d.defaclacl::text,CASE WHEN a.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee)::text END,pg_get_userbyid(a.grantor),a.privilege_type,a.is_grantable FROM pg_default_acl d LEFT JOIN pg_namespace n ON n.oid=d.defaclnamespace LEFT JOIN LATERAL aclexplode(d.defaclacl) a ON true ORDER BY 1,2,3,5,6,7,8").fetchall(),
        'schema_acls': c.execute("SELECT n.nspname,pg_get_userbyid(n.nspowner),n.nspacl::text FROM pg_namespace n WHERE n.nspname=ANY(%s) ORDER BY 1", (SCHEMAS,)).fetchall(),
        'column_acls': c.execute("SELECT n.nspname,t.relname,a.attname,a.attnum,format_type(a.atttypid,a.atttypmod),a.attacl::text FROM pg_attribute a JOIN pg_class t ON t.oid=a.attrelid JOIN pg_namespace n ON n.oid=t.relnamespace WHERE n.nspname=ANY(%s) AND t.relkind='r' AND a.attnum>0 AND NOT a.attisdropped ORDER BY 1,2,4", (SCHEMAS,)).fetchall(),
        # Database name/physical OID are environment-local; compare this exact
        # restore-target database's owner, ACL and connection attributes instead.
        'database_acl': c.execute("SELECT pg_get_userbyid(datdba),encoding,datcollate,datctype,datallowconn,datconnlimit,datacl::text FROM pg_database WHERE datname=current_database()").fetchall(),
        'sequence_acls': c.execute("SELECT n.nspname,t.relname,pg_get_userbyid(t.relowner),t.relacl::text FROM pg_class t JOIN pg_namespace n ON n.oid=t.relnamespace WHERE n.nspname=ANY(%s) AND t.relkind='S' ORDER BY 1,2", (SCHEMAS,)).fetchall(),
        'procedure_acls': c.execute("SELECT n.nspname,p.proname,pg_get_function_identity_arguments(p.oid),p.prokind,pg_get_userbyid(p.proowner),p.prosecdef,p.proconfig,p.proacl::text FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname=ANY(%s) AND p.prokind IN ('f','p') ORDER BY 1,2,3", (SCHEMAS,)).fetchall(),
        'role_attributes': c.execute("SELECT rolname,rolsuper,rolinherit,rolcreaterole,rolcreatedb,rolcanlogin,rolreplication,rolbypassrls,rolconnlimit,rolvaliduntil FROM pg_roles WHERE rolname LIKE 'ra4a_%' OR rolname LIKE 'p2a_%' OR rolname LIKE 'p2b1_%' ORDER BY 1").fetchall(),
        'membership_options': c.execute("SELECT r.rolname,m.rolname,pg_get_userbyid(a.grantor),a.admin_option,a.inherit_option,a.set_option FROM pg_auth_members a JOIN pg_roles r ON r.oid=a.roleid JOIN pg_roles m ON m.oid=a.member WHERE r.rolname LIKE 'ra4a_%' OR r.rolname LIKE 'p2a_%' OR r.rolname LIKE 'p2b1_%' ORDER BY 1,2,3").fetchall(),
    }


def effective_privileges(c):
    rows = c.execute("SELECT r.rolname,n.nspname,t.relname,p.privilege,has_table_privilege(r.oid,t.oid,p.privilege) FROM pg_roles r CROSS JOIN pg_class t JOIN pg_namespace n ON n.oid=t.relnamespace CROSS JOIN unnest(%s::text[]) p(privilege) WHERE (r.rolname LIKE 'ra4a_%%' OR r.rolname LIKE 'p2a_%%' OR r.rolname LIKE 'p2b1_%%') AND t.relkind='r' AND n.nspname=ANY(%s) ORDER BY 1,2,3,4", (PRIVILEGES, SCHEMAS)).fetchall()
    return [r for r in rows if (r[1], r[2]) in TABLE_ACL_SCOPE]


def security_snapshot(c):
    result = independent_planes(c)
    result['has_table_privilege'] = effective_privileges(c)
    result['has_column_privilege'] = c.execute("SELECT r.rolname,n.nspname,t.relname,a.attname,p.privilege,has_column_privilege(r.oid,t.oid,a.attnum,p.privilege) FROM pg_roles r CROSS JOIN pg_class t JOIN pg_namespace n ON n.oid=t.relnamespace JOIN pg_attribute a ON a.attrelid=t.oid CROSS JOIN unnest(ARRAY['SELECT','INSERT','UPDATE','REFERENCES']) p(privilege) WHERE (r.rolname LIKE 'ra4a_%%' OR r.rolname LIKE 'p2a_%%' OR r.rolname LIKE 'p2b1_%%') AND n.nspname=ANY(%s) AND t.relkind='r' AND a.attnum>0 AND NOT a.attisdropped ORDER BY 1,2,3,4,5", (SCHEMAS,)).fetchall()
    result['has_schema_privilege'] = c.execute("SELECT r.rolname,n.nspname,has_schema_privilege(r.oid,n.oid,'USAGE'),has_schema_privilege(r.oid,n.oid,'CREATE') FROM pg_roles r CROSS JOIN pg_namespace n WHERE (r.rolname LIKE 'ra4a_%%' OR r.rolname LIKE 'p2a_%%' OR r.rolname LIKE 'p2b1_%%') AND n.nspname=ANY(%s) ORDER BY 1,2", (SCHEMAS,)).fetchall()
    return result


def denied(c, statement, params=None):
    import psycopg
    try:
        with c.transaction():
            c.execute(statement, params)
            # Force rollback even if the unexpected statement could succeed.
            raise RecoveryDenied('RESTRICTED_SQL_UNEXPECTEDLY_ALLOWED')
    except psycopg.Error as exc:
        if exc.sqlstate != '42501':
            raise RecoveryDenied('RESTRICTED_SQL_DENIAL_WRONG_SQLSTATE') from None
        return exc.sqlstate


def runtime_audit(environment, dbname, graphs):
    from vrae.persistence.private_bytes import locator
    from .manifest import verify_sources
    positives = verify_sources(environment, dbname, graphs)
    rows = []
    with environment.connect(dbname=dbname) as admin:
        tables = admin.execute("SELECT n.nspname,t.relname,(SELECT a.attname FROM pg_attribute a WHERE a.attrelid=t.oid AND a.attnum>0 AND NOT a.attisdropped ORDER BY a.attnum LIMIT 1) FROM pg_class t JOIN pg_namespace n ON n.oid=t.relnamespace WHERE t.relkind='r' ORDER BY 1,2").fetchall()
        tables = [r for r in tables if r[:2] in TABLE_ACL_SCOPE]
    for role in sorted(environment.runtime_passwords):
        with environment.connect(role, dbname=dbname) as c:
            identity = c.execute('SELECT session_user,current_user,rolsuper,rolbypassrls FROM pg_roles WHERE rolname=session_user').fetchone()
            if identity != (role, role, False, False):
                raise RecoveryDenied('ACTUAL_RUNTIME_IDENTITY_DENIED')
            for schema, table, first in tables:
                name = sql.SQL('{}.{}').format(sql.Identifier(schema), sql.Identifier(table))
                statements = [
                    ('SELECT', sql.SQL('SELECT * FROM {} LIMIT 0').format(name)),
                    ('INSERT', sql.SQL('INSERT INTO {} DEFAULT VALUES').format(name)),
                    ('UPDATE', sql.SQL('UPDATE {} SET {}={} WHERE false').format(name, sql.Identifier(first), sql.Identifier(first))),
                    ('DELETE', sql.SQL('DELETE FROM {} WHERE false').format(name)),
                    ('TRUNCATE', sql.SQL('TRUNCATE {}').format(name)),
                ]
                for operation, statement in statements:
                    rows.append({'role': role, 'table': schema + '.' + table, 'operation': operation, 'sqlstate': denied(c, statement)})
    point = locator(graphs['404'])
    args = (point.tenant, point.ref_id, point.source_run, point.report, point.version, point.target_digest)
    scoped = []
    for role in ['ra4a_test_a_app']:
        with environment.connect(role, dbname=dbname) as c:
            with c.transaction():
                count = len(c.execute('SELECT * FROM ra4a_bytes.read_graph(%s,%s,%s,%s,%s,%s)', args).fetchall())
            if count != len(graphs['404'].artifacts):
                raise RecoveryDenied('AUTHORIZED_ORIGINAL_READ_INCOMPLETE')
            scoped.append({'role': role, 'result': 'AUTHORIZED_ORIGINAL_READ', 'objects': count})
    for role, function in [('ra4a_test_b_app', 'ra4a_bytes.read_graph'), ('ra4a_test_unassigned', 'ra4a_bytes.read_graph'), ('p2b1_test_b_reviewer', 'ra4a_review_test.load_target'), ('p2a_test_a_writer', 'ra4a_bytes.read_graph')]:
        with environment.connect(role, dbname=dbname) as c:
            statement = sql.SQL('SELECT * FROM {}.{}(%s,%s,%s,%s,%s,%s)').format(*map(sql.Identifier, function.split('.')))
            label = 'UNGRANTED_READ_FUNCTION_DENIED' if role == 'p2a_test_a_writer' else 'WRONG_TENANT_OR_UNASSIGNED_DENIED'
            scoped.append({'role': role, 'result': label, 'sqlstate': denied(c, statement, args)})
    with environment.connect(dbname=dbname) as admin:
        for table, column in [('ra4a_private.principals', 'enabled'), ('ra4a_private.assignments', 'active'), ('ra4a_review_test.assignments', 'active')]:
            name = sql.SQL('{}.{}').format(*map(sql.Identifier, table.split('.')))
            def toggle(value):
                admin.execute(sql.SQL("UPDATE {} SET {}=%s WHERE db_role='p2b1_test_a_reviewer'").format(name, sql.Identifier(column)), (value,))
            toggle(False)
            try:
                with environment.connect('p2b1_test_a_reviewer', dbname=dbname) as c:
                    scoped.append({'case': table + '.' + column, 'result': 'DISABLED_OR_REVOKED_DENIED',
                        'sqlstate': denied(c, 'SELECT * FROM ra4a_review_test.load_target(%s,%s,%s,%s,%s,%s)', args)})
            finally:
                toggle(True)
    return {'actual_sql': True, 'raw_private_denials': rows, 'scoped_allow_deny': scoped,
            'authorized_originals': positives, 'raw_denial_count': len(rows), 'matrix_sha256': digest(encode(rows))}
