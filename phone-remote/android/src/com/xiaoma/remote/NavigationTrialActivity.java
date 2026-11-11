package com.xiaoma.remote;

import android.app.*;
import android.content.*;
import android.content.pm.PackageManager;
import android.graphics.*;
import android.os.*;
import android.view.*;
import android.widget.*;
import java.lang.reflect.*;
import java.text.SimpleDateFormat;
import java.util.*;
import org.json.JSONObject;

/** Foreground-only fixed-route trial. Optional BLE forwarding contains no coordinates. */
public class NavigationTrialActivity extends Activity {
 final Handler ui=new Handler(Looper.getMainLooper());
 TextView state,road,distance,remaining;CheckBox freeConfirmed;Button online;
 TextView relayStatus;CheckBox relayEnabled;String relaySession="";int relaySequence=0,relaySource=0,relayTurn=0,relayDistance=0,relayRemaining=0,relaySeconds=0,relayPhase=0;
 String relayRoad="";boolean relayValid=false,relayWaiting=false,foreground=true;
 final Runnable heartbeat=new Runnable(){public void run(){if(foreground){sendRelay();ui.postDelayed(this,2000);}}};
 Arrow arrow;Object engine,listener,locationClient,locationListener;Class<?> sdk;boolean busy=false,routeSent=false,navigating=false,closed=false,pendingLocation=false;int generation=0;
 static final int INK=0xffedf2f8,MUTED=0xffa6b4c7;
 static boolean enabled(Context context){try{return context.getPackageManager().getApplicationInfo(context.getPackageName(),PackageManager.GET_META_DATA).metaData.getBoolean("xiaoma.navigation_trial",false);}catch(Exception e){return false;}}
 int dp(int n){return Math.round(n*getResources().getDisplayMetrics().density);}
 TextView label(LinearLayout root,String value,int size){TextView t=new TextView(this);t.setText(value);t.setTextColor(INK);t.setTextSize(size);t.setPadding(0,dp(8),0,dp(8));root.addView(t);return t;}
 Button button(LinearLayout root,String value,Runnable action){Button b=new Button(this);b.setText(value);root.addView(b,new LinearLayout.LayoutParams(-1,dp(56)));b.setOnClickListener(v->action.run());return b;}
 public void onCreate(Bundle saved){super.onCreate(saved);
  if(!enabled(this)){finish();return;}
  ScrollView scroll=new ScrollView(this);LinearLayout root=new LinearLayout(this);root.setOrientation(1);root.setPadding(dp(22),dp(30),dp(22),dp(24));root.setBackgroundColor(0xff090e17);scroll.addView(root);setContentView(scroll);
  label(root,"小马导航 · 免费试验",25);state=label(root,"未连接高德服务",17);state.setTextColor(0xffffd166);
  arrow=new Arrow(this);root.addView(arrow,new LinearLayout.LayoutParams(-1,dp(170)));
  distance=label(root,"-- 米",38);road=label(root,"固定示例路线，不使用当前位置",19);remaining=label(root,"先用离线演示检查界面",16);
  relayEnabled=new CheckBox(this);relayEnabled.setText("通过已连接的蓝牙同步到设备");relayEnabled.setTextColor(INK);root.addView(relayEnabled);
  relayStatus=label(root,"先在遥控首页连接蓝牙，再勾选同步",14);relayStatus.setTextColor(MUTED);
  relayEnabled.setOnCheckedChangeListener((b,checked)->{if(!checked)endRelay();else sendRelay();});
  button(root,"离线演示 60 秒（不请求网络）",()->offline());
  freeConfirmed=new CheckBox(this);freeConfirmed.setText("已核对本月个人学习免费配额仍有余量");freeConfirmed.setTextColor(INK);root.addView(freeConfirmed);
  online=button(root,"算路并模拟 60 秒",()->consent());
  button(root,"在线定位一次",()->locationConsent());
  button(root,"停止并断开导航",()->stop("已停止，高德导航未连接"));
  TextView note=label(root,"本试验不购买服务。每个北京时间自然日最多5次主动在线尝试，算路与定位共享此上限，失败也计次；无自动重试。配额外高德仍可能收费，本地限次不代表账户硬限额。\n算路使用固定示例坐标；单次在线定位需另行授权，不反查详细地址、不持续后台定位。不使用智能硬件定位、搜索或车载功能。设备只接收方向、距离、道路名与剩余时间，不接收坐标或Key。蓝牙同步不增加高德请求；设备15秒未收到数据即过期。当前仅支持演示和模拟导航。",14);note.setTextColor(MUTED);
  button(root,"高德隐私政策",()->startActivity(new Intent(Intent.ACTION_VIEW,android.net.Uri.parse("https://lbs.amap.com/pages/privacy/"))));
  button(root,"返回遥控",()->finish());updateBudget();
 }
 String today(){SimpleDateFormat f=new SimpleDateFormat("yyyy-MM-dd",Locale.US);f.setTimeZone(TimeZone.getTimeZone("Asia/Shanghai"));return f.format(new Date());}
 int count(){android.content.SharedPreferences p=getSharedPreferences("navigation-trial-budget",0);return NavigationTrialBudget.used(p.getString("day",""),p.getInt("count",0),today());}
 void updateBudget(){online.setEnabled(!busy&&count()<5);online.setText("算路并模拟 60 秒（今日余 "+Math.max(0,5-count())+" 次）");}
 void consent(){
  if(!NavigationTrialBudget.allowed(freeConfirmed.isChecked(),busy,count())){state.setText("请先核对免费配额；今日上限为5次");return;}
  new AlertDialog.Builder(this).setTitle("启动一次联网试验").setMessage("同意本次接入高德导航SDK，并已阅读高德隐私政策。SDK会连接高德服务器，可能处理IP、设备信息和固定示例起终点。\n本次不读取你的当前位置，仅进行一条示例步行路线算路及最多60秒模拟。免费状态以高德账号实际权益和账单为准。").setNegativeButton("取消",null).setPositiveButton("同意并试验",(dialog,which)->begin()).show();
 }
 void begin(){
  if(!NavigationTrialBudget.allowed(freeConfirmed.isChecked(),busy,count()))return;
  int next=count()+1;if(!getSharedPreferences("navigation-trial-budget",0).edit().putString("day",today()).putInt("count",next).commit()){state.setText("无法记录试验次数，未启动服务");return;}
  stop("");busy=true;routeSent=false;navigating=false;closed=false;int token=++generation;updateBudget();state.setText("正在初始化高德，使用固定示例坐标");road.setText("联网算路试验 · 非实时定位");
  try{
   if(Build.SUPPORTED_64_BIT_ABIS.length==0)throw new UnsupportedOperationException();
   sdk=Class.forName("com.amap.api.navi.AMapNavi");
   privacy(Class.forName("com.amap.api.maps.MapsInitializer"));
   engine=sdk.getMethod("getInstance",Context.class).invoke(null,this);
   Class<?> contract=Class.forName("com.amap.api.navi.AMapNaviListener");
   listener=Proxy.newProxyInstance(contract.getClassLoader(),new Class<?>[]{contract},(proxy,method,args)->{
    if(method.getName().equals("hashCode"))return System.identityHashCode(proxy);
    if(method.getName().equals("equals"))return args!=null&&args.length==1&&proxy==args[0];
    if(method.getName().equals("toString"))return "NavigationTrialListener";
    ui.post(()->{if(token==generation&&!closed)event(method.getName(),args);});return null;
   });
   sdk.getMethod("addAMapNaviListener",contract).invoke(engine,listener);
   optional("setUseInnerVoice",false);optional("setTrafficStatusUpdateEnabled",false);optional("setTrafficInfoUpdateEnabled",false);optional("setTrafficSignalEnable",false);optional("setIsNaviTravelView",true);
   ui.postDelayed(()->{if(token==generation&&busy)stop("试验时限已到，服务已停止");},75000);
  }catch(Throwable error){stop("初始化失败（"+error.getClass().getSimpleName()+"），未重试");}
 }
 void optional(String name,boolean value){try{sdk.getMethod(name,boolean.class).invoke(engine,value);}catch(Exception ignored){}}
 void event(String name,Object[] args){try{
  if(name.equals("onInitNaviFailure")){stop("SDK初始化失败，未重试");return;}
  if(name.equals("onInitNaviSuccess")&&!routeSent){
   routeSent=true;state.setText("正在请求一条上海示例步行路线");
   Class<?> point=Class.forName("com.amap.api.navi.model.NaviLatLng");
   Object start=point.getConstructor(double.class,double.class).newInstance(31.230416,121.473701);
   Object end=point.getConstructor(double.class,double.class).newInstance(31.240000,121.490000);
   boolean accepted=(Boolean)sdk.getMethod("calculateWalkRoute",point,point).invoke(engine,start,end);
   if(!accepted)stop("算路请求未被接受，未重试");
  }else if(name.equals("onCalculateRouteFailure")){
   String code="未知";if(args!=null&&args.length>0){if(args[0] instanceof Integer)code=args[0].toString();else code=String.valueOf(invoke(args[0],"getErrorCode"));}
   stop("算路失败，错误码 "+code+"；不自动重试");
  }else if(name.equals("onCalculateRouteSuccess")&&!navigating){
   navigating=true;Object path=sdk.getMethod("getNaviPath").invoke(engine);remaining.setText("路线 "+invoke(path,"getAllLength")+" 米 · "+invoke(path,"getAllTime")+" 秒");
   boolean started=(Boolean)sdk.getMethod("startNavi",int.class).invoke(engine,2);
   if(!started){stop("模拟启动失败，未重试");return;}
   state.setText("高德模拟导航 · 不使用当前位置");final int token=generation;
   ui.postDelayed(()->{if(token==generation)stop("60秒模拟结束，服务已停止");},60000);
  }else if(name.equals("onNaviInfoUpdate")&&args!=null&&args.length>0){
   Object info=args[0];distance.setText(invoke(info,"getCurStepRetainDistance")+" 米");road.setText(String.valueOf(invoke(info,"getNextRoadName")));remaining.setText("剩余 "+invoke(info,"getPathRetainDistance")+" 米 · "+invoke(info,"getPathRetainTime")+" 秒");
   int icon=((Number)invoke(info,"getIconType")).intValue();arrow.direction=icon==2?-1:icon==3?1:0;arrow.invalidate();
   frame(1,NavigationFields.turn(icon),((Number)invoke(info,"getCurStepRetainDistance")).intValue(),((Number)invoke(info,"getPathRetainDistance")).intValue(),((Number)invoke(info,"getPathRetainTime")).intValue(),String.valueOf(invoke(info,"getNextRoadName")));
  }else if(name.equals("onEndEmulatorNavi")||name.equals("onArriveDestination"))stop("模拟已到达终点，服务已停止");
 }catch(Throwable error){stop("导航回调处理失败，服务已停止（"+error.getClass().getSimpleName()+"）");}}
 Object invoke(Object object,String method)throws Exception{return object.getClass().getMethod(method).invoke(object);}
 void privacy(Class<?> type)throws Exception{type.getMethod("updatePrivacyShow",Context.class,boolean.class,boolean.class).invoke(null,this,true,true);type.getMethod("updatePrivacyAgree",Context.class,boolean.class).invoke(null,this,true);}
 void locationConsent(){
  if(!NavigationTrialBudget.allowed(freeConfirmed.isChecked(),busy,count())){state.setText("请核对免费配额及今日剩余次数");return;}
  new AlertDialog.Builder(this).setTitle("单次在线定位").setMessage("同意高德定位隐私政策，并授权本次获取手机位置。SDK可能处理精确/大概位置、IP、Wi-Fi、基站和设备信息；显示坐标及精度，不反查地址。完成或15秒超时即停止，不在后台持续定位。").setNegativeButton("取消",null).setPositiveButton("同意并定位",(d,w)->{
   if(checkSelfPermission(android.Manifest.permission.ACCESS_FINE_LOCATION)!=PackageManager.PERMISSION_GRANTED&&checkSelfPermission(android.Manifest.permission.ACCESS_COARSE_LOCATION)!=PackageManager.PERMISSION_GRANTED){pendingLocation=true;requestPermissions(new String[]{android.Manifest.permission.ACCESS_FINE_LOCATION,android.Manifest.permission.ACCESS_COARSE_LOCATION},809);}else locate();
  }).show();
 }
 public void onRequestPermissionsResult(int request,String[] permissions,int[] results){super.onRequestPermissionsResult(request,permissions,results);if(request==809&&pendingLocation){pendingLocation=false;if(checkSelfPermission(android.Manifest.permission.ACCESS_FINE_LOCATION)==PackageManager.PERMISSION_GRANTED||checkSelfPermission(android.Manifest.permission.ACCESS_COARSE_LOCATION)==PackageManager.PERMISSION_GRANTED)locate();else state.setText("未授权定位，没有发起定位请求");}}
 @SuppressWarnings({"unchecked","rawtypes"}) void locate(){
  if(!NavigationTrialBudget.allowed(freeConfirmed.isChecked(),busy,count()))return;
  if(!getSharedPreferences("navigation-trial-budget",0).edit().putString("day",today()).putInt("count",count()+1).commit()){state.setText("无法记录次数，未定位");return;}
  stop("");busy=true;closed=false;final int token=++generation;updateBudget();state.setText("正在进行单次在线定位");
  try{
   Class<?> type=Class.forName("com.amap.api.location.AMapLocationClient");privacy(type);locationClient=type.getConstructor(Context.class).newInstance(this);
   Class<?> options=Class.forName("com.amap.api.location.AMapLocationClientOption");Object option=options.getConstructor().newInstance();
   options.getMethod("setOnceLocation",boolean.class).invoke(option,true);options.getMethod("setOnceLocationLatest",boolean.class).invoke(option,true);
   options.getMethod("setNeedAddress",boolean.class).invoke(option,false);options.getMethod("setHttpTimeOut",long.class).invoke(option,10000L);options.getMethod("setSelfStartServiceEnable",boolean.class).invoke(option,false);
   Class<? extends Enum> protocol=(Class<? extends Enum>)Class.forName("com.amap.api.location.AMapLocationClientOption$AMapLocationProtocol");options.getMethod("setLocationProtocol",protocol).invoke(null,Enum.valueOf(protocol,"HTTPS"));
   type.getMethod("setLocationOption",options).invoke(locationClient,option);
   Class<?> contract=Class.forName("com.amap.api.location.AMapLocationListener");locationListener=Proxy.newProxyInstance(contract.getClassLoader(),new Class<?>[]{contract},(proxy,method,args)->{
    if(method.getName().equals("hashCode"))return System.identityHashCode(proxy);if(method.getName().equals("equals"))return args!=null&&args.length==1&&args[0]==proxy;if(method.getName().equals("toString"))return "SingleLocationListener";
    if(method.getName().equals("onLocationChanged")&&args!=null&&args.length>0){Object value=args[0];ui.post(()->{if(token!=generation||closed)return;try{int code=((Number)invoke(value,"getErrorCode")).intValue();if(code!=0){stop("定位失败，错误码 "+code+"；不自动重试");return;}distance.setText(String.format(Locale.US,"%.6f",((Number)invoke(value,"getLatitude")).doubleValue()));road.setText(String.format(Locale.US,"经度 %.6f",((Number)invoke(value,"getLongitude")).doubleValue()));remaining.setText("定位精度约 "+invoke(value,"getAccuracy")+" 米；坐标仅在手机显示");stop("单次定位完成，已停止定位");}catch(Throwable error){stop("定位结果处理失败，已停止");}});}return null;
   });
   type.getMethod("setLocationListener",contract).invoke(locationClient,locationListener);type.getMethod("startLocation").invoke(locationClient);
   ui.postDelayed(()->{if(token==generation)stop("15秒定位超时，已停止，不自动重试");},15000);
  }catch(Throwable error){stop("定位初始化失败（"+error.getClass().getSimpleName()+"），未重试");}
 }
 void stop(String message){
  endRelay();
  ++generation;closed=true;busy=false;Object previous=engine;Class<?> previousSdk=sdk;engine=null;
  if(locationClient!=null){Object location=locationClient;locationClient=null;try{location.getClass().getMethod("stopLocation").invoke(location);}catch(Throwable ignored){}try{location.getClass().getMethod("onDestroy").invoke(location);}catch(Throwable ignored){}locationListener=null;}
  if(previous!=null){try{previousSdk.getMethod("stopNavi").invoke(previous);}catch(Throwable ignored){}
   try{previousSdk.getMethod("removeAMapNaviListener",Class.forName("com.amap.api.navi.AMapNaviListener")).invoke(previous,listener);}catch(Throwable ignored){}
   try{previousSdk.getMethod("destroy").invoke(previous);}catch(Throwable ignored){}}
  listener=null;if(state!=null&&!message.isEmpty())state.setText(message);if(online!=null)updateBudget();
 }
 void frame(int source,int turn,int meters,int remain,int seconds,String name){
  if(relayPhase==2){relaySession="";relaySequence=0;}
  relaySource=source;relayTurn=turn;relayDistance=Math.max(0,Math.min(100000,meters));relayRemaining=Math.max(0,Math.min(1000000,remain));relaySeconds=Math.max(0,Math.min(604800,seconds));relayRoad=NavigationFields.road(name);relayPhase=0;relayValid=true;sendRelay();
 }
 void sendRelay(){
  if(!relayValid||relayWaiting||relayEnabled==null||!relayEnabled.isChecked()&&relayPhase!=2)return;
  NavigationLink.Transport link=NavigationLink.transport;
  if(link==null||!link.available()){relayStatus.setText("未连接可同步设备，请先连接蓝牙（需 s3.64）");return;}
  if(relaySession.isEmpty()){if(relayPhase==2){relayValid=false;return;}relaySession=UUID.randomUUID().toString().replace("-","").substring(0,16);relaySequence=0;}
  final String session=relaySession;final int next=relaySequence+1,phase=relayPhase;
  JSONObject packet=MainActivity.json("cmd","nav","s",session,"q",next,"m",relaySource,"t",relayTurn,"d",relayDistance,"r",relayRemaining,"e",relaySeconds,"n",relayRoad,"z",phase);
  if(packet.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8).length>256){relayStatus.setText("道路数据过长，未发送");return;}
  relayWaiting=true;
  boolean accepted=link.send(packet,error->{
   relayWaiting=false;
   if(!relaySession.equals(session))return;
   if(error!=null){relayValid=false;relaySession="";relayStatus.setText("同步停止："+error+"；请重新开始演示");return;}
   relaySequence=next;relayStatus.setText(phase==2?"设备已停止显示指引":"设备已同步 · "+(relaySource==0?"离线演示":"高德模拟"));
   if(phase==2){relayValid=false;relaySession="";}else if(relayPhase==2)sendRelay();
  });
  if(!accepted){relayWaiting=false;relayStatus.setText("等待蓝牙通道空闲");}
 }
 void endRelay(){relayPhase=2;if(relayValid&&!relaySession.isEmpty())sendRelay();else relayValid=false;}
 void offline(){stop("离线演示 · 未连接高德服务器");closed=false;int token=++generation;int[] turns={0,-1,0,1,0};
  for(int i=0;i<turns.length;i++){final int step=i;ui.postDelayed(()->{if(token!=generation)return;arrow.direction=turns[step];arrow.invalidate();distance.setText((200-step*35)+" 米");road.setText("示例道路 "+(step+1)+" · 模拟数据");remaining.setText("仅验证界面，不代表真实导航");frame(0,turns[step]<0?1:turns[step]>0?2:0,200-step*35,1500-step*250,900-step*150,"示例道路 "+(step+1));},i*10000L);}
  ui.postDelayed(()->{if(token==generation)stop("60秒离线演示结束");},60000);}
 protected void onResume(){super.onResume();foreground=true;ui.removeCallbacks(heartbeat);ui.post(heartbeat);}
 protected void onStop(){foreground=false;ui.removeCallbacks(heartbeat);pendingLocation=false;stop("页面已离开，导航停止");super.onStop();}
 protected void onDestroy(){stop("");ui.removeCallbacksAndMessages(null);super.onDestroy();}
 static class Arrow extends View{int direction=0;Paint paint=new Paint(3);Arrow(Context c){super(c);}protected void onDraw(Canvas c){super.onDraw(c);c.save();c.translate(getWidth()/2f,getHeight()/2f);float k=Math.min(getWidth(),getHeight())/180f;c.scale(k,k);if(direction!=0)c.rotate(direction*90);paint.setColor(0xff71ddc9);paint.setStrokeWidth(15);paint.setStrokeCap(Paint.Cap.ROUND);paint.setStyle(Paint.Style.STROKE);Path path=new Path();path.moveTo(0,60);path.lineTo(0,-60);path.moveTo(-40,-20);path.lineTo(0,-60);path.lineTo(40,-20);c.drawPath(path,paint);c.restore();}}
}
