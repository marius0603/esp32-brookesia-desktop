package com.xiaoma.remote;
import android.Manifest;
import android.app.*;
import android.os.*;
import android.bluetooth.*;
import android.bluetooth.le.*;
import android.content.pm.PackageManager;
import android.content.res.ColorStateList;
import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.view.*;
import android.widget.*;
import org.json.*;
import java.util.*;
import java.util.concurrent.*;

/** Three native pages share one serialized authenticated GATT session. */
public class MainActivity extends Activity {
 static final UUID SERVICE=UUID.fromString("1775244d-6b43-439b-877c-060f2d9bed07");
 static UUID endpoint(int n){return UUID.fromString(String.format("1775ff%02x-6b43-439b-877c-060f2d9bed07",n));}
 final Handler ui=new Handler(Looper.getMainLooper());final ExecutorService jobs=Executors.newSingleThreadExecutor();
 final Object gate=new Object();byte[] reply;boolean finished;int ioStatus;
 BluetoothAdapter adapter;BluetoothLeScanner scanner;BluetoothGatt gatt,workerGatt;Protocol protocol;
 volatile boolean connected=false,busy=false,destroyed=false;boolean resumed=false,tracking=false;int selectedTab=0;
 LinearLayout root,devices,apps,stories,connectionForm,pairedRow;TextView status,storyTitle,storyState,storyTime,appPages,storyPages;EditText code;
 SeekBar volume,brightness;ScrollView[] pages=new ScrollView[3];Button[] tabs=new Button[3],modeButtons=new Button[3];
 int appPage=-1,storyPage=-1,appTotal=0,storyTotal=0,scanGeneration=0;
 int ink=Color.rgb(240,246,255),muted=Color.rgb(148,165,189),accent=Color.rgb(98,231,192),panel=Color.rgb(21,32,49),back=Color.rgb(9,16,28);
 final String[] modes={"sequence","random","repeat_one"};
 void text(String value){ui.post(()->status.setText(value));}
 int dp(int n){return Math.round(n*getResources().getDisplayMetrics().density);}
 GradientDrawable shape(int color,int radius){GradientDrawable d=new GradientDrawable();d.setColor(color);d.setCornerRadius(dp(radius));return d;}
 TextView label(String value,int size){TextView t=new TextView(this);t.setText(value);t.setTextColor(ink);t.setTextSize(size);t.setPadding(0,dp(6),0,dp(6));return t;}
 LinearLayout column(){LinearLayout v=new LinearLayout(this);v.setOrientation(1);return v;}
 LinearLayout row(){LinearLayout v=new LinearLayout(this);v.setGravity(Gravity.CENTER_VERTICAL);return v;}
 Button button(LinearLayout parent,String title,Runnable action){Button b=new Button(this);b.setText(title);b.setTextColor(ink);b.setTextSize(16);b.setAllCaps(false);b.setBackground(shape(Color.rgb(30,46,65),14));LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,dp(52));p.setMargins(0,dp(5),0,dp(5));parent.addView(b,p);b.setOnClickListener(v->action.run());return b;}
 Button cell(LinearLayout parent,String title,Runnable action){Button b=button(parent,title,action);LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(0,dp(54),1);p.setMargins(dp(3),dp(5),dp(3),dp(5));b.setLayoutParams(p);return b;}
 LinearLayout card(LinearLayout parent){LinearLayout v=column();v.setPadding(dp(16),dp(12),dp(16),dp(14));v.setBackground(shape(panel,20));LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,-2);p.setMargins(0,dp(7),0,dp(7));parent.addView(v,p);return v;}
 public void onCreate(Bundle state){super.onCreate(state);getWindow().setStatusBarColor(back);getWindow().setNavigationBarColor(back);
  root=column();root.setFitsSystemWindows(true);root.setBackgroundColor(back);root.setPadding(dp(16),dp(10),dp(16),dp(10));setContentView(root);
  TextView heading=label("小马遥控",28);heading.setTypeface(null,1);root.addView(heading);status=label("未连接设备",14);status.setTextColor(muted);root.addView(status);
  LinearLayout connection=card(root);connectionForm=column();connection.addView(connectionForm);LinearLayout input=row();connectionForm.addView(input);
  code=new EditText(this);code.setSingleLine(true);code.setTextSize(21);code.setHint("4 位配对码");code.setHintTextColor(muted);code.setTextColor(ink);code.setInputType(android.text.InputType.TYPE_CLASS_NUMBER);code.setFilters(new android.text.InputFilter[]{new android.text.InputFilter.LengthFilter(4)});input.addView(code,new LinearLayout.LayoutParams(0,dp(54),1));
  Button scan=cell(input,"扫描",()->scan());scan.setTextColor(accent);devices=column();connectionForm.addView(devices);
  pairedRow=row();connection.addView(pairedRow);TextView paired=label("蓝牙已连接",16);paired.setTextColor(accent);pairedRow.addView(paired,new LinearLayout.LayoutParams(0,-2,1));cell(pairedRow,"断开",()->disconnect());pairedRow.setVisibility(View.GONE);
  FrameLayout body=new FrameLayout(this);root.addView(body,new LinearLayout.LayoutParams(-1,0,1));LinearLayout[] content=new LinearLayout[3];
  for(int i=0;i<3;i++){pages[i]=new ScrollView(this);pages[i].setFillViewport(true);pages[i].setClipToPadding(false);content[i]=column();content[i].setPadding(0,dp(6),0,dp(12));pages[i].addView(content[i]);body.addView(pages[i]);}
  LinearLayout sound=card(content[0]);sound.addView(label("声音与屏幕",20));volume=slider(sound,"音量",0,"volume");brightness=slider(sound,"亮度",10,"brightness");
  LinearLayout screen=card(content[0]);screen.addView(label("屏幕控制",20));LinearLayout screenActions=row();screen.addView(screenActions);cell(screenActions,"息屏",()->simple("sleep"));cell(screenActions,"唤醒",()->simple("wake"));cell(screenActions,"锁屏",()->new AlertDialog.Builder(this).setTitle("锁定设备屏幕？").setMessage("解锁时，在设备上快速连按两次音量＋。").setPositiveButton("锁屏",(d,w)->simple("lock")).setNegativeButton("取消",null).show());button(screen,"刷新状态",()->refreshStatus());
  LinearLayout now=card(content[1]);now.setBackground(shape(Color.rgb(19,57,56),22));TextView playing=label("听书",14);playing.setTextColor(accent);now.addView(playing);storyTitle=label("选择一篇故事",25);storyTitle.setTypeface(null,1);now.addView(storyTitle);storyState=label("等待播放",15);storyState.setTextColor(muted);now.addView(storyState);storyTime=label("00:00",18);now.addView(storyTime);
  LinearLayout transport=row();now.addView(transport);cell(transport,"暂停",()->simple("pause"));cell(transport,"继续",()->simple("resume"));cell(transport,"停止",()->simple("stop"));
  LinearLayout mode=card(content[1]);mode.addView(label("播放方式",18));LinearLayout choices=row();mode.addView(choices);String[] names={"顺序播放","随机播放","单故事循环"};for(int i=0;i<3;i++){final int index=i;modeButtons[i]=cell(choices,names[i],()->command(json("cmd","mode","value",modes[index]),r->{selectMode(modes[index]);laterRefresh();}));modeButtons[i].setTextSize(13);modeButtons[i].setCompoundDrawablesWithIntrinsicBounds(null,new ModeIcon(this,i,accent),null,null);modeButtons[i].getLayoutParams().height=dp(80);}
  LinearLayout library=card(content[1]);library.addView(label("故事书架",20));stories=column();library.addView(stories);storyPages=label("连接设备后查看故事",14);storyPages.setTextColor(muted);library.addView(storyPages);LinearLayout storyNav=row();library.addView(storyNav);cell(storyNav,"上一页",()->loadStoriesPage(Math.max(0,storyPage-1)));cell(storyNav,"下一页",()->loadStoriesPage(Math.min(Math.max(0,(storyTotal-1)/3),Math.max(0,storyPage+1))));
  LinearLayout launcher=card(content[2]);launcher.addView(label("设备应用",21));apps=column();launcher.addView(apps);appPages=label("连接设备后查看应用",14);appPages.setTextColor(muted);launcher.addView(appPages);LinearLayout appNav=row();launcher.addView(appNav);cell(appNav,"上一页",()->loadAppsPage(Math.max(0,appPage-1)));cell(appNav,"下一页",()->loadAppsPage(Math.min(Math.max(0,(appTotal-1)/3),Math.max(0,appPage+1))));
  LinearLayout navigation=row();root.addView(navigation);String[] labels={"遥控","听书","应用"};for(int i=0;i<3;i++){final int tab=i;tabs[i]=cell(navigation,labels[i],()->showTab(tab));}selectMode("sequence");showTab(0);adapter=((BluetoothManager)getSystemService(BLUETOOTH_SERVICE)).getAdapter();
 }
 void showTab(int tab){selectedTab=tab;for(int i=0;i<3;i++){pages[i].setVisibility(i==tab?View.VISIBLE:View.GONE);tabs[i].setTextColor(i==tab?accent:muted);tabs[i].setBackground(shape(i==tab?Color.rgb(24,57,59):back,16));}if(connected){if(tab==1&&storyPage<0)loadStoriesPage(0);if(tab==2&&appPage<0)loadAppsPage(0);}}
 void setConnectedUi(boolean value){connectionForm.setVisibility(value?View.GONE:View.VISIBLE);pairedRow.setVisibility(value?View.VISIBLE:View.GONE);}
 SeekBar slider(LinearLayout parent,String title,int minimum,String cmd){TextView t=label(title,16);parent.addView(t);SeekBar bar=new SeekBar(this);bar.setMax(100);bar.setMin(minimum);bar.setProgressTintList(ColorStateList.valueOf(accent));bar.setThumbTintList(ColorStateList.valueOf(accent));parent.addView(bar,new LinearLayout.LayoutParams(-1,dp(52)));bar.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener(){public void onStartTrackingTouch(SeekBar b){tracking=true;}public void onProgressChanged(SeekBar b,int p,boolean user){t.setText(title+"  "+p+"%");}public void onStopTrackingTouch(SeekBar b){tracking=false;command(json("cmd",cmd,"value",b.getProgress()),r->{});}});return bar;}
 static JSONObject json(Object... parts){JSONObject r=new JSONObject();try{for(int i=0;i<parts.length;i+=2)r.put((String)parts[i],parts[i+1]);}catch(Exception e){throw new IllegalArgumentException(e);}return r;}
 interface Result{void accept(JSONObject response)throws Exception;}
 void simple(String cmd){command(json("cmd",cmd),r->laterRefresh());}
 void laterRefresh(){ui.postDelayed(()->{if(connected&&!busy)refreshStatus();},250);}
 void command(JSONObject request,Result action){if(!connected){text("请先输入配对码并连接设备");return;}if(busy){text("正在处理，请稍候");return;}busy=true;BluetoothGatt owner=gatt;
  jobs.execute(()->{workerGatt=owner;try{byte[] raw=exchange(0x55,protocol.crypt(request.toString().getBytes("UTF-8")));JSONObject response=new JSONObject(new String(protocol.crypt(raw),"UTF-8"));if(!response.optBoolean("ok")){text(response.optString("error","操作未完成"));return;}ui.post(()->{if(gatt!=owner)return;try{status.setText("已连接");action.accept(response);}catch(Exception e){text("设备回复格式异常");}});}catch(Exception e){if(gatt==owner){disconnect();text("连接中断，请重新扫描并输入配对码");}}finally{busy=false;}});
 }
 void refreshStatus(){command(json("cmd","status"),r->{update(r);ui.post(()->{if(selectedTab==1&&storyPage<0)loadStoriesPage(0);else if(selectedTab==2&&appPage<0)loadAppsPage(0);});});}
 void selectMode(String value){for(int i=0;i<3;i++){boolean chosen=modes[i].equals(value);modeButtons[i].setTextColor(chosen?accent:muted);modeButtons[i].setBackground(shape(chosen?Color.rgb(25,66,62):Color.rgb(30,46,65),13));}}
 String clock(int value){return String.format(Locale.ROOT,"%02d:%02d",Math.max(0,value)/60,Math.max(0,value)%60);}
 void update(JSONObject r){if(!tracking){volume.setProgress(r.optInt("volume",75));brightness.setProgress(r.optInt("brightness",80));}selectMode(r.optString("play_mode","sequence"));String title=r.optString("story_title","");if(!title.isEmpty())storyTitle.setText(title);storyTime.setText(clock(r.optInt("story_position",0)));String state=r.optString("story_state","");storyState.setText(state.equals("Paused")?"已暂停":r.optBoolean("story_active")?"正在播放":"已停止");if(r.optBoolean("locked"))text("设备已锁屏，需双按设备音量＋解锁");}
 void loadAppsPage(int page){command(json("cmd","apps","page",page),r->{appPage=page;appTotal=r.optInt("total",page*3+r.getJSONArray("items").length());apps.removeAllViews();JSONArray items=r.getJSONArray("items");for(int i=0;i<items.length();i++){JSONObject item=items.getJSONObject(i);int id=item.getInt("id");button(apps,item.getString("name"),()->command(json("cmd","open","id",id),v->{}));}appPages.setText("第 "+(page+1)+" / "+Math.max(1,(appTotal+2)/3)+" 页");});}
 void loadStoriesPage(int page){command(json("cmd","stories","page",page),r->{storyPage=page;storyTotal=r.optInt("total",page*3+r.getJSONArray("items").length());stories.removeAllViews();JSONArray items=r.getJSONArray("items");for(int i=0;i<items.length();i++){JSONObject item=items.getJSONObject(i);int id=item.getInt("id");button(stories,String.format(Locale.ROOT,"%02d  %s",id+1,item.getString("name")),()->command(json("cmd","play","id",id),v->{storyTitle.setText(item.optString("name"));laterRefresh();}));}storyPages.setText("第 "+(page+1)+" / "+Math.max(1,(storyTotal+2)/3)+" 页");});}
 final Runnable poller=new Runnable(){public void run(){if(resumed&&!destroyed){if(connected&&!busy&&!tracking)refreshStatus();ui.postDelayed(this,3000);}}};
 protected void onResume(){super.onResume();resumed=true;ui.removeCallbacks(poller);ui.postDelayed(poller,1000);}
 protected void onPause(){resumed=false;ui.removeCallbacks(poller);super.onPause();}
 final Set<String> found=new HashSet<>();
 final ScanCallback scans=new ScanCallback(){public void onScanResult(int type,ScanResult result){BluetoothDevice device=result.getDevice();String name=result.getScanRecord()==null?null:result.getScanRecord().getDeviceName();if(name==null||!name.startsWith("CTRL_")||!found.add(device.getAddress()))return;String title=name;ui.post(()->button(devices,title,()->connect(device)));}public void onScanFailed(int error){text("扫描失败，请检查蓝牙开关和附近设备权限");}};
 void scan(){if(Build.VERSION.SDK_INT>=31){if(checkSelfPermission(Manifest.permission.BLUETOOTH_SCAN)!=PackageManager.PERMISSION_GRANTED||checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT)!=PackageManager.PERMISSION_GRANTED){requestPermissions(new String[]{Manifest.permission.BLUETOOTH_SCAN,Manifest.permission.BLUETOOTH_CONNECT},7);return;}}
  else if(checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION)!=PackageManager.PERMISSION_GRANTED){requestPermissions(new String[]{Manifest.permission.ACCESS_FINE_LOCATION},7);return;}
  if(adapter==null||!adapter.isEnabled()){text("请先打开手机蓝牙");return;}disconnect();found.clear();devices.removeAllViews();scanner=adapter.getBluetoothLeScanner();scanner.startScan(scans);text("正在扫描…请确认设备已开启蓝牙遥控");int generation=++scanGeneration;ui.postDelayed(()->{if(generation==scanGeneration){stopScan();if(found.isEmpty())text("未发现设备；旧版安卓还需开启系统定位");}},12000);
 }
 void stopScan(){++scanGeneration;if(scanner!=null){try{scanner.stopScan(scans);}catch(Exception e){}scanner=null;}}
 void connect(BluetoothDevice device){String pop=code.getText().toString().trim();if(!pop.matches("[0-9]{4}")){text("请输入设备当前显示的4位数字配对码");return;}stopScan();disconnect();apps.removeAllViews();stories.removeAllViews();text("正在连接设备…");protocol=new Protocol(pop);gatt=device.connectGatt(this,false,callbacks,BluetoothDevice.TRANSPORT_LE);ui.postDelayed(()->{if(!connected&&gatt!=null){disconnect();text("连接超时，请重新扫描");}},25000);}
 final BluetoothGattCallback callbacks=new BluetoothGattCallback(){
  public void onConnectionStateChange(BluetoothGatt g,int status,int state){if(g!=gatt)return;if(state==BluetoothProfile.STATE_CONNECTED&&status==0){if(!g.requestMtu(512))g.discoverServices();}else if(state==BluetoothProfile.STATE_DISCONNECTED){connected=false;signal(null,-1);g.close();if(g==gatt)gatt=null;text("已断开连接");ui.post(()->setConnectedUi(false));}}
  public void onMtuChanged(BluetoothGatt g,int mtu,int status){if(g==gatt)g.discoverServices();}
  public void onServicesDiscovered(BluetoothGatt g,int gattStatus){if(g!=gatt)return;if(gattStatus!=0||g.getService(SERVICE)==null||g.getService(SERVICE).getCharacteristic(endpoint(0x55))==null){disconnect();text("设备未开启蓝牙遥控，或固件版本过旧");return;}busy=true;jobs.execute(()->{workerGatt=g;try{byte[] r=exchange(0x51,protocol.hello());r=exchange(0x51,protocol.prove(r));protocol.verify(r);if(gatt!=g)throw new Exception();connected=true;busy=false;ui.post(()->{code.setText("");appPage=storyPage=-1;setConnectedUi(true);status.setText("已连接 · 加密蓝牙通道");refreshStatus();});}catch(Exception e){if(gatt==g){disconnect();text("配对失败，请核对设备上的配对码");}}finally{busy=false;}});}
  public void onCharacteristicWrite(BluetoothGatt g,BluetoothGattCharacteristic c,int status){if(g!=gatt)return;if(status!=0||!g.readCharacteristic(c))signal(null,-1);}
  public void onCharacteristicRead(BluetoothGatt g,BluetoothGattCharacteristic c,byte[] value,int status){if(g==gatt)signal(value,status);}
  @SuppressWarnings("deprecation") public void onCharacteristicRead(BluetoothGatt g,BluetoothGattCharacteristic c,int status){if(g==gatt)signal(c.getValue(),status);}
 };
 void signal(byte[] value,int status){synchronized(gate){reply=value;ioStatus=status;finished=true;gate.notifyAll();}}
 @SuppressWarnings("deprecation") byte[] exchange(int ep,byte[] data)throws Exception{synchronized(gate){finished=false;reply=null;BluetoothGatt g=workerGatt;if(g==null||g!=gatt)throw new Exception();BluetoothGattCharacteristic c=g.getService(SERVICE).getCharacteristic(endpoint(ep));c.setWriteType(BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT);c.setValue(data);if(!g.writeCharacteristic(c))throw new Exception();long deadline=SystemClock.elapsedRealtime()+15000;while(!finished){long left=deadline-SystemClock.elapsedRealtime();if(left<=0)throw new Exception("timeout");gate.wait(left);}if(ioStatus!=0||reply==null)throw new Exception("GATT");return reply;}}
 void disconnect(){stopScan();connected=false;BluetoothGatt g=gatt;gatt=null;if(g!=null){try{g.disconnect();g.close();}catch(Exception e){}}signal(null,-1);if(!destroyed){text("已断开连接");ui.post(()->setConnectedUi(false));}}
 protected void onDestroy(){destroyed=true;ui.removeCallbacks(poller);disconnect();jobs.shutdownNow();super.onDestroy();}
 public void onRequestPermissionsResult(int request,String[] permissions,int[] results){super.onRequestPermissionsResult(request,permissions,results);if(request==7&&results.length>0&&Arrays.stream(results).allMatch(v->v==PackageManager.PERMISSION_GRANTED))scan();else text("请允许附近设备权限后重新扫描");}
}
