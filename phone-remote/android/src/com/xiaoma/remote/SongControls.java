package com.xiaoma.remote;

/** Decisions used by the nursery-song page and its host tests. */
final class SongControls {
 static String toggleCommand(boolean active,String state){return !active?"song_play":"Paused".equals(state)?"song_resume":"song_pause";}
 static String stateLabel(String state){
  switch(state){
   case "Loading":return "正在打开儿歌…";
   case "Playing":return "正在播放";
   case "Paused":return "已暂停";
   case "Ended":return "本首已结束";
   case "SleepEnded":return "定时结束，晚安";
   case "Goodnight":return "晚安";
   case "Error":return "播放失败，请重新选择儿歌";
   default:return "选择一首儿歌开始播放";
  }
 }
 static String timerLabel(boolean active,int seconds){return active?"剩余 "+Math.max(0,(seconds+59)/60)+" 分钟":"睡眠定时";}
 static int page(int requested,int total){return Math.max(0,Math.min(requested,Math.max(0,(total-1)/3)));}
}
