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
