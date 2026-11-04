package com.xiaoma.remote;
public final class SongControlsHarness {
 static void check(boolean value){if(!value)throw new AssertionError();}
 public static void main(String[] args){
  check(SongControls.toggleCommand(false,"Ended").equals("song_play"));
  check(SongControls.toggleCommand(false,"Idle").equals("song_play"));
  check(SongControls.toggleCommand(true,"Playing").equals("song_pause"));
  check(SongControls.toggleCommand(true,"Paused").equals("song_resume"));
  check(SongControls.stateLabel("SleepEnded").contains("晚安"));
  check(SongControls.stateLabel("Error").contains("失败"));
  check(SongControls.timerLabel(true,61).equals("剩余 2 分钟"));
  check(SongControls.timerLabel(false,900).equals("睡眠定时"));
  check(SongControls.page(-1,20)==0 && SongControls.page(7,20)==6);
  check(SongControls.page(100,0)==0 && SongControls.page(1,3)==0);
  System.out.println("Song controls: play/pause/resume, timer, state and seven-page bounds passed.");
 }
}
