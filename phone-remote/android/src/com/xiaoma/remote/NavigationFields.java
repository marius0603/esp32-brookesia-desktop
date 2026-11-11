package com.xiaoma.remote;
import java.nio.charset.StandardCharsets;

final class NavigationFields {
 // Device: straight, left, right, slight left/right, U-turn, arrival, other.
 static int turn(int icon) {
  switch(icon) {
   case 9:case 20:return 0;
   case 2:return 1;case 3:return 2;case 4:return 3;case 5:return 4;
   case 8:case 19:return 5;case 15:return 6;
   default:return 7; // Crosswalks, stairs, roundabouts: keep phone's instruction.
  }
 }
 static String road(String input) {
  if(input==null||input.equals("null"))return "按手机提示";
  StringBuilder result=new StringBuilder();int bytes=0;
  for(int at=0;at<input.length();) {
   int cp=input.codePointAt(at);at+=Character.charCount(cp);
   if(cp<32||cp==127||cp>=0xd800&&cp<=0xdfff)continue;
   if(cp==34)cp=0xff02;if(cp==92)cp=0xff3c; // Bound JSON escaping as well as UTF-8 bytes.
   String piece=new String(Character.toChars(cp));int size=piece.getBytes(StandardCharsets.UTF_8).length;
   if(bytes+size>72)break;result.append(piece);bytes+=size;
  }
  return result.length()==0?"按手机提示":result.toString();
 }
 private NavigationFields() {}
}
