package com.xiaoma.remote;
import android.app.NotificationManager;import android.content.*;import android.os.*;import android.provider.Settings;import android.service.notification.NotificationListenerService;

/** Request the system to rebind an already-authorized listener. Never grants access. */
final class NavigationListenerRecovery {
 static final Handler ui=new Handler(Looper.getMainLooper());static final NavigationRetry budget=new NavigationRetry();
 static Runnable pending;static int attempts=0;static boolean granted=false;
 static String status="等待通知监听连接";
 static ComponentName component(Context c){return new ComponentName(c,NavigationNotificationService.class);}
 static boolean hasAccess(Context c){try{
  if(Build.VERSION.SDK_INT>=27){NotificationManager m=c.getSystemService(NotificationManager.class);return m!=null&&m.isNotificationListenerAccessGranted(component(c));}
  String enabled=Settings.Secure.getString(c.getContentResolver(),"enabled_notification_listeners");
  if(enabled!=null)for(String item:enabled.split(":"))if(component(c).equals(ComponentName.unflattenFromString(item)))return true;
 }catch(RuntimeException ignored){}return false;}
 static void cancel(){if(pending!=null)ui.removeCallbacks(pending);pending=null;}
 static void connected(){cancel();budget.reset();attempts=0;granted=true;status="通知监听在线";}
 static void request(Context context,boolean explicit){
  Context c=context.getApplicationContext();
  if(explicit){cancel();budget.reset();attempts=0;}
  if(NavigationNotificationService.listening){connected();return;}
  if(!NavigationNotificationService.savedEnabled(c)){cancel();status="同步已关闭";return;}
  granted=hasAccess(c);if(!granted){cancel();status="通知使用权未授权，请在系统设置中重新授权";return;}
  if(!budget.ready(SystemClock.elapsedRealtime())){if(budget.blocked())status="自动恢复未连接，请点恢复通知监听；仍失败时重新授予通知使用权";return;}
  cancel();attempts++;budget.failed(SystemClock.elapsedRealtime());
  try{NotificationListenerService.requestRebind(component(c));status="正在请求系统恢复通知监听（"+attempts+"/3）";}
  catch(RuntimeException e){status="系统暂未接受监听恢复，请检查通知使用权";}
  pending=()->request(c,false);ui.postDelayed(pending,5000);
 }
 private NavigationListenerRecovery(){}
}
