"""Conservative runtime ceiling for catalog and matching channel overrides."""
import fnmatch
import math
import urllib.parse
from server_storage import Error

def price_bounds(api,gid,model):
    group=api('/api/v1/admin/groups/'+str(gid))
    if group.get('status','active')!='active':raise Error(503,'官方分组暂时不可用。')
    catalog=api('/api/v1/admin/channels/model-pricing?model='+urllib.parse.quote(model))
    if not catalog.get('found'):raise Error(503,'模型价格缺失。')
    channels=api('/api/v1/admin/channels?page=1&page_size=100')
    items=channels.get('items',[]) if isinstance(channels,dict) else channels
    if isinstance(channels,dict) and channels.get('total',0)>len(items):raise Error(503,'价格列表需要重新核验。')
    prices=[catalog]
    for channel in items:
        if gid not in (channel.get('group_ids') or []) or channel.get('status')!='active':continue
        names={model.lower()}
        for mapping in (channel.get('model_mapping') or {}).values():
            if isinstance(mapping,dict):
                names.update(str(v).lower() for k,v in mapping.items() if fnmatch.fnmatchcase(model.lower(),k.lower()))
        entries=list(channel.get('model_pricing') or [])
        for rule in channel.get('account_stats_pricing_rules') or []:entries.extend(rule.get('pricing') or [])
        prices.extend(p for p in entries if any(fnmatch.fnmatchcase(name,str(pattern).lower()) for name in names for pattern in p.get('models',[])))
    inp=out=0
    for price in prices:
        if price.get('billing_mode','token')!='token' or price.get('per_request_price'):raise Error(503,'该模型计费方式需要核验。')
        factor=max([1,float(price.get('max_reasoning_effort_multiplier') or 1),float(price.get('fast_multiplier') or 1),float(price.get('flex_multiplier') or 1)]+[float(v) for v in (price.get('reasoning_effort_multipliers') or {}).values()])
        factor*=max([1]+[float(p.get('multiplier') or 1) for p in (price.get('time_pricing') or {}).get('periods',[])])
        for entry in [price]+list(price.get('intervals') or []):
            inp=max(inp,max(float(entry.get(k) or 0) for k in ('input_price','cache_read_price','cache_write_price','cache_write_1h_price'))*factor)
            out=max(out,float(entry.get('output_price') or 0)*factor)
    multiplier=float(group.get('rate_multiplier',1))*1e6
    inp*=multiplier;out*=multiplier
    if not math.isfinite(inp+out) or inp<0 or out<=0:raise Error(503,'模型价格无效。')
    return inp,out
