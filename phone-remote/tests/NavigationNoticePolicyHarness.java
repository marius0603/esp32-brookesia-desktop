package com.xiaoma.remote;
import java.util.*;
public class NavigationNoticePolicyHarness {
 static void check(boolean v){if(!v)throw new AssertionError();}
 static NavigationNoticePolicy.Candidate c(String key,String words,long time){return new NavigationNoticePolicy.Candidate(key,"",time,NavigationNotice.parse(words));}
 public static void main(String[] args){
  NavigationNoticePolicy.Candidate guidance=c("route","前方200米右转",1000),summary=c("summary","导航正在运行",2000);
  check(NavigationNoticePolicy.best(Arrays.asList(summary,guidance),"summary")==guidance);
  check(NavigationNoticePolicy.best(Arrays.asList(guidance,summary),"route")==guidance);
  check(NavigationNoticePolicy.usable(true,true,guidance.notice,120000,120500)); // Old text, freshly verified active notice.
  check(NavigationNoticePolicy.usable(true,true,guidance.notice,240000,240001)); // Still unchanged after four minutes.
  check(!NavigationNoticePolicy.usable(true,true,guidance.notice,120000,130000)); // System checks stopped.
  check(!NavigationNoticePolicy.usable(false,true,guidance.notice,120000,120001));
  check(!NavigationNoticePolicy.usable(true,false,guidance.notice,120000,120001));
  check(!NavigationNoticePolicy.usable(true,true,guidance.notice,0,120001));
  check(!NavigationNoticePolicy.usable(true,true,guidance.notice,120000,119999));
  check(NavigationNoticePolicy.best(Collections.emptyList(),"route")==null);
  check(NavigationNoticePolicy.best(Arrays.asList(summary,c("route","导航已结束",3000)),"route")==null);
  check(!NavigationNoticePolicy.usable(true,true,c("route","导航已结束",3000).notice,120000,120001));
  check(NavigationNoticePolicy.best(Arrays.asList(summary),"",true)==null); // No resurrection from a generic background notice after end.
  check(NavigationNoticePolicy.best(Arrays.asList(summary,guidance),"",true)==guidance);
  check(guidance.notice.distance==200&&guidance.notice.turn==2); // Never extrapolate movement.
  System.out.println("Navigation background policy: unchanged active notice, lease expiry, removal/end, selection and consent gates passed.");
 }
}
