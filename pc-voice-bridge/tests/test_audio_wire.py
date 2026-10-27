import math,struct,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from audio_wire import encode_adpcm,decode_packet,HEADER,META

class AudioWireTests(unittest.TestCase):
    def test_compressed_voice_roundtrip_and_independent_packet_state(self):
        source=struct.pack('<4800h',*[int(5000*math.sin(i*2*math.pi*440/16000)) for i in range(4800)])
        state=(0,0);packets=[];decoded=[]
        for sequence,offset in enumerate(range(0,len(source),1920)):
            packet,state=encode_adpcm(source[offset:offset+1920],7,sequence,state)
            turn,number,pcm=decode_packet(packet)
            self.assertEqual((turn,number),(7,sequence));decoded.append(pcm);packets.append(packet)
        self.assertLess(sum(map(len,packets)),len(source)*.27)
        # Decoding a later packet does not need any earlier packet.
        self.assertEqual(decode_packet(packets[-1])[2],decoded[-1])
        actual=struct.unpack('<4800h',b''.join(decoded));expected=struct.unpack('<4800h',source)
        error=sum((a-b)**2 for a,b in zip(actual[300:],expected[300:]));signal=sum(a*a for a in expected[300:])
        self.assertLess(error/signal,.01)
    def test_odd_sample_count_and_legacy_pcm(self):
        pcm=struct.pack('<3h',1,2,3);packet,_=encode_adpcm(pcm,2,4)
        self.assertEqual(len(decode_packet(packet)[2]),len(pcm))
        self.assertEqual(decode_packet(HEADER.pack(b'VPC1',2,4)+pcm),(2,4,pcm))
    def test_invalid_state_length_and_sample_count_are_rejected(self):
        for payload in [META.pack(0,89,2)+b'\x00',META.pack(0,0,0),META.pack(0,0,961)+bytes(481),META.pack(0,0,4)+b'\x00']:
            with self.assertRaises(ValueError):decode_packet(HEADER.pack(b'VPA1',1,0)+payload)

if __name__=='__main__':unittest.main()
