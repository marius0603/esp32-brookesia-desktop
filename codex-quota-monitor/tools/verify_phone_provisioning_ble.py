"""Test the real BLE protocol without logging pairing codes or network credentials."""
import argparse,asyncio,hashlib,json,sys,time
from pathlib import Path
from bleak import BleakClient,BleakScanner
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey,X25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat
from cryptography.hazmat.primitives.ciphers import Cipher,algorithms,modes
from deploy_audiobook_sleep import StoryClient
ROOT=Path(__file__).resolve().parents[2]
SERVICE='1775244d-6b43-439b-877c-060f2d9bed07'
ENDPOINTS={n:f'1775ff{i:02x}-6b43-439b-877c-060f2d9bed07' for n,i in [('session',0x51),('config',0x52),('version',0x53),('scan',0x54)]}
def varint(n):
 out=bytearray()
 while n>127:out.append((n&127)|128);n>>=7
 out.append(n);return bytes(out)
def number(field,n):return varint(field*8)+varint(n)
def binary(field,data):return varint(field*8+2)+varint(len(data))+data
def fields(data):
 result={};at=0
 def read():
  nonlocal at
  n=shift=0
  while at<len(data) and shift<=63:
   b=data[at];at+=1;n|=(b&127)<<shift
   if not b&128:return n
   shift+=7
  raise ValueError('Invalid protobuf varint')
 while at<len(data):
  key=read();kind=key&7
  if kind==0:value=read()
  elif kind==2:
   size=read();assert size<=len(data)-at;value=data[at:at+size];at+=size
  else:raise ValueError('Unexpected wire type')
  result.setdefault(key>>3,[]).append(value)
 return result
def one(values,key,default=0):return values.get(key,[default])[0]
async def exchange(client,name,data):
 await client.write_gatt_char(ENDPOINTS[name],data,response=True)
 await asyncio.sleep(.04)
 return bytes(await client.read_gatt_char(ENDPOINTS[name]))
class Security:
 def __init__(self,pop,session_module):self.pop=pop;self.proto=session_module;self.cipher=None
 async def start(self,client):
  key=X25519PrivateKey.generate();public=key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)
  request=self.proto.SessionData();request.sec_ver=1;request.sec1.sc0.client_pubkey=public
  response=self.proto.SessionData();response.ParseFromString(await exchange(client,'session',request.SerializeToString()))
  assert response.sec_ver==1 and len(response.sec1.sr0.device_pubkey)==32
  peer=response.sec1.sr0.device_pubkey;shared=key.exchange(X25519PublicKey.from_public_bytes(peer))
  digest=hashlib.sha256(self.pop.encode('ascii')).digest();shared=bytes(a^b for a,b in zip(shared,digest))
  self.cipher=Cipher(algorithms.AES(shared),modes.CTR(response.sec1.sr0.device_random)).encryptor()
  request=self.proto.SessionData();request.sec_ver=1;request.sec1.msg=2;request.sec1.sc1.client_verify_data=self.cipher.update(peer)
  response=self.proto.SessionData();response.ParseFromString(await exchange(client,'session',request.SerializeToString()))
  assert len(response.sec1.sr1.device_verify_data)==32,'Pairing proof rejected'
  assert self.cipher.update(response.sec1.sr1.device_verify_data)==public,'Pairing proof rejected'
 async def request(self,client,name,payload):
  return fields(self.cipher.update(await exchange(client,name,self.cipher.update(payload))))
async def exercise(device,pop,session_module,credentials):
 report={}
 async with BleakClient(device,timeout=25) as client:
  version=json.loads(await exchange(client,'version',b'ESP'))
  assert version['prov']['sec_ver']==1;report['security_version']=1
  rejected=False
  try:await Security('definitely-wrong',session_module).start(client)
  except Exception:rejected=True
  assert rejected,'Incorrect pairing code accepted'
  report['wrong_pairing_code_rejected']=True
 await asyncio.sleep(.8)
 async with BleakClient(device,timeout=25) as client:
  secure=Security(pop,session_module);await secure.start(client);report['authenticated']=True
  response=await secure.request(client,'scan',binary(10,number(4,120)))
  assert one(response,1)==1 and one(response,2)==0
  end=time.monotonic()+15
  while True:
   response=await secure.request(client,'scan',number(1,2)+binary(12,b''));assert one(response,1)==3 and one(response,2)==0
   scan=fields(one(response,13,b''));count=one(scan,2)
   if one(scan,1):break
   assert time.monotonic()<end,'Wi-Fi scan timed out';await asyncio.sleep(.4)
  assert 0<=count<=16;report['scanned_network_count']=count
  if count:
   response=await secure.request(client,'scan',number(1,4)+binary(14,number(2,count)))
   assert one(response,1)==5 and one(response,2)==0
   assert len(fields(one(response,15,b'')).get(1,[]))==count
  invalid=number(1,2)+binary(12,binary(1,b'validation-test')+binary(2,b'bad'))
  response=await secure.request(client,'config',invalid);assert one(response,1)==3
  assert one(fields(one(response,13,b'')),1)!=0,'Short Wi-Fi password accepted'
  report['invalid_password_rejected']=True
  if credentials:
   ssid,password=credentials
   payload=number(1,2)+binary(12,binary(1,ssid.encode('utf-8'))+binary(2,password.encode('utf-8')))
   response=await secure.request(client,'config',payload);assert one(fields(one(response,13,b'')),1)==0
   response=await secure.request(client,'config',number(1,4)+binary(14,b''));assert one(fields(one(response,15,b'')),1)==0
   deadline=time.monotonic()+45
   while True:
    response=await secure.request(client,'config',binary(10,b''));assert one(response,1)==1
    state=fields(one(response,11,b''));assert one(state,1)==0
    if one(state,2)==0:break
    assert one(state,2)==1 and time.monotonic()<deadline,'Wi-Fi connect did not complete'
    await asyncio.sleep(.5)
   report['existing_network_reconnected']=True
 return report
def main():
 p=argparse.ArgumentParser();p.add_argument('--port',required=True);p.add_argument('--idf',type=Path,required=True);p.add_argument('--apply-existing',action='store_true');a=p.parse_args()
 sys.path.insert(0,str(a.idf/'components/protocomm/python'));import session_pb2
 with StoryClient(a.port,timeout=30) as c:
  c.hello()
  def f(s,n,args=None):return c.call(s,n,args or {})['result']
  f('PhoneProvisioning','Start');deadline=time.monotonic()+15
  while True:
   state=f('PhoneProvisioning','GetSetup')
   if state['active']:break
   assert time.monotonic()<deadline,state.get('status');time.sleep(.2)
  name=state['device_name'];pop=state.pop('pop');credentials=None
  if a.apply_existing:
   saved=f('Wifi','GetConnectAp');credentials=(saved['ssid'],saved.get('password',''))
 async def run():
  device=await BleakScanner.find_device_by_filter(lambda d,ad:ad.local_name==name,timeout=15)
  assert device,'Provisioning device not discovered over BLE'
  return await exercise(device,pop,session_pb2,credentials)
 try:report=asyncio.run(run())
 finally:
  with StoryClient(a.port,timeout=30) as c:
   c.hello();c.call('PhoneProvisioning','Stop',{})
  pop=None;credentials=None
 report['passed']=True
 (ROOT/'codex-quota-monitor/runtime/phone-provisioning-ble-verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(report))
if __name__=='__main__':main()
