"""Independent IMA ADPCM network packets; Python runtime is pinned to 3.12."""
import audioop,struct

HEADER=struct.Struct('<4sII');META=struct.Struct('<hBH')
def encode_adpcm(pcm,turn,sequence,state=(0,0)):
    if not pcm or len(pcm)%2 or len(pcm)>1920:raise ValueError('Invalid PCM fragment')
    samples=len(pcm)//2
    padded=pcm+(b'\x00\x00' if samples%2 else b'')
    encoded,newstate=audioop.lin2adpcm(padded,2,state)
    return HEADER.pack(b'VPA1',turn,sequence)+META.pack(state[0],state[1],samples)+encoded,newstate

def decode_packet(packet):
    if len(packet)<=HEADER.size:raise ValueError('Invalid audio packet')
    magic,turn,sequence=HEADER.unpack_from(packet)
    payload=packet[HEADER.size:]
    if magic==b'VPC1':
        if len(payload)>1920 or len(payload)%2:raise ValueError('Invalid PCM fragment')
        return turn,sequence,payload
    if magic!=b'VPA1' or len(payload)<META.size:raise ValueError('Unknown audio format')
    predictor,index,samples=META.unpack_from(payload)
    encoded=payload[META.size:]
    if index>88 or not 0<samples<=960 or len(encoded)!=(samples+1)//2:raise ValueError('Invalid ADPCM fragment')
    pcm,_=audioop.adpcm2lin(encoded,2,(predictor,index))
    return turn,sequence,pcm[:samples*2]
