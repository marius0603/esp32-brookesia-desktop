package com.xiaoma.remote;
import android.app.*;
import android.content.*;
import android.os.*;
import android.provider.Settings;
import android.widget.*;
import java.util.Locale;

public class NavigationNotificationActivity extends Activity {
 final Handler ui=new Handler(Looper.getMainLooper());TextView connection,fields,parsed;CheckBox forward;
 TextView label(LinearLayout root,String s,int size){TextView t=new TextView(this);t.setText(s);t.setTextSize(size);t.setTextColor(0xffedf2f8);t.setPadding(0,12,0,12);root.addView(t);return t;}
 void button(LinearLayout root,String s,Runnable action){Button b=new Button(this);b.setText(s);root.addView(b);b.setOnClickListener(v->action.run());}
 public void onCreate(Bundle state){super.onCreate(state);ScrollView scroll=new ScrollView(this);LinearLayout root=new LinearLayout(this);root.setOrientation(1);root.setPadding(28,40,28,30);root.setBackgroundColor(0xff090e17);scroll.addView(root);setContentView(scroll);
  label(root,"导航通知转发 · 试验",25);connection=label(root,"等待通知授权",17);
  label(root,"只处理高德地图的通知，不读取其他应用通知；内容仅暂存内存，不写日志、不上传服务器。开启同步后，只通过已配对的蓝牙发送导航文字。无需开发者 Key 或高德 SDK。",15);
  button(root,"前往系统开启通知使用权",()->new AlertDialog.Builder(this).setTitle("允许读取导航通知？").setMessage("Android 的通知使用权权限范围较广；本App代码只处理高德地图（com.autonavi.minimap），不处理其他应用。请在接下来的系统页面手动授权“小马遥控”，随时可撤销。").setNegativeButton("取消",null).setPositiveButton("前往设置",(d,w)->{try{startActivity(new Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS));}catch(Exception e){connection.setText("无法打开，请在系统设置中搜索通知使用权");}}).show());
  forward=new CheckBox(this);forward.setText("将高德导航通知同步到设备（默认开启）");forward.setTextColor(0xff71ddc9);root.addView(forward);forward.setChecked(NavigationNotificationService.savedEnabled(this));forward.setOnCheckedChangeListener((v,checked)->NavigationNotificationService.enable(this,checked));
  label(root,"识别结果（未知字段保留 --）",19);parsed=label(root,"尚无导航指引",17);label(root,"手机实际提供的通知字段",19);fields=label(root,"尚未收到高德通知",15);
  label(root,"使用步骤：先在遥控首页连接蓝牙并授权通知，再到高德App启动导航，最后返回此页查看。通知15秒未更新则不继续保活旧指引。首次先验证通知包含什么，不代表完整或持续导航已验证；手机后台限制或蓝牙断开后需重新连接。",15);
  button(root,"返回遥控",()->finish());
 }
 final Runnable poll=new Runnable(){public void run(){connection.setText((NavigationNotificationService.listening?"通知服务已连接":"通知服务未连接，请授权")+"\n"+NavigationNotificationService.status);fields.setText(NavigationNotificationService.preview);
  NavigationNotice n=NavigationNotificationService.latest;if(n!=null){String[] turns={"直行","左转","右转","左前方","右前方","掉头","到达","未识别"};parsed.setText("方向："+turns[n.turn]+"\n转向距离："+(n.distance<0?"--":n.distance+" 米")+"\n剩余："+(n.remaining<0?"--":n.remaining+" 米")+" / "+(n.seconds<0?"--":n.seconds/60+" 分钟"));}else parsed.setText("尚无新鲜导航指引");
  ui.postDelayed(this,1000);
 }};
 protected void onResume(){super.onResume();ui.removeCallbacks(poll);ui.post(poll);}
 protected void onPause(){ui.removeCallbacks(poll);super.onPause();}
 protected void onDestroy(){ui.removeCallbacksAndMessages(null);super.onDestroy();}
}
