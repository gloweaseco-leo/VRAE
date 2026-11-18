"""Add accepted C2 read-only source routes to the existing C3 business port."""
from integration.s2_buyer_workbench.workbench import SourceBinding, Workbench
from vrae.industry.l2_v1.pack import IndustryPins, load_s2
from vrae.l2_ops.sources import OperationsDenied


def bind(business, report_id):
    app = business.app
    manager = app.native_tasks
    if manager is None or manager.active is None or manager.active["report_id"] != report_id:
        raise OperationsDenied("S2_CURRENT_NATIVE_TASK_REQUIRED")
    source = manager.active["source"]
    if (report_id not in business.bindings or app.deep.ledgers[report_id].source is not source
            or business.bindings[report_id].bundle is not manager.bundle):
        raise OperationsDenied("S2_EXISTING_REPORT_PORT_REQUIRED")
    # Original signed task authority is checked around both construction and every read.
    with manager.access() as (evidence, _):
        tenant = manager.identity["tenant_id"]
        task = manager.active["task"]
        scope = {"tenant_id": tenant, "run_id": task.run_id,
                 "policy_id": evidence.pack.document["policy_id"],
                 "policy_version": evidence.pack.document["policy_version"]}
        config = load_s2(tenant_id=tenant)
        held = IndustryPins(config["industry_ref"], tenant)
        binding = SourceBinding(source, evidence.pack, trusted_scope=scope, industry_pins=held)
        component = Workbench(app.deep, binding)
    # Do not call the component installer or replace native_business/native_tasks.
    business.source_views[report_id] = component
    return component


def route(business, path):
    for rid, component in business.source_views.items():
        match = component.route(path)
        if match is not None and match[1] == rid:
            return rid
    return None


def handle(business, method, path, headers, raw):
    rid = route(business, path)
    if rid is None:
        raise OperationsDenied("S2_CURRENT_SOURCE_ROUTE_REQUIRED")
    try:
        with business.app.native_tasks.access():
            reply = business.source_views[rid].handle(method, path, headers, raw)
            business.app.native_tasks.audit()
            return reply
    except Exception:
        return business.app.deep.reply("未提供来源候选",
            '<p data-code="S2_NATIVE_SOURCE_DENIED">当前任务签名或来源绑定已失效，请重新认证。</p>', 403)


def proof(business, rid):
    component = business.source_views.get(rid)
    if component is None:
        return None
    binding = component.binding
    return {"authority": "READ_ONLY_CANDIDATE_NOT_RX_OR_GUARD",
            "pack_ref": binding.pack.ref, "scope": binding.scope,
            "projection_ref": binding.expected_ref, "industry_ref": binding.pins.industry_ref}
