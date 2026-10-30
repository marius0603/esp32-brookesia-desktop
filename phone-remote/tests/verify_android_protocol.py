"""Cross-check the exact APK Security1 source against an independent Python peer."""
import argparse,base64,hashlib,json,os,subprocess,sys
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey,X25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat
from cryptography.hazmat.primitives.ciphers import Cipher,algorithms,modes
ROOT=Path(__file__).resolve().parents[2]
def main():
 p=argparse.ArgumentParser();p.add_argument('--tools',type=Path,required=True);p.add_argument('--idf',type=Path,required=True);p.add_argument('--work',type=Path,required=True);a=p.parse_args();t=json.loads(a.tools.read_text());a.work.mkdir(parents=True,exist_ok=True)
 sys.path.insert(0,str(a.idf/'components/protocomm/python'));import session_pb2
 subprocess.run([t['javac'],'-encoding','UTF-8','-cp',t['bc'],'-d',str(a.work),str(ROOT/'phone-remote/android/src/com/xiaoma/remote/Protocol.java'),str(ROOT/'phone-remote/tests/ProtocolHarness.java')],check=True)
 child=subprocess.Popen([t['java'],'-cp',str(a.work)+os.pathsep+t['bc'],'com.xiaoma.remote.ProtocolHarness'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
 def exchange(cmd,data=None):
  child.stdin.write(cmd+(' '+base64.b64encode(data).decode() if data is not None else '')+'\n');child.stdin.flush();line=child.stdout.readline().strip();assert line,'Java protocol exited';return line if line in ('OK','FAIL','REJECTED') else base64.b64decode(line)
 try:
  request=session_pb2.SessionData();request.ParseFromString(exchange('hello'));assert request.sec_ver==1;client=request.sec1.sc0.client_pubkey
  secret=X25519PrivateKey.generate();public=secret.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw);shared=secret.exchange(X25519PublicKey.from_public_bytes(client));digest=hashlib.sha256(b'AB12CD34').digest();key=bytes(x^y for x,y in zip(shared,digest));iv=bytes(range(16));cipher=Cipher(algorithms.AES(key),modes.CTR(iv)).encryptor()
  response=session_pb2.SessionData();response.sec_ver=1;response.sec1.msg=1;response.sec1.sr0.device_pubkey=public;response.sec1.sr0.device_random=iv
  request.ParseFromString(exchange('prove',response.SerializeToString()));assert request.sec1.msg==2 and cipher.update(request.sec1.sc1.client_verify_data)==public
  response=session_pb2.SessionData();response.sec_ver=1;response.sec1.msg=3;response.sec1.sr1.device_verify_data=cipher.update(client);assert exchange('verify',response.SerializeToString())=='OK'
  for payload in [b'{"cmd":"status"}',bytes(range(255)),b'a',b'word'*23]:
   encrypted=exchange('crypt',payload);assert cipher.update(encrypted)==payload
   answer=payload[::-1];assert exchange('crypt',cipher.update(answer))==answer
  response.sec1.sr1.device_verify_data=cipher.update(bytes(32));assert exchange('reject',response.SerializeToString())=='REJECTED'
  print('APK protocol: official protobuf layout, X25519/PoP proof and bidirectional continuous AES-CTR passed.')
 finally:child.stdin.close();child.wait(timeout=10)
if __name__=='__main__':main()
