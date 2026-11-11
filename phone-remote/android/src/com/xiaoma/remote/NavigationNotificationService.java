package com.xiaoma.remote;
import android.app.Notification;
import android.content.Context;
import android.os.*;
import android.service.notification.*;
import java.util.*;
import org.json.JSONObject;

/** System-bound notification listener. Only the AMap package is inspected. RAM only. */
public class NavigationNotificationService extends NotificationListenerService {
 static final String AMAP="com.autonavi.minimap";
 static volatile boolean listening=false,forwarding=true;
 static volatile String preview="尚未收到高德通知",status="未开启转发";
 static NavigationNotice latest;static long seenAt=0;static String noticeKey="";
 static NavigationNotificationService instance;
 final Handler ui=new Handler(Looper.getMainLooper());String session="";int sequence=0;boolean waiting=false;
 final Runnable heartbeat=new Runnable(){public void run(){if(forwarding){send(false);ui.postDelayed(this,2000);}}};
 static boolean savedEnabled(Context context){return context.getSharedPreferences("navigation-notification-settings",0).getBoolean("enabled",true);}
 static void enable(Context context,boolean value){
  context.getSharedPreferences("navigation-notification-settings",0).edit().putBoolean("enabled",value).apply();
  forwarding=value;
  if(instance!=null){instance.ui.removeCallbacks(instance.heartbeat);if(value){instance.session="";instance.sequence=0;instance.ui.post(instance.heartbeat);}else instance.send(true);}
  status=value?"等待新鲜的高德导航通知":"转发已关闭";
 }
 @Override public void onListenerConnected(){listening=true;instance=this;forwarding=savedEnabled(this);try{for(StatusBarNotification n:getActiveNotifications())accept(n,false);}catch(Exception ignored){}if(forwarding)ui.post(heartbeat);}
 @Override public void onListenerDisconnected(){listening=false;forwarding=false;ui.removeCallbacks(heartbeat);send(true);latest=null;seenAt=0;noticeKey="";preview="通知服务已断开，内容已清除";status="通知服务断开，请重新授权或打开遥控";instance=null;}
 @Override public void onNotificationPosted(StatusBarNotification n){accept(n,true);}
 void accept(StatusBarNotification n,boolean fresh){
  if(n==null||!AMAP.equals(n.getPackageName()))return;
  Bundle b=n.getNotification().extras;if(b==null){preview="高德通知没有文字字段";return;}StringBuilder shown=new StringBuilder();LinkedHashSet<String> unique=new LinkedHashSet<>();
  for(String key:new String[]{Notification.EXTRA_TITLE,Notification.EXTRA_TEXT,Notification.EXTRA_BIG_TEXT,Notification.EXTRA_SUB_TEXT}){
   Object value=b.get(key);if(value instanceof CharSequence){String s=value.toString();if(s.length()>256)s=s.substring(0,256);shown.append(key).append(": ").append(s).append('\n');if(!s.trim().isEmpty())unique.add(s);}
  }
  CharSequence[] lines=b.getCharSequenceArray(Notification.EXTRA_TEXT_LINES);if(lines!=null)for(int i=0;i<Math.min(4,lines.length);i++)if(lines[i]!=null){String s=lines[i].toString();if(s.length()>256)s=s.substring(0,256);unique.add(s);shown.append("textLines: ").append(s).append('\n');}
  preview=shown.length()==0?"高德通知没有可读取的文字字段":shown.toString();
  NavigationNotice parsed=NavigationNotice.parse(String.join(" · ",unique));
  if(parsed==null){status="已读取高德通知，未识别为导航指引";return;}
  latest=parsed;noticeKey=n.getKey();
  // Reading an old active notification is useful for preview, but must not
  // manufacture a fresh guidance timestamp after reconnect/restart.
  seenAt=fresh?SystemClock.elapsedRealtime():0;
  if(parsed.ended)send(true);else if(forwarding)send(false);
 }
 @Override public void onNotificationRemoved(StatusBarNotification n){if(n!=null&&AMAP.equals(n.getPackageName())&&n.getKey().equals(noticeKey)){send(true);latest=null;seenAt=0;status="高德导航通知已移除";}}
 void send(boolean stop){
  if(waiting)return;
  NavigationNotice frame=latest;if(frame==null)return;
  if(frame.ended)stop=true;
  if(!stop&&(!forwarding||seenAt==0||SystemClock.elapsedRealtime()-seenAt>=15000)){status="导航通知未更新，设备指引将过期";return;}
  NavigationLink.Transport link=NavigationLink.transport;if(link==null||!link.available()){status="请在遥控首页连接支持导航的设备";return;}
  if(session.isEmpty()){if(stop)return;session=UUID.randomUUID().toString().replace("-","").substring(0,16);sequence=0;}
  final String owner=session;final int next=sequence+1;final boolean terminal=stop;
  JSONObject packet=MainActivity.json("cmd","nav","s",owner,"q",next,"m",2,"t",frame.turn,"d",frame.distance,"r",frame.remaining,"e",frame.seconds,"n",NavigationFields.road(frame.text),"z",stop?2:frame.turn==6?1:0);
  // An arrived first frame must open a normal session before its terminal state.
  if(next==1&&!stop)try{packet.put("z",0);}catch(Exception ignored){}
  if(packet.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8).length>256){status="通知文字过长，未发送";return;}
  waiting=true;boolean accepted=link.send(packet,error->{waiting=false;if(!session.equals(owner))return;if(error!=null){session="";forwarding=false;ui.removeCallbacks(heartbeat);status="转发停止："+error;return;}sequence=next;if(terminal){session="";sequence=0;status="设备指引已停止";}else status="已同步高德通知 · 缺失字段显示 --";});
  if(!accepted){waiting=false;status="等待蓝牙通道空闲";}
 }
 @Override public void onDestroy(){ui.removeCallbacksAndMessages(null);send(true);listening=false;forwarding=false;if(instance==this)instance=null;latest=null;seenAt=0;preview="通知服务已停止，内容已清除";super.onDestroy();}
}
