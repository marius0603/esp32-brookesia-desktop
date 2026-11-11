"""Execute the actual notification service with deterministic Android/GATT test doubles.
No notification text, positions, phone connection or online requests are used.
"""
import argparse,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
STUBS={
'android/content/Context.java':'''package android.content;public class Context {public Pref getSharedPreferences(String n,int m){return new Pref();}public static class Pref{public boolean getBoolean(String k,boolean d){return d;}public Pref edit(){return this;}public Pref putBoolean(String k,boolean v){return this;}public void apply(){}}}''',
'android/os/Looper.java':'''package android.os;public class Looper{public static Looper getMainLooper(){return new Looper();}}''',
'android/os/Handler.java':'''package android.os;public class Handler{public Handler(Looper l){}public void post(Runnable r){}public void postDelayed(Runnable r,long d){}public void removeCallbacks(Runnable r){}public void removeCallbacksAndMessages(Object o){}}''',
'android/os/SystemClock.java':'''package android.os;public class SystemClock{public static long now=100000;public static long elapsedRealtime(){return now;}}''',
'android/os/Bundle.java':'''package android.os;public class Bundle extends java.util.HashMap<String,Object>{public CharSequence[] getCharSequenceArray(String k){return (CharSequence[])get(k);}}''',
'android/app/Notification.java':'''package android.app;public class Notification{public android.os.Bundle extras=new android.os.Bundle();public CharSequence tickerText;public static final String EXTRA_TITLE="title",EXTRA_TEXT="text",EXTRA_BIG_TEXT="big",EXTRA_SUB_TEXT="sub",EXTRA_TITLE_BIG="title.big",EXTRA_SUMMARY_TEXT="summary",EXTRA_INFO_TEXT="info",EXTRA_TEXT_LINES="lines";}''',
'android/service/notification/StatusBarNotification.java':'''package android.service.notification;public class StatusBarNotification{final String key;final android.app.Notification n=new android.app.Notification();public StatusBarNotification(String k,String text){key=k;n.extras.put("text",text);}public String getPackageName(){return "com.autonavi.minimap";}public String getKey(){return key;}public long getPostTime(){return android.os.SystemClock.now;}public android.app.Notification getNotification(){return n;}}''',
'android/service/notification/NotificationListenerService.java':'''package android.service.notification;public class NotificationListenerService extends android.content.Context{public StatusBarNotification[] notices={};public StatusBarNotification[] getActiveNotifications(){return notices;}public void onListenerConnected(){}public void onListenerDisconnected(){}public void onNotificationPosted(StatusBarNotification n){}public void onNotificationRemoved(StatusBarNotification n){}public void onDestroy(){}}''',
'org/json/JSONObject.java':'''package org.json;public class JSONObject extends java.util.LinkedHashMap<String,Object>{public String toString(){return super.toString();}}''',
'com/xiaoma/remote/MainActivity.java':'''package com.xiaoma.remote;class MainActivity{static org.json.JSONObject json(Object... a){org.json.JSONObject j=new org.json.JSONObject();for(int i=0;i<a.length;i+=2)j.put((String)a[i],a[i+1]);return j;}}''',
'com/xiaoma/remote/NavigationKeepAliveService.java':'''package com.xiaoma.remote;class NavigationKeepAliveService{static boolean running;static void ensure(android.content.Context c){running=true;}static void stop(android.content.Context c){running=false;}}''',
}
HARNESS='''package com.xiaoma.remote;
import android.os.SystemClock;import android.service.notification.StatusBarNotification;import org.json.JSONObject;import java.util.*;
public class NavigationRestartHarness {
 static void check(boolean b){if(!b)throw new AssertionError();}
 static class Link implements NavigationLink.Transport {
  boolean up=true,busy=false;List<JSONObject> sent=new ArrayList<>();NavigationLink.Reply pending;
  public boolean available(){return up;}
  public boolean send(JSONObject p,NavigationLink.Reply r){if(busy||!up)return false;sent.add(p);pending=r;return true;}
  void ack(String error){NavigationLink.Reply r=pending;pending=null;check(r!=null);r.done(error);}
  JSONObject last(){return sent.get(sent.size()-1);}
 }
 static void guide(NavigationNotificationService s,String key,String text){s.notices=new StatusBarNotification[]{new StatusBarNotification(key,text)};s.refreshActive();s.send(false);}
 public static void main(String[] a){
  Link l=new Link();NavigationLink.transport=l;NavigationNotificationService s=new NavigationNotificationService();s.onListenerConnected();
  guide(s,"route","前方80米左转");check((int)l.last().get("q")==1);String first=(String)l.last().get("s");l.ack(null);
  s.notices=new StatusBarNotification[]{};s.refreshActive();check((int)l.last().get("z")==2);
  guide(s,"route","前方90米右转");int count=l.sent.size();l.ack(null);check(l.sent.size()==count+1);check((int)l.last().get("q")==1);check(!first.equals(l.last().get("s")));l.ack(null);
  // A terminal-session rejection used to permanently set forwarding=false.
  s.send(false);String failed=(String)l.last().get("s");l.ack("导航会话已结束或数据顺序无效");check(NavigationNotificationService.forwarding);check(NavigationNotificationService.deliveryIssue);
  count=l.sent.size();s.heartbeat.run();check(l.sent.size()==count);SystemClock.now+=5000;s.heartbeat.run();check(l.sent.size()==count+1);check((int)l.last().get("q")==1);check(!failed.equals(l.last().get("s")));l.ack(null);check(!NavigationNotificationService.deliveryIssue);
  // Bounded retry, then a genuinely new route resets the budget.
  for(int i=0;i<3;i++){s.heartbeat.run();l.ack("请先解锁并退出儿童模式");SystemClock.now+=5000;}
  count=l.sent.size();s.heartbeat.run();check(l.sent.size()==count);check(s.recovery.blocked());
  s.notices=new StatusBarNotification[]{};s.refreshActive();guide(s,"route","前方70米直行");check(l.sent.size()==count+1);check((int)l.last().get("q")==1);l.ack(null);
  // Busy stop remains pending; new guidance cannot overtake the old stop.
  l.busy=true;s.notices=new StatusBarNotification[]{};s.refreshActive();count=l.sent.size();guide(s,"new","前方60米右转");check(l.sent.size()==count);l.busy=false;s.send(false);check((int)l.last().get("z")==2);l.ack(null);check((int)l.last().get("q")==1);l.ack(null);
  // Manual disable, stale lease and disconnected transport never send active guidance.
  NavigationNotificationService.enable(s,false);check((int)l.last().get("z")==2);l.ack(null);count=l.sent.size();guide(s,"off","前方50米左转");check(l.sent.size()==count);
  NavigationNotificationService.enable(s,true);s.send(false);l.ack(null);SystemClock.now+=10000;count=l.sent.size();s.send(false);check(l.sent.size()==count);l.up=false;s.heartbeat.run();check(l.sent.size()==count);
  System.out.println("Actual notification service: route restart, in-flight/busy stop, new UUID/q1, rejection recovery, retry bound, manual off, stale and disconnect passed.");
 }
}'''
def main():
 p=argparse.ArgumentParser();p.add_argument('--tools',type=Path,required=True);p.add_argument('--work',type=Path,required=True);a=p.parse_args();w=a.work.resolve();assert not w.is_relative_to(ROOT)
 t=json.loads(a.tools.read_text());src=w/'stubs';classes=w/'classes';classes.mkdir(parents=True,exist_ok=True)
 STUBS['com/xiaoma/remote/NavigationRestartHarness.java']=HARNESS
 files=[]
 for n,s in STUBS.items():
  f=src/n;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(s,encoding='utf-8');files.append(str(f))
 base=ROOT/'phone-remote/android/src/com/xiaoma/remote'
 for n in ['NavigationLink','NavigationNotice','NavigationNoticePolicy','NavigationFields','NavigationRetry','NavigationNotificationService']:files.append(str(base/(n+'.java')))
 subprocess.run([t['javac'],'-encoding','UTF-8','-d',str(classes),*files],check=True)
 subprocess.run([t['java'],'-cp',str(classes),'com.xiaoma.remote.NavigationRestartHarness'],check=True)
if __name__=='__main__':main()
