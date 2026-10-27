import asyncio,json,sys,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from deepseek_client import Cancellation,Cancelled
from device_gateway import Session,HEADER
import device_gateway

class Socket:
    def __init__(self):self.audio=[];self.full=asyncio.Event()
    async def send(self,value):
        if isinstance(value,bytes):
            self.audio.append(value)
            if len(self.audio)==256:self.full.set()

class PlaybackWindowTests(unittest.IsolatedAsyncioTestCase):
    async def test_coalesced_ack_credits_only_sent_packets_once(self):
        class AcknowledgingSocket(Socket):
            async def recv(self):return json.dumps({'type':'hello','token':'paired','sample_rate':16000})
            def __aiter__(self):
                async def messages():
                    for turn,sequence in [(8,4),(9,4),(9,2),(9,5)]:
                        yield json.dumps({'type':'played','turn':turn,'seq':sequence})
                return messages()
        socket=AcknowledgingSocket();session=Session(socket);session.turn=9
        session.output_sequence=5;session.sent_lengths=dict.fromkeys(range(5),1920)
        ready=SimpleNamespace(is_set=lambda:True)
        previous=device_gateway.state['played_bytes']
        with patch.object(device_gateway,'load',return_value={'device_token':'paired'}),patch.object(device_gateway,'engines',SimpleNamespace(ready=ready)):
            await session.receive()
        self.assertEqual(session.ack_sequence,4)
        self.assertEqual(session.sent_lengths,{})
        self.assertEqual(device_gateway.state['played_bytes']-previous,5*1920)

    async def test_window_waits_and_accepts_coalesced_playback_progress(self):
        socket=Socket();session=Session(socket);session.turn=3;cancel=Cancellation()
        task=asyncio.create_task(session.event({'type':'audio','pcm':bytes(257*1920),'text':'测试'},3,cancel))
        await asyncio.wait_for(socket.full.wait(),2)
        self.assertEqual(len(socket.audio),256)
        self.assertFalse(task.done())
        session.ack_sequence=31;session.ack.set()
        await asyncio.wait_for(task,2)
        self.assertEqual(len(socket.audio),257)
        self.assertEqual(HEADER.unpack_from(socket.audio[-1]),(b'VPC1',3,256))

    async def test_cancel_releases_blocked_sender_without_more_audio(self):
        socket=Socket();session=Session(socket);session.turn=4;cancel=Cancellation();session.cancel=cancel
        task=asyncio.create_task(session.event({'type':'audio','pcm':bytes(257*1920),'text':'测试'},4,cancel))
        await asyncio.wait_for(socket.full.wait(),2)
        session.stop()
        with self.assertRaises(Cancelled):await asyncio.wait_for(task,2)
        self.assertEqual(len(socket.audio),256)

if __name__=='__main__':unittest.main()
