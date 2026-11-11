package com.xiaoma.remote;
import java.util.List;
/** Active-notification lease is distinct from instruction content age. */
final class NavigationNoticePolicy {
 static final class Candidate {
  final String key,preview;final long posted;final NavigationNotice notice;
  Candidate(String k,String p,long at,NavigationNotice n){key=k;preview=p;posted=at;notice=n;}
 }
 static int quality(NavigationNotice n){return n==null||n.ended?-1:(n.turn<7?4:0)+(n.distance>=0?2:0)+(n.remaining>=0?1:0)+(n.seconds>=0?1:0);}
 static Candidate best(List<Candidate> candidates,String current){return best(candidates,current,false);}
 static Candidate best(List<Candidate> candidates,String current,boolean awaitingGuidance){Candidate best=null;
  for(Candidate c:candidates)if(c.key.equals(current)&&c.notice!=null&&c.notice.ended)return null;
  for(Candidate c:candidates){if(quality(c.notice)<0||awaitingGuidance&&quality(c.notice)==0)continue;
   if(best==null||quality(c.notice)>quality(best.notice)||quality(c.notice)==quality(best.notice)&&((c.key.equals(current)&&!best.key.equals(current))||!best.key.equals(current)&&c.posted>best.posted))best=c;
  }return best;
 }
 static boolean usable(boolean enabled,boolean listening,NavigationNotice n,long checked,long now){return enabled&&listening&&n!=null&&!n.ended&&checked>0&&now>=checked&&now-checked<10000;}
 private NavigationNoticePolicy(){}
}
