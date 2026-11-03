package com.xiaoma.remote;
import java.util.*;
public final class RadioControlsHarness {
 static void check(boolean value){if(!value)throw new AssertionError();}
 public static void main(String[] args){
  List<String> ids=Arrays.asList("suzhou","junior","classic","news"),groups=Arrays.asList("儿童","儿童","音乐","资讯");
  check(RadioControls.next(ids,groups,"suzhou","儿童",1).equals("junior"));
  check(RadioControls.next(ids,groups,"junior","儿童",1).equals("suzhou"));
  check(RadioControls.next(ids,groups,"suzhou","儿童",-1).equals("junior"));
  check(RadioControls.next(ids,groups,"suzhou","资讯",1).equals("news"));
  check(RadioControls.next(ids,groups,"missing","儿童",-1).equals("junior"));
  check(RadioControls.next(ids,groups,"classic","音乐",1).equals("classic"));
  try{RadioControls.next(ids,groups,"suzhou","空",1);throw new AssertionError();}catch(IllegalArgumentException expected){}
  check(RadioControls.toggleCommand(false,false).equals("radio_play"));
  check(RadioControls.toggleCommand(true,false).equals("radio_pause"));
  check(RadioControls.toggleCommand(true,true).equals("radio_resume"));
  check(RadioControls.timerLabel(true,61).equals("剩余 2 分钟"));
  check(RadioControls.timerLabel(true,0).equals("剩余 0 分钟"));
  check(RadioControls.timerLabel(false,900).equals("定时关闭"));
  check(RadioControls.stateLabel("Buffering").contains("缓冲"));
  check(RadioControls.stateLabel("Reconnecting").contains("重连"));
  check(RadioControls.stateLabel("TimerEnded").contains("停止"));
  System.out.println("Radio controls: category navigation, wrap, empty list, playback state and timer rounding passed.");
 }
}
