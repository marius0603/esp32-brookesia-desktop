package com.xiaoma.remote;
import android.Manifest;
import android.app.*;
import android.os.*;
import android.bluetooth.*;
import android.bluetooth.le.*;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.view.*;
import android.widget.*;
import org.json.*;
import java.util.*;
import java.util.concurrent.*;

/** One serialized GATT exchange at a time: Security 1 cipher state is shared. */
public class MainActivity extends Activity {
 static final UUID SERVICE=UUID.fromString("1775244d-6b43-439b-877c-060f2d9bed07");
 static UUID endpoint(int n){return UUID.fromString(String.format("1775ff%02x-6b43-439b-877c-060f2d9bed07",n));}
 final Handler ui=new Handler(Looper.getMainLooper());
 final ExecutorService jobs=Executors.newSingleThreadExecutor();
 final Object gate=new Object();byte[] reply;boolean finished;int ioStatus;
 BluetoothAdapter adapter;BluetoothLeScanner scanner;BluetoothGatt gatt,workerGatt;
 Protocol protocol;volatile boolean connected=false,busy=false,destroyed=false;
 LinearLayout root,devices,apps,stories;TextView status;EditText code;
 SeekBar volume,brightness;int appPage=-1,storyPage=-1,scanGeneration=0;
 int ink=Color.rgb(235,241,255),muted=Color.rgb(155,174,201);
 void text(String value){ui.post(()->status.setText(value));}
 TextView label(String value,int size){TextView t=new TextView(this);t.setText(value);t.setTextColor(ink);t.setTextSize(size);t.setPadding(8,12,8,8);return t;}
 int dp(int n){return Math.round(n*getResources().getDisplayMetrics().density);}
 Button button(LinearLayout parent,String title,Runnable action){Button b=new Button(this);b.setText(title);b.setTextColor(ink);b.setAllCaps(false);parent.addView(b,new LinearLayout.LayoutParams(-1,dp(54)));b.setOnClickListener(v->action.run());return b;}
 LinearLayout section(String title){root.addView(label(title,21));LinearLayout box=new LinearLayout(this);box.setOrientation(1);root.addView(box);return box;}
 public void onCreate(Bundle state){super.onCreate(state);getWindow().setStatusBarColor(Color.rgb(11,18,32));
  ScrollView scroll=new ScrollView(this);scroll.setBackgroundColor(Color.rgb(11,18,32));root=new LinearLayout(this);root.setOrientation(1);root.setPadding(dp(20),dp(20),dp(20),dp(28));scroll.addView(root);setContentView(scroll);
  root.addView(label("小马遥控",32));status=label("在设备上开启蓝牙遥控，然后扫描连接",16);root.addView(status);
  code=new EditText(this);code.setSingleLine(true);code.setHint("输入设备显示的 8 位配对码");code.setHintTextColor(muted);code.setTextColor(ink);code.setInputType(0x1001);root.addView(code);
  button(root,"扫描设备",()->scan());button(root,"断开连接",()->disconnect());devices=section("附近设备");
  LinearLayout sound=section("音量与亮度");volume=slider(sound,"音量",0,"volume");brightness=slider(sound,"亮度",10,"brightness");
  button(sound,"刷新设备状态",()->command(json("cmd","status"),r->update(r)));
  apps=section("打开应用");button(root,"查看应用 / 下一页",()->loadApps(true));stories=section("听书");button(root,"查看故事 / 下一页",()->loadStories(true));
  LinearLayout playback=section("播放控制");button(playback,"暂停",()->simple("pause"));button(playback,"继续播放",()->simple("resume"));button(playback,"停止播放",()->simple("stop"));
  LinearLayout screen=section("屏幕");button(screen,"息屏",()->simple("sleep"));button(screen,"唤醒屏幕",()->simple("wake"));button(screen,"锁屏",()->new AlertDialog.Builder(this).setTitle("锁定设备屏幕？").setMessage("锁定后需在设备上快速连按两次音量＋解锁。").setPositiveButton("锁屏",(d,w)->simple("lock")).setNegativeButton("取消",null).show());
  adapter=((BluetoothManager)getSystemService(BLUETOOTH_SERVICE)).getAdapter();
 }
 SeekBar slider(LinearLayout parent,String title,int minimum,String cmd){TextView t=label(title,17);parent.addView(t);SeekBar s=new SeekBar(this);s.setMax(100);s.setMin(minimum);parent.addView(s,new LinearLayout.LayoutParams(-1,dp(55)));s.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener(){public void onStartTrackingTouch(SeekBar b){}public void onProgressChanged(SeekBar b,int p,boolean user){t.setText(title+"  "+p+"%");}public void onStopTrackingTouch(SeekBar b){command(json("cmd",cmd,"value",b.getProgress()),r->{});}});return s;}
 static JSONObject json(Object... parts){JSONObject r=new JSONObject();try{for(int i=0;i<parts.length;i+=2)r.put((String)parts[i],parts[i+1]);}catch(Exception e){throw new IllegalArgumentException(e);}return r;}
 interface Result{void accept(JSONObject response)throws Exception;}
 void simple(String cmd){command(json("cmd",cmd),r->{});}
 void command(JSONObject request,Result action){if(!connected){text("请先扫描、输入配对码并连接设备");return;}if(busy){text("正在处理，请稍候");return;}busy=true;BluetoothGatt owner=gatt;
  jobs.execute(()->{workerGatt=owner;try{byte[] raw=exchange(0x55,protocol.crypt(request.toString().getBytes("UTF-8")));JSONObject response=new JSONObject(new String(protocol.crypt(raw),"UTF-8"));if(!response.optBoolean("ok")){text(response.optString("error","操作未完成"));return;}ui.post(()->{if(gatt!=owner)return;try{status.setText("已连接 · 操作成功");action.accept(response);}catch(Exception e){text("设备回复格式异常");}});}catch(Exception e){if(gatt==owner){disconnect();text("连接中断，请重新扫描并输入配对码");}}finally{busy=false;}});
 }
 void update(JSONObject r){volume.setProgress(r.optInt("volume",75));brightness.setProgress(r.optInt("brightness",80));if(r.optBoolean("locked"))text("设备已锁屏，需双按设备音量＋解锁");}
 void loadApps(boolean next){if(next)appPage++;command(json("cmd","apps","page",appPage),r->{apps.removeAllViews();JSONArray a=r.getJSONArray("items");for(int i=0;i<a.length();i++){JSONObject item=a.getJSONObject(i);int id=item.getInt("id");button(apps,item.getString("name"),()->command(json("cmd","open","id",id),v->{}));}if(!r.optBoolean("more"))appPage=-1;});}
 void loadStories(boolean next){if(next)storyPage++;command(json("cmd","stories","page",storyPage),r->{stories.removeAllViews();JSONArray a=r.getJSONArray("items");for(int i=0;i<a.length();i++){JSONObject item=a.getJSONObject(i);int id=item.getInt("id");button(stories,item.getString("name"),()->command(json("cmd","play","id",id),v->{}));}if(!r.optBoolean("more"))storyPage=-1;});}
 final Set<String> found=new HashSet<>();
 final ScanCallback scans=new ScanCallback(){public void onScanResult(int type,ScanResult result){BluetoothDevice device=result.getDevice();String name=result.getScanRecord()==null?null:result.getScanRecord().getDeviceName();if(name==null||!name.startsWith("CTRL_")||!found.add(device.getAddress()))return;String title=name;ui.post(()->button(devices,title,()->connect(device)));}public void onScanFailed(int error){text("扫描失败，请检查蓝牙开关和附近设备权限");}};
 void scan(){if(Build.VERSION.SDK_INT>=31){if(checkSelfPermission(Manifest.permission.BLUETOOTH_SCAN)!=PackageManager.PERMISSION_GRANTED||checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT)!=PackageManager.PERMISSION_GRANTED){requestPermissions(new String[]{Manifest.permission.BLUETOOTH_SCAN,Manifest.permission.BLUETOOTH_CONNECT},7);return;}}
  else if(checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION)!=PackageManager.PERMISSION_GRANTED){requestPermissions(new String[]{Manifest.permission.ACCESS_FINE_LOCATION},7);return;}
  if(adapter==null||!adapter.isEnabled()){text("请先打开手机蓝牙");return;}disconnect();found.clear();devices.removeAllViews();scanner=adapter.getBluetoothLeScanner();scanner.startScan(scans);text("正在扫描…请确认设备已开启蓝牙遥控");int generation=++scanGeneration;ui.postDelayed(()->{if(generation==scanGeneration){stopScan();if(found.isEmpty())text("未发现设备；旧版安卓还需开启系统定位");}},12000);
 }
 void stopScan(){++scanGeneration;if(scanner!=null){try{scanner.stopScan(scans);}catch(Exception e){}scanner=null;}}
 void connect(BluetoothDevice device){String pop=code.getText().toString().trim().toUpperCase(Locale.ROOT);if(!pop.matches("[0-9A-F]{8}")){text("请输入设备当前显示的8位配对码");return;}stopScan();disconnect();apps.removeAllViews();stories.removeAllViews();text("正在连接设备…");protocol=new Protocol(pop);gatt=device.connectGatt(this,false,callbacks,BluetoothDevice.TRANSPORT_LE);ui.postDelayed(()->{if(!connected&&gatt!=null){disconnect();text("连接超时，请重新扫描");}},25000);}
 final BluetoothGattCallback callbacks=new BluetoothGattCallback(){
  public void onConnectionStateChange(BluetoothGatt g,int status,int state){if(g!=gatt)return;if(state==BluetoothProfile.STATE_CONNECTED&&status==0){if(!g.requestMtu(512))g.discoverServices();}else if(state==BluetoothProfile.STATE_DISCONNECTED){connected=false;signal(null,-1);g.close();if(g==gatt)gatt=null;text("已断开连接");}}
  public void onMtuChanged(BluetoothGatt g,int mtu,int status){if(g==gatt)g.discoverServices();}
  public void onServicesDiscovered(BluetoothGatt g,int gattStatus){if(g!=gatt)return;if(gattStatus!=0||g.getService(SERVICE)==null||g.getService(SERVICE).getCharacteristic(endpoint(0x55))==null){disconnect();text("设备未开启蓝牙遥控，或固件版本过旧");return;}busy=true;jobs.execute(()->{workerGatt=g;try{byte[] r=exchange(0x51,protocol.hello());r=exchange(0x51,protocol.prove(r));protocol.verify(r);if(gatt!=g)throw new Exception();connected=true;busy=false;ui.post(()->{code.setText("");appPage=storyPage=-1;status.setText("已连接 · 加密蓝牙通道");command(json("cmd","status"),v->update(v));});}catch(Exception e){if(gatt==g){disconnect();text("配对失败，请核对设备上的配对码");}}finally{busy=false;}});}
  public void onCharacteristicWrite(BluetoothGatt g,BluetoothGattCharacteristic c,int status){if(g!=gatt)return;if(status!=0||!g.readCharacteristic(c))signal(null,-1);}
  public void onCharacteristicRead(BluetoothGatt g,BluetoothGattCharacteristic c,byte[] value,int status){if(g==gatt)signal(value,status);}
  @SuppressWarnings("deprecation") public void onCharacteristicRead(BluetoothGatt g,BluetoothGattCharacteristic c,int status){if(g==gatt)signal(c.getValue(),status);}
 };
 void signal(byte[] value,int status){synchronized(gate){reply=value;ioStatus=status;finished=true;gate.notifyAll();}}
 @SuppressWarnings("deprecation") byte[] exchange(int ep,byte[] data)throws Exception{synchronized(gate){finished=false;reply=null;BluetoothGatt g=workerGatt;if(g==null||g!=gatt)throw new Exception();BluetoothGattCharacteristic c=g.getService(SERVICE).getCharacteristic(endpoint(ep));c.setWriteType(BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT);c.setValue(data);if(!g.writeCharacteristic(c))throw new Exception();long deadline=SystemClock.elapsedRealtime()+15000;while(!finished){long left=deadline-SystemClock.elapsedRealtime();if(left<=0)throw new Exception("timeout");gate.wait(left);}if(ioStatus!=0||reply==null)throw new Exception("GATT");return reply;}}
 void disconnect(){stopScan();connected=false;BluetoothGatt g=gatt;gatt=null;if(g!=null){try{g.disconnect();g.close();}catch(Exception e){}}signal(null,-1);if(!destroyed)text("已断开连接");}
 protected void onDestroy(){destroyed=true;disconnect();jobs.shutdownNow();super.onDestroy();}
 public void onRequestPermissionsResult(int request,String[] permissions,int[] results){super.onRequestPermissionsResult(request,permissions,results);if(request==7&&results.length>0&&Arrays.stream(results).allMatch(v->v==PackageManager.PERMISSION_GRANTED))scan();else text("请允许附近设备权限后重新扫描");}
}
