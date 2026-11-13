"""Independent pre-backup SQL/catalog roots; public output contains no row bytes."""
from psycopg import sql

from vrae.persistence.private_bytes import locator, verify, Artifact, ByteGraph
from integration.ra4a import p2a_support, p2b1_support

from .lab import encode, digest, RecoveryDenied
from .security import TABLE_ACL_SCOPE, table_acl_entries, security_snapshot

SCHEMAS = ['ra4a', 'ra4a_private', 'ra4a_bytes', 'ra4a_review_test']


def capture(environment, dbname):
    tables = {}
    with environment.connect(dbname=dbname) as c:
        names = c.execute("SELECT n.nspname,c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=ANY(%s) AND c.relkind='r' ORDER BY 1,2", (SCHEMAS,)).fetchall()
        for schema, name in names:
            value = c.execute(sql.SQL("SELECT coalesce(jsonb_agg(to_jsonb(x) ORDER BY to_jsonb(x)::text),'[]'::jsonb) FROM {}.{} x").format(sql.Identifier(schema), sql.Identifier(name))).fetchone()[0]
            tables[schema + '.' + name] = {'count': len(value), 'sha256': digest(encode(value))}
        catalog = {
            'roles': c.execute("SELECT rolname,rolsuper,rolinherit,rolcreaterole,rolcreatedb,rolcanlogin,rolreplication,rolbypassrls FROM pg_roles WHERE rolname LIKE 'ra4a_%' OR rolname LIKE 'p2a_%' OR rolname LIKE 'p2b1_%' ORDER BY rolname").fetchall(),
            'memberships': c.execute("SELECT r.rolname,m.rolname,a.admin_option FROM pg_auth_members a JOIN pg_roles r ON r.oid=a.roleid JOIN pg_roles m ON m.oid=a.member WHERE r.rolname LIKE 'ra4a_%' OR r.rolname LIKE 'p2a_%' OR r.rolname LIKE 'p2b1_%' ORDER BY 1,2").fetchall(),
            'policies': c.execute("SELECT schemaname,tablename,policyname,roles,cmd,qual,with_check FROM pg_policies WHERE schemaname=ANY(%s) ORDER BY 1,2,3", (SCHEMAS,)).fetchall(),
            'tables': c.execute("SELECT n.nspname,c.relname,c.relrowsecurity,c.relforcerowsecurity,pg_get_userbyid(c.relowner),c.relacl::text FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=ANY(%s) AND c.relkind='r' ORDER BY 1,2", (SCHEMAS,)).fetchall(),
            'constraints': c.execute("SELECT n.nspname,c.relname,p.conname,pg_get_constraintdef(p.oid) FROM pg_constraint p JOIN pg_class c ON c.oid=p.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=ANY(%s) ORDER BY 1,2,3", (SCHEMAS,)).fetchall(),
            'functions': c.execute("SELECT n.nspname,p.proname,pg_get_functiondef(p.oid),pg_get_userbyid(p.proowner),p.prosecdef,p.proconfig,p.proacl::text FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname=ANY(%s) ORDER BY 1,2", (SCHEMAS,)).fetchall(),
            'triggers': c.execute("SELECT n.nspname,c.relname,t.tgname,pg_get_triggerdef(t.oid) FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE NOT t.tgisinternal AND n.nspname=ANY(%s) ORDER BY 1,2,3", (SCHEMAS,)).fetchall(),
            'sequences': c.execute("SELECT schemaname,sequencename,sequenceowner,data_type::text,start_value,min_value,max_value,increment_by,cycle,cache_size,last_value FROM pg_sequences WHERE schemaname=ANY(%s) ORDER BY 1,2", (SCHEMAS,)).fetchall(),
        }
        raw_acl_evidence = []
        found = set()
        semantic_tables = []
        for row in catalog['tables']:
            schema, table, rls, force, owner, raw = row
            if (schema, table) in TABLE_ACL_SCOPE:
                kind = c.execute('SELECT relkind FROM pg_class WHERE oid=%s::regclass', (schema + '.' + table,)).fetchone()[0]
                if kind != 'r' or owner != 'ra4a_owner':
                    raise RecoveryDenied('TABLE_ACL_RELKIND_OR_OWNER_CHANGED')
                entries = table_acl_entries(c, raw, owner)
                raw_acl_evidence.append({'table': schema + '.' + table, 'relkind': kind, 'owner': owner,
                    'raw_relacl': raw, 'expanded_entries': entries})
                semantic_tables.append((schema, table, rls, force, owner, entries))
                found.add((schema, table))
            else:
                semantic_tables.append(row)
        if found != TABLE_ACL_SCOPE:
            raise RecoveryDenied('TABLE_ACL_SCOPE_OBJECT_MISSING')
        catalog['tables'] = semantic_tables
        catalog['independent_security_planes'] = security_snapshot(c)
        if len([r for r in catalog['roles'] if r[0].startswith('ra4a_')]) != 8:
            raise RecoveryDenied('FROZEN_EIGHT_ROLE_CONTRACT')
        if len([r for r in catalog['policies'] if r[0] in ['ra4a', 'ra4a_private']]) != 10:
            raise RecoveryDenied('FROZEN_TEN_POLICY_CONTRACT')
        if not all(r[2] and r[3] for r in catalog['tables'] if r[:2] != ('ra4a_private', 'migrations')):
            raise RecoveryDenied('FORCE_RLS_REQUIRED')
        versions = c.execute('SELECT version,sha256 FROM ra4a_private.migrations ORDER BY version').fetchall()
    data = {'tables': tables, 'catalog_sha256': digest(encode(catalog)), 'migrations': versions,
            'p2a_schema_sha256': None, 'p2b1_schema_sha256': None}
    with environment.connect(dbname=dbname) as c:
        data['p2a_schema_sha256'] = p2a_support.schema_sha256(c)
        data['p2b1_schema_sha256'] = p2b1_support.schema_sha256(c)
    data['root_sha256'] = digest(encode(data))
    # Raw ACL representation is preserved as evidence, explicitly outside the
    # compared semantic catalog. Every effective entry remains in catalog_sha256.
    return data, {'comparison_catalog': catalog, 'raw_table_acl_evidence': raw_acl_evidence}


def public_catalog(evidence):
    import json
    value = json.loads(encode(evidence))
    for row in value['comparison_catalog']['functions']:
        row[2] = {'definition_sha256': digest(row[2].encode()), 'full_source_not_published': True}
    return value


def verify_sources(environment, dbname, graphs):
    verified = {}
    with environment.connect('p2b1_test_a_reviewer', dbname=dbname) as c:
        for case, expected in graphs.items():
            point = locator(expected)
            with c.transaction():
                rows = c.execute('SELECT * FROM ra4a_review_test.load_target(%s,%s,%s,%s,%s,%s)',
                    (point.tenant, point.ref_id, point.source_run, point.report, point.version, point.target_digest)).fetchall()
                if not rows:
                    raise RecoveryDenied('RESTORED_SOURCE_ABSENT')
                target, manifest = bytes(rows[0][0]), bytes(rows[0][1])
                artifacts = tuple(Artifact(kind, key, bytes(raw)) for _, _, kind, key, raw, _, _ in rows)
                candidate = ByteGraph(expected.ref_id, target, artifacts, manifest, expected.trust)
                verify(candidate, provenance=expected)
                import json
                t = json.loads(target)
                native = t['native_content_hash']
                draft = json.loads(next(a.raw for a in artifacts if a.kind == 'DRAFT'))
                if len(draft['issues']) != (0 if case == '200' else 1):
                    raise RecoveryDenied('ORIGINAL_FINDING_COUNT_CHANGED')
                if (case == '200') != (native is None):
                    raise RecoveryDenied('NATIVE_NULL_SEMANTICS_CHANGED')
                verified[case] = {'target_sha256': digest(target), 'manifest_sha256': digest(manifest),
                    'native_content_hash': native, 'objects': len(artifacts),
                    'kind': t['kind'], 'displayed_claims': len(t['claims']), 'findings': len(draft['issues'])}
    return verified
