package com.xiaoma.remote;
import java.util.*;
public final class StoryNavigationHarness {
 static void check(boolean okay){if(!okay)throw new AssertionError();}
 public static void main(String[] args){
  List<String> names=Arrays.asList("咕咚","小马过河","雪孩子");Random r=new Random(42);
  check(StoryNavigation.next(names,"咕咚","sequence",r)==1);
  check(StoryNavigation.next(names,"雪孩子","sequence",r)==0);
  check(StoryNavigation.next(names,"咕咚","repeat_one",r)==1);
  for(int i=0;i<100;i++)check(StoryNavigation.next(names,"小马过河","random",r)!=1);
  check(StoryNavigation.next(names,"","sequence",r)==0);
  check(StoryNavigation.next(Collections.singletonList("咕咚"),"咕咚","random",r)==0);
  for(List<String> bad:Arrays.asList(Collections.<String>emptyList(),Arrays.asList("咕咚","咕咚"))){
   try{StoryNavigation.next(bad,"咕咚","sequence",r);throw new AssertionError();}catch(IllegalArgumentException expected){}
  }
  try{StoryNavigation.next(names,"旧故事","sequence",r);throw new AssertionError();}catch(IllegalArgumentException expected){}
  check(StoryNavigation.displayName("/sdcard/audiobooks/雪孩子.mp3").equals("雪孩子"));
  System.out.println("Next story: sequence/wrap/random/single/repeat/empty/ambiguity/stale-title checks passed.");
 }
}
