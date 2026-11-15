"""Independent six-schema byte/catalog/permission snapshot, never a restore input."""
from psycopg import sql
from integration.ra4e.lab import digest, encode

SCHEMAS = ['ra4a', 'ra4a_private', 'ra4a_bytes', 'ra4a_review_test', 'b3_p0', 'ra4b_test']
ROLE_FILTER = "(starts_with(rolname,'ra4a_') OR starts_with(rolname,'ra4b_') OR starts_with(rolname,'p2a_') OR starts_with(rolname,'p2b1_'))"


def acl(c, raw, owner, kind):
    """SQL NULL means PG defaults; an explicit empty ACL means zero entries.

    Keep raw representations separately. Compare the full effective grant tuples,
    including grantor and grantability, without rewriting any restored ACL.
    """
    if raw is None:
        raw = c.execute('SELECT acldefault(%s::"char",%s::regrole)::text', (kind, owner)).fetchone()[0]
    if c.execute('SELECT cardinality(%s::aclitem[])', (raw,)).fetchone()[0] == 0:
        return []
    return c.execute("SELECT CASE WHEN x.grantee=0 THEN 'PUBLIC' ELSE pg_get_userbyid(x.grantee) END,pg_get_userbyid(x.grantor),privilege_type,is_grantable FROM aclexplode(%s::aclitem[]) x ORDER BY 1,2,3,4", (raw,)).fetchall()


def capture(env):
    raw_acls, tables, catalog = {}, {}, {}
    with env.connect() as c:
        found = [r[0] for r in c.execute('SELECT nspname FROM pg_namespace WHERE nspname=ANY(%s) ORDER BY 1', (SCHEMAS,))]
        if sorted(found) != sorted(SCHEMAS):
            raise AssertionError('MISSING_REQUIRED_SCHEMA')
        relations = c.execute("SELECT n.nspname,t.relname,t.relkind,pg_get_userbyid(t.relowner),t.relacl::text,t.relrowsecurity,t.relforcerowsecurity,t.relpersistence,t.relreplident FROM pg_class t JOIN pg_namespace n ON n.oid=t.relnamespace WHERE n.nspname=ANY(%s) AND t.relkind IN ('r','p','S','v','m') ORDER BY 1,2", (SCHEMAS,)).fetchall()
        catalog['relations'] = []
        for schema, name, kind, owner, raw, *flags in relations:
            key = schema + '.' + name
            raw_acls[key] = raw
            catalog['relations'].append((schema, name, kind, owner, acl(c, raw, owner, 'S' if kind == 'S' else 'r'), *flags))
            if kind in ('r', 'p'):
                rows = c.execute(sql.SQL("SELECT coalesce(jsonb_agg(to_jsonb(x) ORDER BY to_jsonb(x)::text),'[]'::jsonb) FROM {}.{} x").format(sql.Identifier(schema), sql.Identifier(name))).fetchone()[0]
                tables[key] = {'count': len(rows), 'sha256': digest(encode(rows)), 'rows': rows,
                               'coverage': 'SEEDED' if rows else 'ZERO/NOT_TESTED'}
            elif kind == 'S':
                tables[key] = {'sequence': c.execute(sql.SQL('SELECT last_value,is_called FROM {}.{}').format(sql.Identifier(schema), sql.Identifier(name))).fetchone()}
        queries = {
            'columns': "SELECT n.nspname,t.relname,a.attnum,a.attname,format_type(a.atttypid,a.atttypmod),a.attnotnull,a.attidentity,a.attgenerated,a.attstorage,a.attcompression,pg_get_expr(d.adbin,d.adrelid),co.collname FROM pg_attribute a JOIN pg_class t ON t.oid=a.attrelid JOIN pg_namespace n ON n.oid=t.relnamespace LEFT JOIN pg_attrdef d ON d.adrelid=t.oid AND d.adnum=a.attnum LEFT JOIN pg_collation co ON co.oid=a.attcollation WHERE n.nspname=ANY(%s) AND a.attnum>0 AND NOT a.attisdropped ORDER BY 1,2,3",
            'constraints': "SELECT n.nspname,t.relname,p.conname,p.contype,p.condeferrable,p.condeferred,p.convalidated,pg_get_constraintdef(p.oid) FROM pg_constraint p JOIN pg_class t ON t.oid=p.conrelid JOIN pg_namespace n ON n.oid=t.relnamespace WHERE n.nspname=ANY(%s) ORDER BY 1,2,3",
            'indexes': "SELECT schemaname,tablename,indexname,indexdef FROM pg_indexes WHERE schemaname=ANY(%s) ORDER BY 1,2,3",
            'policies': "SELECT schemaname,tablename,policyname,permissive,roles,cmd,qual,with_check FROM pg_policies WHERE schemaname=ANY(%s) ORDER BY 1,2,3",
            'triggers': "SELECT n.nspname,t.relname,g.tgname,g.tgenabled,pg_get_triggerdef(g.oid) FROM pg_trigger g JOIN pg_class t ON t.oid=g.tgrelid JOIN pg_namespace n ON n.oid=t.relnamespace WHERE n.nspname=ANY(%s) AND NOT g.tgisinternal ORDER BY 1,2,3",
            'sequences': "SELECT schemaname,sequencename,sequenceowner,data_type::text,start_value,min_value,max_value,increment_by,cycle,cache_size,last_value FROM pg_sequences WHERE schemaname=ANY(%s) ORDER BY 1,2",
            'default_acls': "SELECT pg_get_userbyid(d.defaclrole),coalesce(n.nspname,''),d.defaclobjtype,d.defaclacl::text FROM pg_default_acl d LEFT JOIN pg_namespace n ON n.oid=d.defaclnamespace WHERE n.nspname=ANY(%s) OR d.defaclnamespace=0 ORDER BY 1,2,3",
        }
        for name, query in queries.items():
            catalog[name] = c.execute(query, (SCHEMAS,)).fetchall()
        catalog['roles'] = c.execute('SELECT rolname,rolsuper,rolinherit,rolcreaterole,rolcreatedb,rolcanlogin,rolreplication,rolbypassrls,rolconnlimit,rolvaliduntil,rolconfig FROM pg_roles WHERE ' + ROLE_FILTER + ' ORDER BY 1').fetchall()
        catalog['memberships'] = c.execute("SELECT pg_get_userbyid(a.roleid),pg_get_userbyid(a.member),pg_get_userbyid(a.grantor),a.admin_option,a.inherit_option,a.set_option FROM pg_auth_members a WHERE a.member IN (SELECT oid FROM pg_roles WHERE " + ROLE_FILTER + ') ORDER BY 1,2,3').fetchall()
        catalog['schemas'] = []
        for name, owner, raw in c.execute("SELECT nspname,pg_get_userbyid(nspowner),nspacl::text FROM pg_namespace WHERE nspname=ANY(%s) OR nspname='public' ORDER BY 1", (SCHEMAS,)).fetchall():
            raw_acls['SCHEMA:' + name] = raw
            catalog['schemas'].append((name, owner, acl(c, raw, owner, 'n')))
        catalog['functions'] = []
        for schema, signature, body, owner, raw, *attributes in c.execute("SELECT n.nspname,p.oid::regprocedure::text,pg_get_functiondef(p.oid),pg_get_userbyid(p.proowner),p.proacl::text,p.prosecdef,p.proconfig,p.provolatile,p.proparallel,p.proleakproof,p.proisstrict FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname=ANY(%s) ORDER BY 1,2", (SCHEMAS,)).fetchall():
            raw_acls['FUNCTION:' + signature] = raw
            catalog['functions'].append((schema, signature, body, owner, acl(c, raw, owner, 'f'), *attributes))
        catalog['column_acls'] = c.execute("SELECT n.nspname,t.relname,a.attname,a.attacl::text FROM pg_attribute a JOIN pg_class t ON t.oid=a.attrelid JOIN pg_namespace n ON n.oid=t.relnamespace WHERE n.nspname=ANY(%s) AND a.attnum>0 AND NOT a.attisdropped ORDER BY 1,2,3", (SCHEMAS,)).fetchall()
        catalog['effective_table_privileges'] = c.execute("SELECT r.rolname,n.nspname,t.relname,p,has_table_privilege(r.oid,t.oid,p) FROM pg_roles r CROSS JOIN pg_class t JOIN pg_namespace n ON n.oid=t.relnamespace CROSS JOIN unnest(ARRAY['SELECT','INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER']) p WHERE n.nspname=ANY(%s) AND t.relkind IN ('r','p') AND " + ROLE_FILTER + ' ORDER BY 1,2,3,4', (SCHEMAS,)).fetchall()
        catalog['effective_schema_privileges'] = c.execute("SELECT r.rolname,n.nspname,has_schema_privilege(r.oid,n.oid,'USAGE'),has_schema_privilege(r.oid,n.oid,'CREATE') FROM pg_roles r CROSS JOIN pg_namespace n WHERE (n.nspname=ANY(%s) OR n.nspname='public') AND " + ROLE_FILTER + ' ORDER BY 1,2', (SCHEMAS,)).fetchall()
        catalog['effective_column_privileges'] = c.execute("SELECT r.rolname,n.nspname,t.relname,a.attname,p,has_column_privilege(r.oid,t.oid,a.attnum,p) FROM pg_roles r CROSS JOIN pg_class t JOIN pg_namespace n ON n.oid=t.relnamespace JOIN pg_attribute a ON a.attrelid=t.oid CROSS JOIN unnest(ARRAY['SELECT','INSERT','UPDATE','REFERENCES']) p WHERE n.nspname=ANY(%s) AND t.relkind IN ('r','p') AND a.attnum>0 AND NOT a.attisdropped AND " + ROLE_FILTER + ' ORDER BY 1,2,3,4,5', (SCHEMAS,)).fetchall()
        owner, raw, *attrs = c.execute("SELECT pg_get_userbyid(datdba),datacl::text,pg_encoding_to_char(encoding),datcollate,datctype,datallowconn,datconnlimit FROM pg_database WHERE datname=current_database()").fetchone()
        raw_acls['DATABASE'] = raw
        catalog['database'] = (owner, acl(c, raw, owner, 'd'), *attrs)
    data = {key: {k: v for k, v in value.items() if k != 'rows'} for key, value in tables.items()}
    return {'root': digest(encode({'data': data, 'catalog': catalog})),
            'data_root': digest(encode(data)), 'catalog_root': digest(encode(catalog)),
            'tables': tables, 'catalog': catalog, 'raw_acls': raw_acls}


def evidence(snapshot):
    return {k: snapshot[k] for k in ('root', 'data_root', 'catalog_root')} | {
        'tables': {name: {k: v for k, v in row.items() if k != 'rows'}
                   for name, row in snapshot['tables'].items()},
        'job_state_counts': {state: sum(row['state'] == state for row in snapshot['tables']['ra4a.jobs']['rows'])
                             for state in ('PENDING', 'LEASED', 'TEST_ONLY_DONE', 'DEAD_LETTER')},
        'dead_letter_coverage': ('SEEDED' if any(row['state'] == 'DEAD_LETTER' for row in snapshot['tables']['ra4a.jobs']['rows'])
                                 else 'ZERO/NOT_TESTED'),
        'schemas': SCHEMAS, 'raw_acls_sha256': digest(encode(snapshot['raw_acls']))}


def compare(expected, actual):
    if expected['root'] == actual['root']:
        return {'equal': True, 'raw_acl_representation_equal': expected['raw_acls'] == actual['raw_acls']}
    differences = {'tables': [key for key in expected['tables'] if expected['tables'][key] != actual['tables'].get(key)],
                   'catalog': [key for key in expected['catalog'] if expected['catalog'][key] != actual['catalog'].get(key)]}
    raise AssertionError('SIX_SCHEMA_DIFFERENCE:' + repr(differences))
