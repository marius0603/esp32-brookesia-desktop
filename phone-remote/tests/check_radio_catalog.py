"""Check that BLE exposes the same station metadata and fits one GATT reply."""
import json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
catalog=json.loads((ROOT/'brookesia-apps/radio/src/app/catalog.json').read_text(encoding='utf-8'))
header=(ROOT/'platform/super_s3_216/main/modules/phone_provisioning/radio_catalog.hpp').read_text(encoding='utf-8')
rows=[json.loads('['+row+']') for row in re.findall(r'^ \{(.+)\},$',header,re.M)]
assert rows==[[s[k] for k in ('id','display_name','group','sub')] for s in catalog]
native=(ROOT/'platform/super_s3_216/main/modules/radio/stations.hpp').read_text(encoding='utf-8')
for station in catalog:assert '"'+station['id']+'"' in native
sizes=[]
for page in range((len(catalog)+1)//2):
 items=[dict(zip(('id','name','group','sub'),row)) for row in rows[page*2:page*2+2]]
 data={'ok':True,'items':items,'more':page*2+2<len(rows),'total':len(rows)}
 size=len(json.dumps(data,ensure_ascii=False,separators=(',',':')).encode('utf-8'));assert size<=480,size;sizes.append(size)
print('BLE catalog matches all',len(rows),'device stations; reply sizes:',sizes)
