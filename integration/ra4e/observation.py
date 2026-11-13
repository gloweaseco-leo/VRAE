"""Read-consistent diagnostic evidence only; never changes the restoration oracle."""
from datetime import datetime, timezone

from psycopg import sql

from .lab import encode, digest
from .manifest import SCHEMAS


def snapshot(environment, dbname, private, output, label):
    objects, debug = {}, {}

    def add(path, value, kind, *, expose=False, relevance='semantic'):
        debug[path] = value
        row = {'sha256': digest(encode(value)), 'value_class': kind, 'relevance': relevance}
        if expose:
            row['value'] = value
        objects[path] = row

    with environment.connect(dbname=dbname) as c:
        c.execute('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY')
        state = c.execute("SELECT txid_current_snapshot()::text,transaction_timestamp()::text,clock_timestamp()::text,current_database(),current_setting('server_version_num')").fetchone()
        relations = c.execute("SELECT c.oid,n.nspname,c.relname,c.relkind,c.relrowsecurity,c.relforcerowsecurity,pg_get_userbyid(c.relowner),c.relacl::text FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=ANY(%s) ORDER BY 2,3", (SCHEMAS,)).fetchall()
        present = {(r[1], r[2]) for r in relations}
        for schema, name in [('ra4a', n) for n in ['requests', 'runs', 'jobs', 'audit', 'outbox']] + [('ra4a_bytes', n) for n in ['graphs', 'objects']] + [('ra4a_review_test', n) for n in ['proposals', 'audit', 'outbox']] + [('ra4a_private', n) for n in ['migrations', 'principals', 'assignments']]:
            add('presence/' + schema + '.' + name, (schema, name) in present, 'catalog_enumerated_presence', expose=True)
        for oid, schema, name, kind, rls, force, owner, acl in relations:
            key = schema + '.' + name
            base = 'relations/' + key
            add(base + '/oid', oid, 'physical_oid', expose=True, relevance='environment_local_not_an_oracle_exclusion')
            for field, value in [('kind', kind), ('rls', rls), ('force_rls', force), ('owner', owner), ('acl_raw', acl)]:
                add(base + '/' + field, value, 'relation_' + field, expose=True)
            grants = c.execute("SELECT CASE WHEN a.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee)::text END,pg_get_userbyid(a.grantor),a.privilege_type,a.is_grantable FROM pg_class c CROSS JOIN LATERAL aclexplode(coalesce(c.relacl,acldefault(CASE WHEN c.relkind='S' THEN 'S'::\"char\" ELSE 'r'::\"char\" END,c.relowner))) a WHERE c.oid=%s ORDER BY 1,2,3,4", (oid,)).fetchall()
            add(base + '/acl_entries_observed', grants, 'ordered_acl_semantics_observation_only', expose=True)
            if kind == 'S':
                seq = c.execute(sql.SQL('SELECT last_value,is_called FROM {}.{}').format(sql.Identifier(schema), sql.Identifier(name))).fetchone()
                add(base + '/sequence_state', seq, 'last_value_and_is_called', expose=True)
            if kind not in ['r', 'p']:
                continue
            columns = c.execute("SELECT a.attnum,a.attname,format_type(a.atttypid,a.atttypmod),a.attnotnull,a.attidentity,a.attgenerated,pg_get_expr(d.adbin,d.adrelid) FROM pg_attribute a LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum WHERE a.attrelid=%s AND a.attnum>0 AND NOT a.attisdropped ORDER BY a.attnum", (oid,)).fetchall()
            for column in columns:
                add(base + '/columns/' + column[1], column, 'column_type_default_identity', expose=True)
            primary = c.execute("SELECT a.attname FROM pg_index i CROSS JOIN LATERAL unnest(i.indkey) WITH ORDINALITY k(attnum,ord) JOIN pg_attribute a ON a.attrelid=i.indrelid AND a.attnum=k.attnum WHERE i.indrelid=%s AND i.indisprimary ORDER BY k.ord", (oid,)).fetchall()
            keys = [r[0] for r in primary]
            add(base + '/primary_key_columns', keys, 'catalog_primary_key', expose=True)
            values = c.execute(sql.SQL("SELECT to_jsonb(x) FROM {}.{} x ORDER BY to_jsonb(x)::text COLLATE \"C\"").format(sql.Identifier(schema), sql.Identifier(name))).fetchall()
            add(base + '/count', len(values), 'row_count', expose=True)
            row_hashes = []
            byte_columns = {r[1] for r in columns if r[2] == 'bytea'}
            for (value,) in values:
                key_value = {k:value[k] for k in keys} if keys else value
                row_key = digest(encode(key_value))
                path = base + '/rows/' + row_key
                row_hashes.append((row_key, digest(encode(value))))
                add(path, value, 'canonical_row_hash_no_public_values')
                for column, item in value.items():
                    add(path + '/' + column, item, 'column_value_hash_no_public_values')
                    if column in byte_columns:
                        raw = bytes.fromhex(item[2:]) if item is not None else None
                        add(path + '/' + column + '/original_bytes', None if raw is None else {'sha256': digest(raw), 'length': len(raw)}, 'actual_bytea_digest_and_length', expose=True)
            add(base + '/per_key_sorted_row_hashes', sorted(row_hashes), 'canonical_key_sorted_rows', expose=True)
        catalogs = {
            'roles': ("SELECT rolname,oid,rolsuper,rolinherit,rolcreaterole,rolcreatedb,rolcanlogin,rolreplication,rolbypassrls FROM pg_roles WHERE rolname LIKE 'ra4a_%' OR rolname LIKE 'p2a_%' OR rolname LIKE 'p2b1_%' ORDER BY rolname", None),
            'memberships': ("SELECT r.rolname,m.rolname,pg_get_userbyid(a.grantor),a.admin_option,a.inherit_option,a.set_option FROM pg_auth_members a JOIN pg_roles r ON r.oid=a.roleid JOIN pg_roles m ON m.oid=a.member WHERE r.rolname LIKE 'ra4a_%' OR r.rolname LIKE 'p2a_%' OR r.rolname LIKE 'p2b1_%' ORDER BY 1,2,3", None),
            'policies': ("SELECT schemaname,tablename,policyname,roles,cmd,qual,with_check FROM pg_policies WHERE schemaname=ANY(%s) ORDER BY 1,2,3", (SCHEMAS,)),
            'constraints': ("SELECT n.nspname,c.relname,p.conname,pg_get_constraintdef(p.oid),p.convalidated,p.condeferrable,p.condeferred FROM pg_constraint p JOIN pg_class c ON c.oid=p.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=ANY(%s) ORDER BY 1,2,3", (SCHEMAS,)),
            'indexes': ("SELECT schemaname,tablename,indexname,indexdef FROM pg_indexes WHERE schemaname=ANY(%s) ORDER BY 1,2,3", (SCHEMAS,)),
            'triggers': ("SELECT n.nspname,c.relname,t.tgname,pg_get_triggerdef(t.oid),t.tgenabled,t.tgdeferrable,t.tginitdeferred FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE NOT t.tgisinternal AND n.nspname=ANY(%s) ORDER BY 1,2,3", (SCHEMAS,)),
            'sequences': ("SELECT schemaname,sequencename,sequenceowner,data_type::text,start_value,min_value,max_value,increment_by,cycle,cache_size,last_value FROM pg_sequences WHERE schemaname=ANY(%s) ORDER BY 1,2", (SCHEMAS,)),
        }
        for name, (query, params) in catalogs.items():
            rows = c.execute(query, params).fetchall()
            add('catalog/' + name + '/count', len(rows), 'catalog_row_count', expose=True)
            for row in rows:
                identity = '/'.join(str(x) for x in row[:1 if name == 'roles' else 3 if name in ['policies', 'constraints', 'indexes', 'triggers'] else 2])
                if name == 'roles':
                    add('catalog/' + name + '/' + identity + '/oid', row[1], 'physical_oid', expose=True, relevance='environment_local_not_an_oracle_exclusion')
                    row = (row[0], *row[2:])
                add('catalog/' + name + '/' + identity, row, name, expose=name not in ['triggers', 'indexes', 'policies', 'constraints'])
        functions = c.execute("SELECT p.oid,n.nspname,p.proname,pg_get_function_identity_arguments(p.oid),pg_get_userbyid(p.proowner),p.prosecdef,p.proconfig,p.proacl::text,p.prosrc,pg_get_functiondef(p.oid) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname=ANY(%s) AND p.prokind IN ('f','p') ORDER BY 2,3,4", (SCHEMAS,)).fetchall()
        for oid, schema, name, args, owner, definer, config, acl, body, definition in functions:
            path = 'functions/' + schema + '.' + name + '(' + args + ')'
            for field, value in [('owner', owner), ('security_definer', definer), ('search_path_config', config), ('acl_raw', acl), ('body', body), ('definition', definition)]:
                add(path + '/' + field, value, 'function_' + field, expose=field not in ['body', 'definition'])
            grants = c.execute("SELECT CASE WHEN a.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(a.grantee)::text END,pg_get_userbyid(a.grantor),a.privilege_type,a.is_grantable FROM pg_proc p CROSS JOIN LATERAL aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) a WHERE p.oid=%s ORDER BY 1,2,3,4", (oid,)).fetchall()
            add(path + '/acl_entries_observed', grants, 'ordered_acl_semantics_observation_only', expose=True)
        frozen_roles = c.execute("SELECT count(*) FROM pg_roles WHERE rolname LIKE 'ra4a_%'").fetchone()[0]
        if ('ra4a_private', 'migrations') in present:
            for version, sha256 in c.execute('SELECT version,sha256 FROM ra4a_private.migrations ORDER BY version').fetchall():
                add('migrations/' + str(version), {'version': version, 'sha256': sha256}, 'actual_migration_version_and_digest', expose=True)
        frozen_policies = c.execute("SELECT count(*) FROM pg_policies WHERE schemaname IN ('ra4a','ra4a_private')").fetchone()[0]
        add('invariants/ra4a_role_count', frozen_roles, 'frozen_count', expose=True)
        add('invariants/original_policy_count', frozen_policies, 'frozen_count', expose=True)
        c.execute('ROLLBACK')
    metadata = {'snapshot': state[0], 'transaction_timestamp': state[1], 'clock_timestamp': state[2],
        'database_name': state[3], 'server_version_num': state[4], 'isolation': 'REPEATABLE READ READ ONLY',
        'captured_at_utc': datetime.now(timezone.utc).isoformat(), 'credentials_and_password_hashes_queried': False}
    public = {'metadata': metadata, 'objects': objects, 'objects_root_sha256': digest(encode(objects))}
    private.joinpath(label + '-private-debug.json').write_bytes(encode({'metadata': metadata, 'values': debug}))
    output.joinpath(label + '-snapshot.json').write_bytes(encode(public))
    return public


def diff(expected, actual, output, label):
    rows = []
    for path in sorted(set(expected['objects']) | set(actual['objects'])):
        left, right = expected['objects'].get(path), actual['objects'].get(path)
        if left == right:
            continue
        row = {'object_path': path, 'source': left, 'target': right, 'equal': False,
               'classification': 'MISSING_OBJECT' if left is None or right is None else 'UNCLASSIFIED_OBSERVED_DIFFERENCE'}
        if left and right and left['value_class'] == 'physical_oid':
            row['classification'] = 'PHYSICAL_OID_OBSERVED_NOT_USED_TO_RELAX_GATE'
        if path.endswith('/acl_raw'):
            sibling = path.removesuffix('acl_raw') + 'acl_entries_observed'
            a, b = expected['objects'].get(sibling), actual['objects'].get(sibling)
            if a and b and a['sha256'] == b['sha256']:
                row['classification'] = 'RAW_ACL_DIFF_OBSERVED_ENTRIES_EQUAL_CANONICALIZATION_PROPOSAL_ONLY'
        rows.append(row)
    result = {'label': label, 'source_root': expected['objects_root_sha256'], 'target_root': actual['objects_root_sha256'],
              'different_objects': len(rows), 'differences': rows, 'normalization_applied_to_oracle': False}
    output.joinpath(label + '-diff.json').write_bytes(encode(result))
    return result
