package com.xiaoma.remote;
import android.app.Notification;import android.content.Context;import android.os.*;import android.service.notification.*;import java.util.*;import org.json.JSONObject;
/** Only AMap notifications are inspected; all guidance stays in RAM. */
public class NavigationNotificationService extends NotificationListenerService {
 static final String AMAP="com.autonavi.minimap";
 static volatile boolean listening=false,forwarding=true,deliveryIssue=false;
 static volatile String preview="尚未收到高德通知",status="未开启转发";
 static NavigationNotice latest;static long seenAt=0,checkedAt=0;static int activeChecks=0;static String noticeKey="";
 static NavigationNotificationService instance;
 final Handler ui=new Handler(Looper.getMainLooper());String session="";int sequence=0;boolean waiting=false,stopRequested=false,awaitingGuidance=false;NavigationNotice stopFrame;
 final NavigationRetry recovery=new NavigationRetry();
 final Runnable stopRetry=()->send(true);
 final Runnable heartbeat=new Runnable(){public void run(){if(forwarding){refreshActive();send(false);ui.postDelayed(this,2000);}}};
 static boolean savedEnabled(Context c){return c.getSharedPreferences("navigation-notification-settings",0).getBoolean("enabled",true);}
 static void enable(Context c,boolean value){c.getSharedPreferences("navigation-notification-settings",0).edit().putBoolean("enabled",value).apply();forwarding=value;
  if(value)NavigationKeepAliveService.ensure(c);else NavigationKeepAliveService.stop(c);
  if(instance!=null){instance.recovery.reset();deliveryIssue=false;instance.ui.removeCallbacks(instance.heartbeat);if(value)instance.ui.post(instance.heartbeat);else instance.send(true);}
  status=value?"正在核对系统中的导航通知":"转发已关闭";
 }
 public void onListenerConnected(){listening=true;instance=this;forwarding=savedEnabled(this);recovery.reset();deliveryIssue=false;refreshActive();ui.removeCallbacks(heartbeat);if(forwarding)ui.post(heartbeat);}
 public void onListenerDisconnected(){listening=false;forwarding=false;ui.removeCallbacks(heartbeat);send(true);latest=null;checkedAt=seenAt=0;noticeKey="";preview="通知服务已断开，内容已清除";status="通知服务断开，请重新授权或打开遥控";instance=null;}
 public void onNotificationPosted(StatusBarNotification n){if(n!=null&&AMAP.equals(n.getPackageName())){refreshActive();if(forwarding)send(false);}}
 public void onNotificationRemoved(StatusBarNotification n){if(n!=null&&AMAP.equals(n.getPackageName())){if(n.getKey().equals(noticeKey))awaitingGuidance=true;refreshActive();if(forwarding)send(false);}}
 NavigationNoticePolicy.Candidate decode(StatusBarNotification n){
  if(n==null||!AMAP.equals(n.getPackageName()))return null; // Filter before reading extras.
  Bundle b=n.getNotification().extras;if(b==null)return null;StringBuilder shown=new StringBuilder();LinkedHashSet<String> parts=new LinkedHashSet<>();
  for(String key:new String[]{Notification.EXTRA_TITLE,Notification.EXTRA_TEXT,Notification.EXTRA_BIG_TEXT,Notification.EXTRA_SUB_TEXT,Notification.EXTRA_TITLE_BIG,Notification.EXTRA_SUMMARY_TEXT,Notification.EXTRA_INFO_TEXT}){
   Object value=b.get(key);if(value instanceof CharSequence){String s=value.toString();if(s.length()>256)s=s.substring(0,256);shown.append(key).append(": ").append(s).append('\n');if(!s.trim().isEmpty())parts.add(s);}}
  CharSequence[] lines=b.getCharSequenceArray(Notification.EXTRA_TEXT_LINES);if(lines!=null)for(int i=0;i<Math.min(4,lines.length);i++)if(lines[i]!=null){String s=lines[i].toString();if(s.length()>256)s=s.substring(0,256);parts.add(s);shown.append("textLines: ").append(s).append('\n');}
  CharSequence ticker=n.getNotification().tickerText;if(ticker!=null){String s=ticker.toString();if(s.length()>256)s=s.substring(0,256);parts.add(s);shown.append("ticker: ").append(s).append('\n');}
  NavigationNotice parsed=NavigationNotice.parse(String.join(" · ",parts));if(parsed==null)return null;
  return new NavigationNoticePolicy.Candidate(n.getKey(),shown.toString(),n.getPostTime(),parsed);
 }
 void refreshActive(){if(!listening)return;try{
  StatusBarNotification[] active=getActiveNotifications();if(active==null){status="系统通知暂不可读取，等待恢复";return;}
  ArrayList<NavigationNoticePolicy.Candidate> candidates=new ArrayList<>();for(StatusBarNotification n:active){NavigationNoticePolicy.Candidate c=decode(n);if(c!=null)candidates.add(c);}
  activeChecks++;NavigationNoticePolicy.Candidate best=NavigationNoticePolicy.best(candidates,noticeKey,awaitingGuidance);
  if(best==null){awaitingGuidance=true;send(true);latest=null;noticeKey="";checkedAt=0;recovery.reset();deliveryIssue=false;preview="当前没有有效的高德导航通知";status="导航通知已移除或结束";return;}
  if(NavigationNoticePolicy.quality(best.notice)>0)awaitingGuidance=false;
  long now=SystemClock.elapsedRealtime();
  if(latest==null||!best.key.equals(noticeKey)||!best.notice.text.equals(latest.text))seenAt=now;
  // A successful OS query renews only the active-notification lease. It does
  // not fabricate a changed instruction timestamp, distance or position.
  checkedAt=now;latest=best.notice;noticeKey=best.key;preview=best.preview;
 }catch(RuntimeException e){status="系统通知核对失败；未延长旧指引有效期";}}
 static boolean fresh(){return NavigationNoticePolicy.usable(forwarding,listening,latest,checkedAt,SystemClock.elapsedRealtime());}
 static String diagnostics(){long now=SystemClock.elapsedRealtime();NavigationLink.Transport t=NavigationLink.transport;return "蓝牙："+(t!=null&&t.available()?"已连接":"未连接")+"\n通知监听："+(listening?"在线":"断开")+"\n后台服务："+(NavigationKeepAliveService.running?"运行":"停止")+"\n系统核对次数："+activeChecks+"\n最近核对："+(checkedAt==0?"--":(now-checkedAt)/1000+"秒前")+"\n指引内容变化："+(seenAt==0?"--":(now-seenAt)/1000+"秒前");}
 void send(boolean stop){
  if(stop&&session.isEmpty())return;
  if(stop&&!stopRequested&&!session.isEmpty()){stopRequested=true;stopFrame=latest;}
  if(waiting)return;final boolean terminal=stopRequested;NavigationNotice frame=terminal?stopFrame:latest;if(frame==null)return;
  if(!terminal&&!fresh()){status="无法核对当前导航通知，设备指引将过期";return;}
  if(!terminal&&!recovery.ready(SystemClock.elapsedRealtime()))return;
  NavigationLink.Transport link=NavigationLink.transport;if(link==null||!link.available()){status="请在遥控首页连接支持导航的设备";return;}
  if(session.isEmpty()){if(terminal)return;session=UUID.randomUUID().toString().replace("-","").substring(0,16);sequence=0;}
  final String owner=session;final int next=sequence+1;
  JSONObject packet=MainActivity.json("cmd","nav","s",owner,"q",next,"m",2,"t",frame.turn,"d",frame.distance,"r",frame.remaining,"e",frame.seconds,"n",NavigationFields.road(frame.text),"z",terminal?2:next==1?0:frame.turn==6?1:0);
  if(packet.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8).length>256){status="通知文字过长，未发送";return;}
  waiting=true;boolean accepted=link.send(packet,error->{waiting=false;if(!session.equals(owner))return;
   if(error!=null){session="";sequence=0;stopRequested=false;stopFrame=null;ui.removeCallbacks(stopRetry);recovery.failed(SystemClock.elapsedRealtime());deliveryIssue=true;
    status=(recovery.blocked()?"同步暂停，请重新开始导航或关闭再开启同步：":"等待新会话重试：")+error;return;}
   recovery.reset();deliveryIssue=false;
   sequence=next;if(terminal){session="";sequence=0;stopRequested=false;stopFrame=null;ui.removeCallbacks(stopRetry);status="设备指引已停止";if(forwarding&&fresh())send(false);}
   else{status=SystemClock.elapsedRealtime()-seenAt>=15000?"蓝牙同步正常 · 系统通知仍有效，指引未变化":"已同步系统中的高德导航通知";if(stopRequested)send(true);}
  });if(!accepted){waiting=false;status="等待蓝牙通道空闲";if(terminal){ui.removeCallbacks(stopRetry);ui.postDelayed(stopRetry,500);}}
 }
 public void onDestroy(){ui.removeCallbacksAndMessages(null);send(true);listening=false;forwarding=false;if(instance==this)instance=null;latest=null;checkedAt=seenAt=0;preview="通知服务已停止，内容已清除";super.onDestroy();}
}
