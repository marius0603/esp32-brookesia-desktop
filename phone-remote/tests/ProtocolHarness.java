package com.xiaoma.remote;
import java.io.*;
import java.util.Base64;
public final class ProtocolHarness {
 public static void main(String[] args)throws Exception {
  Protocol p=new Protocol(System.getenv().getOrDefault("XIAOMA_TEST_POP","0042"));BufferedReader reader=new BufferedReader(new InputStreamReader(System.in));
  for(String line;(line=reader.readLine())!=null;){String[] parts=line.split(" ",2);byte[] value=parts.length==2?Base64.getDecoder().decode(parts[1]):new byte[0];
   if(parts[0].equals("hello"))value=p.hello();
   else if(parts[0].equals("prove"))value=p.prove(value);
   else if(parts[0].equals("verify")){p.verify(value);System.out.println("OK");continue;}
   else if(parts[0].equals("reject")){try{p.verify(value);System.out.println("FAIL");}catch(SecurityException e){System.out.println("REJECTED");}continue;}
   else value=p.crypt(value);
   System.out.println(Base64.getEncoder().encodeToString(value));
  }
 }
}
