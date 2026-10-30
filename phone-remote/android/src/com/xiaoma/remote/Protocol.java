package com.xiaoma.remote;
import java.io.ByteArrayOutputStream;
import java.security.*;
import java.util.*;
import javax.crypto.*;
import javax.crypto.spec.*;
import org.bouncycastle.math.ec.rfc7748.X25519;

/** ESP protocomm Security 1; one continuous AES-CTR stream in wire order. */
final class Protocol {
 private final byte[] secret=new byte[32],pub=new byte[32];
 private final String pop;
 private byte[] peer;
 private Cipher cipher;
 Protocol(String code){pop=code;X25519.generatePrivateKey(new SecureRandom(),secret);X25519.generatePublicKey(secret,0,pub,0);}
 static byte[] join(byte[]... parts){ByteArrayOutputStream out=new ByteArrayOutputStream();for(byte[] p:parts)out.write(p,0,p.length);return out.toByteArray();}
 static byte[] integer(int field,int n){return join(varint(field*8),varint(n));}
 static byte[] bytes(int field,byte[] value){return join(varint(field*8+2),varint(value.length),value);}
 static byte[] varint(int n){ByteArrayOutputStream o=new ByteArrayOutputStream();while(n>127){o.write((n&127)|128);n>>>=7;}o.write(n);return o.toByteArray();}
 static byte[] field(byte[] wire,int wanted){int p=0;while(p<wire.length){int key=0,s=0,b;do{b=wire[p++]&255;key|=(b&127)<<s;s+=7;if(s>35)throw new IllegalArgumentException();}while((b&128)!=0);int value=0;s=0;do{b=wire[p++]&255;value|=(b&127)<<s;s+=7;if(s>35)throw new IllegalArgumentException();}while((b&128)!=0);if((key&7)==2){if(value<0||p+value>wire.length)throw new IllegalArgumentException();if((key>>3)==wanted)return Arrays.copyOfRange(wire,p,p+value);p+=value;}else if((key&7)!=0)throw new IllegalArgumentException();}return new byte[0];}
 byte[] hello(){return join(integer(2,1),bytes(11,bytes(20,bytes(1,pub))));}
 byte[] prove(byte[] response)throws Exception{
  byte[] data=field(field(response,11),21);peer=field(data,2);byte[] iv=field(data,3);
  if(peer.length!=32||iv.length!=16)throw new SecurityException("握手失败");
  byte[] key=new byte[32];if(!X25519.calculateAgreement(secret,0,peer,0,key,0))throw new SecurityException("设备密钥无效");
  byte[] hash=MessageDigest.getInstance("SHA-256").digest(pop.getBytes("UTF-8"));for(int i=0;i<32;i++)key[i]^=hash[i];
  cipher=Cipher.getInstance("AES/CTR/NoPadding");cipher.init(Cipher.ENCRYPT_MODE,new SecretKeySpec(key,"AES"),new IvParameterSpec(iv));Arrays.fill(key,(byte)0);Arrays.fill(secret,(byte)0);
  return join(integer(2,1),bytes(11,join(integer(1,2),bytes(22,bytes(2,cipher.update(peer))))));
 }
 void verify(byte[] response){byte[] proof=field(field(field(response,11),23),3);if(proof.length!=32||!MessageDigest.isEqual(cipher.update(proof),pub))throw new SecurityException("配对码不正确");}
 byte[] crypt(byte[] data){return cipher.update(data);}
}
