"""USB maintenance client that separates board INFO output from RPC replies."""
import time
from deploy_audiobook_sleep import StoryClient

class MaintenanceClient(StoryClient):
 def __init__(self,*args,**kwargs):
  super().__init__(*args,**kwargs)
  self.request_id=1000000000+(time.monotonic_ns()//1000)%2000000000
 def read_json(self):
  while True:
   try:return super().read_json()
   except RuntimeError as e:
    if not str(e).startswith(("invalid device response: b'I (",'invalid device response: b"I (')):raise
    self.diagnostic_lines.append(str(e).encode())

 def call_timeout(self,service,function,args,timeout_ms=60000):
  """Set device deadline and host wait; only retry an explicit non-execution."""
  previous=self.serial.timeout
  self.serial.timeout=max(previous or 0,timeout_ms/1000+10)
  def once():
   request=self.write_command('call',service=service,function=function,args=args,timeout_ms=timeout_ms)
   response=self.wait_for(request,'call','error')
   self._raise_for_error(response)
   return response
  try:
   try:return once()
   except RuntimeError as e:
    if str(e)!='invalid_command: hello is required first':raise
    self.session_active=False
    self.hello()
    return once()
  finally:self.serial.timeout=previous
