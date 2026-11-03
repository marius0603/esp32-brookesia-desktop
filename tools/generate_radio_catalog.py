"""Generate the native whitelist and interpreted UI catalog from one source."""
import json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
 doc=json.loads((ROOT/'brookesia-apps/radio/stations.json').read_text(encoding='utf-8'))
 stations=doc['stations'];assert len({s['id'] for s in stations})==len(stations)
 quote=lambda s:json.dumps(s,ensure_ascii=True)
 header='#pragma once\nnamespace radio_catalog {\nstruct Station {const char *id,*url,*format;};\ninline constexpr Station stations[]={\n'
 for s in stations:
  assert s['stream_url'].startswith('https://')
  format=s.get('stream_format','hls_ts' if '.m3u8' in s['stream_url'] else 'mp3' if 'mp3' in s['verification']['audio'].lower() else 'aac')
  assert format in ('hls_ts','mp3','aac')
  header+=' {'+quote(s['id'])+','+quote(s['stream_url'])+','+quote(format)+'},\n'
  if s.get('previous_stream_url'):
   assert s['previous_stream_url'].startswith('https://')
   assert all(x['id']!=s['id']+'-legacy' for x in stations)
   header+=' {'+quote(s['id']+'-legacy')+','+quote(s['previous_stream_url'])+','+quote(format)+'},\n'
 header+='};\n}\n'
 path=ROOT/'platform/super_s3_216/main/modules/radio/stations.hpp';path.write_text(header,encoding='utf-8')
 app=ROOT/'brookesia-apps/radio/src/app';app.mkdir(parents=True,exist_ok=True)
 catalog=[{k:s[k] for k in ('id','name','display_name','group','sub','symbol')} for s in stations]
 (app/'catalog.json').write_text(json.dumps(catalog,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
 preview=ROOT/'brookesia-apps/radio/design/preview.html'
 text=preview.read_text(encoding='utf-8')
 text=re.sub(r'(<script type="application/json" id="radio-catalog">).*?(</script>)',lambda m:m[1]+json.dumps(doc,ensure_ascii=False,separators=(',',':'))+m[2],text,flags=re.S)
 preview.write_text(text,encoding='utf-8')
 print('Generated',len(stations),'station whitelist entries')
if __name__=='__main__':main()
