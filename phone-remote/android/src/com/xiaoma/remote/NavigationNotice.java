package com.xiaoma.remote;
import java.util.regex.*;

/** Conservative parsing of public notification text; missing fields stay unknown. */
final class NavigationNotice {
 final String text;final int turn,distance,remaining,seconds;final boolean ended;
 NavigationNotice(String s,int t,int d,int r,int e,boolean stop){text=s;turn=t;distance=d;remaining=r;seconds=e;ended=stop;}
 static int meters(String value,String unit){try{double n=Double.parseDouble(value)*(unit.equals("米")||unit.equals("m")?1:1000);return n>=0&&n<=1000000?(int)Math.round(n):-1;}catch(Exception e){return -1;}}
 static NavigationNotice parse(String input){
  String s=input==null?"":input.replaceAll("[\\p{Cntrl}]"," ").trim();if(s.length()>1024)s=s.substring(0,1024);
  boolean ended=s.contains("导航已结束")||s.contains("已结束导航");
  if(!ended&&!Pattern.compile("导航|左转|右转|直行|掉头|左前方|右前方|目的地|终点|行驶|继续步行|向左|向右").matcher(s).find())return null;
  int t=7;
  if(Pattern.compile("已到达|到达目的地|到达终点").matcher(s).find())t=6;
  else if(s.contains("掉头")||s.contains("调头"))t=5;
  else if(s.contains("左前方"))t=3;else if(s.contains("右前方"))t=4;
  else if(s.contains("左转")||s.contains("向左"))t=1;else if(s.contains("右转")||s.contains("向右"))t=2;else if(s.contains("直行"))t=0;
  int d=-1,r=-1,e=-1;
  Matcher rem=Pattern.compile("(?:剩余|全程|距终点)\\s*(\\d+(?:\\.\\d+)?)\\s*(公里|千米|km|米|m)",Pattern.CASE_INSENSITIVE).matcher(s);
  if(rem.find())r=meters(rem.group(1),rem.group(2).toLowerCase(java.util.Locale.ROOT));
  Matcher next=Pattern.compile("(\\d+(?:\\.\\d+)?)\\s*(公里|千米|km|米|m)",Pattern.CASE_INSENSITIVE).matcher(s);
  while(t<6&&next.find()){
   String before=s.substring(Math.max(0,next.start()-8),next.start());
   if(Pattern.compile("(?:剩余|全程|距终点)\\s*$").matcher(before).find())continue;
   int value=meters(next.group(1),next.group(2).toLowerCase(java.util.Locale.ROOT));if(value<=100000)d=value;break;
  }
  Matcher time=Pattern.compile("(?:剩余|预计|约)\\s*(?:(\\d+)小时)?\\s*(\\d+)分钟").matcher(s);
  if(time.find())try{int n=(time.group(1)==null?0:Integer.parseInt(time.group(1))*3600)+Integer.parseInt(time.group(2))*60;if(n<=604800)e=n;}catch(Exception ignored){}
  return new NavigationNotice(s,t,d,r,e,ended);
 }
}
