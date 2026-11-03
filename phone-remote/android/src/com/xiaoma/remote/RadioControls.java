package com.xiaoma.remote;
import java.util.*;

/** Playback decisions shared by the Android page and host-side tests. */
final class RadioControls {
 static String toggleCommand(boolean active,boolean paused){return !active?"radio_play":paused?"radio_resume":"radio_pause";}
 static String stateLabel(String state){
  switch(state){
   case "Connecting":return "连接电台…";
   case "Buffering":return "缓冲中…";
   case "Playing":return "正在播放";
   case "Paused":return "已暂停";
   case "Reconnecting":return "连接中断，正在重连…";
   case "TimerEnded":return "定时结束，已停止";
   case "Error":return "播放失败，请切换频道或重试";
   default:return "准备播放";
  }
 }
 static String timerLabel(boolean active,int seconds){return active?"剩余 "+Math.max(0,(seconds+59)/60)+" 分钟":"定时关闭";}
 static String next(List<String> ids,List<String> groups,String selected,String category,int step){
  if(ids.size()!=groups.size()||Math.abs(step)!=1)throw new IllegalArgumentException("频道列表异常，请刷新");
  ArrayList<String> filtered=new ArrayList<>();
  for(int i=0;i<ids.size();i++)if(groups.get(i).equals(category))filtered.add(ids.get(i));
  if(filtered.isEmpty())throw new IllegalArgumentException("请先加载这个分类的频道");
  int at=filtered.indexOf(selected);if(at<0)at=step>0?-1:0;
  return filtered.get((at+step+filtered.size())%filtered.size());
 }
}
