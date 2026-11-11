package com.xiaoma.remote;
public class NavigationNoticeHarness {
 static void check(boolean v){if(!v)throw new AssertionError();}
 public static void main(String[] args){
  NavigationNotice n=NavigationNotice.parse("前方200米右转 · 示例道路 · 剩余3.5公里 预计12分钟");
  check(n.turn==2&&n.distance==200&&n.remaining==3500&&n.seconds==720);
  n=NavigationNotice.parse("正在导航 · 剩余3.5公里");check(n.turn==7&&n.distance==-1&&n.remaining==3500&&n.seconds==-1);
  n=NavigationNotice.parse("导航中");check(n.turn==7&&n.distance==-1&&n.remaining==-1);
  n=NavigationNotice.parse("导航中 25公里 32分钟");check(n.distance==-1&&n.remaining==-1);
  check(NavigationNotice.parse("限时领券优惠")==null);
  check(NavigationNotice.parse("前方0.1公里掉头").distance==100);
  check(NavigationNotice.parse("前方50米向左前方行进").turn==3);
  check(NavigationNotice.parse("已到达目的地").turn==6);
  check(NavigationNotice.parse("导航已结束").ended);
  check(NavigationNotice.parse("导航中，剩余2公里 预计1小时12分钟").seconds==4320);
  System.out.println("Notification parsing: unknown fields, step vs remaining distance, turns and terminal states passed.");
 }
}
