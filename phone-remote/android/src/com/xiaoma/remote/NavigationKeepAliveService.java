package com.xiaoma.remote;
import android.app.*;import android.content.*;import android.content.pm.ServiceInfo;import android.os.*;
/** Retain foreground importance for the existing serialized BLE session. */
public class NavigationKeepAliveService extends Service {
 static volatile boolean running=false;
 static void ensure(Context c){NavigationLink.Transport t=NavigationLink.transport;if(running||!NavigationNotificationService.forwarding||t==null||!t.available())return;try{c.startForegroundService(new Intent(c,NavigationKeepAliveService.class));}catch(RuntimeException e){NavigationNotificationService.status="后台运行受限，请保持遥控在前台";}}
 static void stop(Context c){c.stopService(new Intent(c,NavigationKeepAliveService.class));}
 final Handler ui=new Handler(Looper.getMainLooper());final Runnable check=new Runnable(){public void run(){NavigationLink.Transport t=NavigationLink.transport;if(!NavigationNotificationService.forwarding||t==null||!t.available()){stopSelf();return;}ui.postDelayed(this,5000);}};
 public void onCreate(){super.onCreate();getSystemService(NotificationManager.class).createNotificationChannel(new NotificationChannel("navigation_sync","导航后台同步",NotificationManager.IMPORTANCE_LOW));
 PendingIntent open=PendingIntent.getActivity(this,0,new Intent(this,MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP|Intent.FLAG_ACTIVITY_CLEAR_TOP),PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);
 PendingIntent stop=PendingIntent.getService(this,1,new Intent(this,NavigationKeepAliveService.class).setAction("stop"),PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);
 Notification note=new Notification.Builder(this,"navigation_sync").setSmallIcon(android.R.drawable.ic_dialog_map).setContentTitle("小马导航同步运行中").setContentText("蓝牙同步高德指引 · 点击返回遥控").setContentIntent(open).setOngoing(true).addAction(new Notification.Action.Builder(null,"停止同步",stop).build()).build();
 try{if(Build.VERSION.SDK_INT>=29)startForeground(42,note,ServiceInfo.FOREGROUND_SERVICE_TYPE_CONNECTED_DEVICE);else startForeground(42,note);running=true;ui.post(check);}catch(RuntimeException e){NavigationNotificationService.status="后台服务受限，请保持遥控在前台";stopSelf();}}
 public int onStartCommand(Intent i,int f,int id){if(i!=null&&"stop".equals(i.getAction())){NavigationNotificationService.enable(this,false);stopSelf();}return START_NOT_STICKY;}
 public void onDestroy(){running=false;ui.removeCallbacksAndMessages(null);stopForeground(STOP_FOREGROUND_REMOVE);super.onDestroy();}public IBinder onBind(Intent i){return null;}
}
