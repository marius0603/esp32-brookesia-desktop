package com.xiaoma.remote;
import java.nio.charset.StandardCharsets;
public class NavigationFieldsHarness {
 static void check(boolean value){if(!value)throw new AssertionError();}
 public static void main(String[] args){
  check(NavigationFields.turn(2)==1);check(NavigationFields.turn(3)==2);check(NavigationFields.turn(9)==0);
  for(int n:new int[]{0,1,6,7,11,12,29,34,99})check(NavigationFields.turn(n)==7);
  check(NavigationFields.turn(15)==6);check(NavigationFields.turn(19)==5);
  check(NavigationFields.road(null).equals("按手机提示"));
  String road=NavigationFields.road("南京东路😀南京东路😀南京东路😀南京东路😀南京东路😀南京东路😀");
  check(road.getBytes(StandardCharsets.UTF_8).length<=72);check(!road.endsWith("\ud83d"));
  check(!NavigationFields.road("路\n名\"\\").contains("\n"));check(!NavigationFields.road("路\"\\").contains("\""));
  check(NavigationFields.road("前方左转，进入示例路｜附加乱码").equals("进入示例路"));
  check(NavigationFields.road("进入示例路\ue123\u200b").equals("进入示例路"));
  System.out.println("Navigation fields: known/unknown turns and bounded UTF-8 roads passed.");
 }
}
