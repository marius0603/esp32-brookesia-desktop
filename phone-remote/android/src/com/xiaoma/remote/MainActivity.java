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

/** Five native pages share one serialized authenticated GATT session. */
public class MainActivity extends Activity {
 static final UUID SERVICE=UUID.fromString("1775244d-6b43-439b-877c-060f2d9bed07");
 static UUID endpoint(int n){return UUID.fromString(String.format("1775ff%02x-6b43-439b-877c-060f2d9bed07",n));}
 final Handler ui=new Handler(Looper.getMainLooper());final ExecutorService jobs=Executors.newSingleThreadExecutor();
 final Object gate=new Object();byte[] reply;boolean finished;int ioStatus;
 BluetoothAdapter adapter;BluetoothLeScanner scanner;BluetoothGatt gatt,workerGatt;Protocol protocol;
 volatile boolean connected=false,busy=false,destroyed=false;boolean resumed=false,tracking=false;int selectedTab=0;
 LinearLayout root,devices,apps,stories,connectionForm,pairedRow;TextView status,storyTitle,storyState,storyTime,appPages,storyPages;EditText code;
 Button speedButton,radioToggle,radioTimer;TextView radioTitle,radioState,radioDetail,radioNetwork,radioEmpty;
 LinearLayout radioStations;SeekBar radioVolume;Button[] radioCategories=new Button[3];
 final ArrayList<String> radioIds=new ArrayList<>(),radioNames=new ArrayList<>(),radioGroups=new ArrayList<>(),radioSubs=new ArrayList<>();
 String radioSelected="",radioCategory="儿童";boolean radioReady=false,radioSupported=false;
 TextView songTitle,songState,songTime,songPages;LinearLayout songRows;SeekBar songVolume;Button songToggle,songTimer;
 Button[] songModeButtons=new Button[3];boolean songsSupported=false;int songPage=-1,songTotal=0,selectedSongId=-1;
 SeekBar volume,brightness;ScrollView[] pages=new ScrollView[5];Button[] tabs=new Button[5],modeButtons=new Button[3];
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
  if(NavigationTrialActivity.enabled(this))button(root,"导航免费试验",()->startActivity(new android.content.Intent(this,NavigationTrialActivity.class)));
  LinearLayout connection=card(root);connectionForm=column();connection.addView(connectionForm);LinearLayout input=row();connectionForm.addView(input);
  code=new EditText(this);code.setSingleLine(true);code.setTextSize(21);code.setHint("4 位配对码");code.setHintTextColor(muted);code.setTextColor(ink);code.setInputType(android.text.InputType.TYPE_CLASS_NUMBER);code.setFilters(new android.text.InputFilter[]{new android.text.InputFilter.LengthFilter(4)});input.addView(code,new LinearLayout.LayoutParams(0,dp(54),1));
  Button scan=cell(input,"扫描",()->scan());scan.setTextColor(accent);devices=column();connectionForm.addView(devices);
  pairedRow=row();connection.addView(pairedRow);TextView paired=label("蓝牙已连接",16);paired.setTextColor(accent);pairedRow.addView(paired,new LinearLayout.LayoutParams(0,-2,1));cell(pairedRow,"断开",()->disconnect());pairedRow.setVisibility(View.GONE);
  FrameLayout body=new FrameLayout(this);root.addView(body,new LinearLayout.LayoutParams(-1,0,1));LinearLayout[] content=new LinearLayout[5];
  for(int i=0;i<5;i++){pages[i]=new ScrollView(this);pages[i].setFillViewport(true);pages[i].setClipToPadding(false);content[i]=column();content[i].setPadding(0,dp(6),0,dp(12));pages[i].addView(content[i]);body.addView(pages[i]);}
  LinearLayout sound=card(content[0]);sound.addView(label("声音与屏幕",20));volume=slider(sound,"音量",0,"volume");brightness=slider(sound,"亮度",10,"brightness");
  LinearLayout screen=card(content[0]);screen.addView(label("屏幕控制",20));LinearLayout screenActions=row();screen.addView(screenActions);cell(screenActions,"息屏",()->simple("sleep"));cell(screenActions,"唤醒",()->simple("wake"));cell(screenActions,"锁屏",()->new AlertDialog.Builder(this).setTitle("锁定设备屏幕？").setMessage("解锁时，在设备上快速连按两次音量＋。").setPositiveButton("锁屏",(d,w)->simple("lock")).setNegativeButton("取消",null).show());button(screen,"刷新状态",()->refreshStatus());
  LinearLayout now=card(content[1]);now.setBackground(shape(Color.rgb(19,57,56),22));TextView playing=label("听书",14);playing.setTextColor(accent);now.addView(playing);storyTitle=label("选择一篇故事",25);storyTitle.setTypeface(null,1);now.addView(storyTitle);storyState=label("等待播放",15);storyState.setTextColor(muted);now.addView(storyState);storyTime=label("00:00",18);now.addView(storyTime);
  LinearLayout transport=row();now.addView(transport);cell(transport,"暂停",()->simple("pause"));cell(transport,"继续",()->simple("resume"));cell(transport,"下一篇",()->nextStory());
  LinearLayout mode=card(content[1]);mode.addView(label("播放方式",18));LinearLayout choices=row();mode.addView(choices);String[] names={"顺序播放","随机播放","单故事循环"};for(int i=0;i<3;i++){final int index=i;modeButtons[i]=cell(choices,names[i],()->command(json("cmd","mode","value",modes[index]),r->{selectMode(modes[index]);laterRefresh();}));modeButtons[i].setTextSize(13);modeButtons[i].setCompoundDrawablesWithIntrinsicBounds(null,new ModeIcon(this,i,accent),null,null);modeButtons[i].getLayoutParams().height=dp(80);}
  speedButton=button(mode,"播放速度  1x",()->new AlertDialog.Builder(this).setTitle("播放速度").setItems(new String[]{"0.5x","0.75x","1x","1.25x","1.5x","2x"},(d,which)->{double[] speeds={0.5,0.75,1,1.25,1.5,2};command(json("cmd","speed","value",speeds[which]),r->laterRefresh());}).show());
  LinearLayout library=card(content[1]);library.addView(label("故事书架",20));stories=column();library.addView(stories);storyPages=label("连接设备后查看故事",14);storyPages.setTextColor(muted);library.addView(storyPages);LinearLayout storyNav=row();library.addView(storyNav);cell(storyNav,"上一页",()->loadStoriesPage(Math.max(0,storyPage-1)));cell(storyNav,"下一页",()->loadStoriesPage(Math.min(Math.max(0,(storyTotal-1)/3),Math.max(0,storyPage+1))));
  createSongsPage(content[2]);
  createRadioPage(content[3]);
  LinearLayout launcher=card(content[4]);launcher.addView(label("设备应用",21));apps=column();launcher.addView(apps);appPages=label("连接设备后查看应用",14);appPages.setTextColor(muted);launcher.addView(appPages);LinearLayout appNav=row();launcher.addView(appNav);cell(appNav,"上一页",()->loadAppsPage(Math.max(0,appPage-1)));cell(appNav,"下一页",()->loadAppsPage(Math.min(Math.max(0,(appTotal-1)/3),Math.max(0,appPage+1))));
  LinearLayout navigation=row();root.addView(navigation);String[] labels={"遥控","听书","儿歌","电台","应用"};for(int i=0;i<5;i++){final int tab=i;tabs[i]=cell(navigation,labels[i],()->showTab(tab));tabs[i].setTextSize(13);tabs[i].setMinWidth(0);tabs[i].setPadding(dp(2),0,dp(2),0);}selectMode("sequence");showTab(0);adapter=((BluetoothManager)getSystemService(BLUETOOTH_SERVICE)).getAdapter();
 }
 void showTab(int tab){selectedTab=tab;for(int i=0;i<5;i++){pages[i].setVisibility(i==tab?View.VISIBLE:View.GONE);tabs[i].setTextColor(i==tab?accent:muted);tabs[i].setBackground(shape(i==tab?Color.rgb(24,57,59):back,16));}if(connected){if(tab==1&&storyPage<0)loadStoriesPage(0);if(tab==2){if(songsSupported&&songPage<0)loadSongsPage(0);else laterRefresh();}if(tab==3){if(radioSupported&&!radioReady)loadRadioStations();else laterRefresh();}if(tab==4&&appPage<0)loadAppsPage(0);}}
 void setConnectedUi(boolean value){connectionForm.setVisibility(value?View.GONE:View.VISIBLE);pairedRow.setVisibility(value?View.VISIBLE:View.GONE);}
 SeekBar slider(LinearLayout parent,String title,int minimum,String cmd){TextView t=label(title,16);parent.addView(t);SeekBar bar=new SeekBar(this);bar.setMax(100);bar.setMin(minimum);bar.setProgressTintList(ColorStateList.valueOf(accent));bar.setThumbTintList(ColorStateList.valueOf(accent));parent.addView(bar,new LinearLayout.LayoutParams(-1,dp(52)));bar.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener(){public void onStartTrackingTouch(SeekBar b){tracking=true;}public void onProgressChanged(SeekBar b,int p,boolean user){t.setText(title+"  "+p+"%");}public void onStopTrackingTouch(SeekBar b){tracking=false;command(json("cmd",cmd,"value",b.getProgress()),r->{});}});return bar;}
 static JSONObject json(Object... parts){JSONObject r=new JSONObject();try{for(int i=0;i<parts.length;i+=2)r.put((String)parts[i],parts[i+1]);}catch(Exception e){throw new IllegalArgumentException(e);}return r;}
 interface Result{void accept(JSONObject response)throws Exception;}
 void simple(String cmd){command(json("cmd",cmd),r->laterRefresh());}
 void laterRefresh(){ui.postDelayed(()->{if(connected&&!busy)refreshStatus();},250);}
 interface RemoteWork{JSONObject run()throws Exception;}
 JSONObject sendRequest(JSONObject request)throws Exception{
  byte[] raw=exchange(0x55,protocol.crypt(request.toString().getBytes("UTF-8")));
  JSONObject response=new JSONObject(new String(protocol.crypt(raw),"UTF-8"));
  if(!response.optBoolean("ok"))throw new IllegalArgumentException(response.optString("error","操作未完成"));
  return response;
 }
 void nextStory(){runCommand(()->{
  ArrayList<String> names=new ArrayList<>();ArrayList<Integer> ids=new ArrayList<>();
  for(int page=0;;page++){
   JSONObject list=sendRequest(json("cmd","stories","page",page));JSONArray items=list.getJSONArray("items");
   for(int i=0;i<items.length();i++){JSONObject item=items.getJSONObject(i);names.add(item.getString("name"));ids.add(item.getInt("id"));}
   if(!list.optBoolean("more"))break;
   if(page>=127)throw new IllegalArgumentException("书架过大，请从书架选择故事");
  }
  JSONObject state=sendRequest(json("cmd","status"));
  int at=StoryNavigation.next(names,state.optString("story_title",""),state.optString("play_mode","sequence"),new Random());
  return sendRequest(json("cmd","play","id",ids.get(at)));
 },r->laterRefresh());}
 void command(JSONObject request,Result action){runCommand(()->sendRequest(request),action);}
 void runCommand(RemoteWork work,Result action){if(!connected){text("请先输入配对码并连接设备");return;}if(busy){text("正在处理，请稍候");return;}busy=true;BluetoothGatt owner=gatt;
  jobs.execute(()->{workerGatt=owner;try{JSONObject response=work.run();ui.post(()->{if(gatt!=owner)return;try{status.setText("已连接");action.accept(response);}catch(Exception e){text("设备回复格式异常");}});}catch(IllegalArgumentException e){text(e.getMessage());}catch(Exception e){if(gatt==owner){disconnect();text("连接中断，请重新扫描并输入配对码");}}finally{busy=false;}});
 }
 void refreshStatus(){final int tab=selectedTab;runCommand(()->{JSONObject r=sendRequest(json("cmd","status"));if(tab==3&&r.optBoolean("radio_supported"))r.put("radio",sendRequest(json("cmd","radio_status")));if(tab==2&&r.optBoolean("songs_supported"))r.put("song",sendRequest(json("cmd","song_status")));return r;},r->{update(r);if(r.has("song"))updateSong(r.getJSONObject("song"));if(r.has("radio"))updateRadio(r.getJSONObject("radio"));ui.post(()->{if(selectedTab==1&&storyPage<0)loadStoriesPage(0);else if(selectedTab==2&&songsSupported&&songPage<0)loadSongsPage(0);else if(selectedTab==3&&radioSupported&&!radioReady)loadRadioStations();else if(selectedTab==4&&appPage<0)loadAppsPage(0);});});}
 void selectMode(String value){for(int i=0;i<3;i++){boolean chosen=modes[i].equals(value);modeButtons[i].setTextColor(chosen?accent:muted);modeButtons[i].setBackground(shape(chosen?Color.rgb(25,66,62):Color.rgb(30,46,65),13));}}
 String clock(int value){return String.format(Locale.ROOT,"%02d:%02d",Math.max(0,value)/60,Math.max(0,value)%60);}
 void update(JSONObject r){songsSupported=r.optBoolean("songs_supported");if(!songsSupported)songState.setText("儿歌遥控需开发板 s3.48 或更新固件");radioSupported=r.optBoolean("radio_supported");if(!radioSupported){radioState.setText("电台遥控需开发板 s3.45 或更新固件");radioNetwork.setText("请先更新开发板，再重新连接");}if(!tracking){volume.setProgress(r.optInt("volume",75));radioVolume.setProgress(r.optInt("volume",75));songVolume.setProgress(r.optInt("volume",75));brightness.setProgress(r.optInt("brightness",80));}selectMode(r.optString("play_mode","sequence"));speedButton.setText("播放速度  "+r.optDouble("story_speed",1)+"x");String title=r.optString("story_title","");if(!title.isEmpty())storyTitle.setText(title);storyTime.setText(clock(r.optInt("story_position",0)));String state=r.optString("story_state","");storyState.setText(state.equals("Paused")?"已暂停":r.optBoolean("story_active")?"正在播放":"已停止");if(r.optBoolean("locked"))text("设备已锁屏，需双按设备音量＋解锁");}
 void loadAppsPage(int page){command(json("cmd","apps","page",page),r->{appPage=page;appTotal=r.optInt("total",page*3+r.getJSONArray("items").length());apps.removeAllViews();JSONArray items=r.getJSONArray("items");for(int i=0;i<items.length();i++){JSONObject item=items.getJSONObject(i);int id=item.getInt("id");button(apps,item.getString("name"),()->command(json("cmd","open","id",id),v->{}));}appPages.setText("第 "+(page+1)+" / "+Math.max(1,(appTotal+2)/3)+" 页");});}
 void loadStoriesPage(int page){command(json("cmd","stories","page",page),r->{storyPage=page;storyTotal=r.optInt("total",page*3+r.getJSONArray("items").length());stories.removeAllViews();JSONArray items=r.getJSONArray("items");for(int i=0;i<items.length();i++){JSONObject item=items.getJSONObject(i);int id=item.getInt("id");button(stories,String.format(Locale.ROOT,"%02d  %s",id+1,item.getString("name")),()->command(json("cmd","play","id",id),v->{storyTitle.setText(item.optString("name"));laterRefresh();}));}storyPages.setText("第 "+(page+1)+" / "+Math.max(1,(storyTotal+2)/3)+" 页");});}
 void createSongsPage(LinearLayout parent){
  LinearLayout now=card(parent);now.setBackground(shape(Color.rgb(43,43,68),22));
  TextView tag=label("儿歌  ·  SD 离线播放",14);tag.setTextColor(Color.rgb(228,207,255));now.addView(tag);
  songTitle=label("选择一首儿歌",25);songTitle.setTypeface(null,1);now.addView(songTitle);
  songState=label("连接设备后查看儿歌",16);songState.setTextColor(muted);now.addView(songState);
  songTime=label("00:00 / 00:00",18);now.addView(songTime);
  LinearLayout transport=row();now.addView(transport);cell(transport,"上一首",()->songCommand(json("cmd","song_previous")));
  songToggle=cell(transport,"播放",()->toggleSong());songToggle.setTextColor(accent);
  cell(transport,"下一首",()->songCommand(json("cmd","song_next")));
  LinearLayout extra=row();now.addView(extra);cell(extra,"停止",()->songCommand(json("cmd","song_stop")));
  songTimer=cell(extra,"睡眠定时",()->{if(!requireSongs())return;new AlertDialog.Builder(this).setTitle("儿歌睡眠定时").setItems(new String[]{"关闭定时","15 分钟","30 分钟","45 分钟"},(d,which)->{int[] minutes={0,15,30,45};songCommand(json("cmd","song_timer","minutes",minutes[which]));}).show();});
  TextView note=label("最后两分钟声音渐弱、屏幕渐暗，到时说晚安并停止。",13);note.setTextColor(muted);now.addView(note);
  LinearLayout sound=card(parent);songVolume=slider(sound,"儿歌音量",0,"volume");
  LinearLayout mode=card(parent);mode.addView(label("播放方式",18));LinearLayout choices=row();mode.addView(choices);
  String[] names={"顺序播放","随机播放","单曲循环"};for(int i=0;i<3;i++){final int at=i;songModeButtons[i]=cell(choices,names[i],()->songCommand(json("cmd","song_mode","value",modes[at])));songModeButtons[i].setTextSize(13);songModeButtons[i].setCompoundDrawablesWithIntrinsicBounds(null,new ModeIcon(this,i,accent),null,null);songModeButtons[i].getLayoutParams().height=dp(80);}
  LinearLayout library=card(parent);library.addView(label("儿歌曲库",20));songRows=column();library.addView(songRows);songPages=label("连接设备后查看曲库",14);songPages.setTextColor(muted);library.addView(songPages);
  LinearLayout nav=row();library.addView(nav);cell(nav,"上一页",()->loadSongsPage(SongControls.page(songPage-1,songTotal)));cell(nav,"下一页",()->loadSongsPage(SongControls.page(songPage+1,songTotal)));button(library,"刷新曲库与状态",()->loadSongsPage(Math.max(0,songPage)));
  selectSongMode("sequence");
 }
 boolean requireSongs(){if(!connected){text("请先输入配对码并连接设备");return false;}if(!songsSupported){text("请先更新开发板至 s3.48 或更新固件");return false;}return true;}
 void songCommand(JSONObject request){if(requireSongs())command(request,r->laterRefresh());}
 void toggleSong(){
  if(!requireSongs())return;final int selected=selectedSongId;
  runCommand(()->{JSONObject r=sendRequest(json("cmd","song_status"));String cmd=SongControls.toggleCommand(r.optBoolean("active"),r.optString("state"));int id=r.optInt("id",selected);if(id<0)id=selected;if(cmd.equals("song_play")&&id<0)throw new IllegalArgumentException("请先从列表选择一首儿歌");return sendRequest(cmd.equals("song_play")?json("cmd",cmd,"id",id):json("cmd",cmd));},r->laterRefresh());
 }
 void loadSongsPage(int page){
  if(!requireSongs())return;
  command(json("cmd","songs","page",Math.max(0,page)),r->{songPage=page;songTotal=r.optInt("total");songRows.removeAllViews();JSONArray items=r.getJSONArray("items");
   for(int i=0;i<items.length();i++){JSONObject item=items.getJSONObject(i);final int id=item.getInt("id");String title=item.getString("name");if(selectedSongId<0){selectedSongId=id;songTitle.setText(title);}button(songRows,String.format(Locale.ROOT,"%02d  %s",id+1,title),()->command(json("cmd","song_play","id",id),reply->{selectedSongId=id;songTitle.setText(title);laterRefresh();}));}
   songPages.setText(songTotal==0?"暂无儿歌，请插入含曲库的 SD 卡":"共 "+songTotal+" 首 · 第 "+(songPage+1)+" / "+Math.max(1,(songTotal+2)/3)+" 页");laterRefresh();});
 }
 void selectSongMode(String value){for(int i=0;i<3;i++){boolean chosen=modes[i].equals(value);songModeButtons[i].setTextColor(chosen?accent:muted);songModeButtons[i].setBackground(shape(chosen?Color.rgb(25,66,62):Color.rgb(30,46,65),13));}}
 void updateSong(JSONObject r){
  String title=r.optString("title","");if(!title.isEmpty())songTitle.setText(title);int id=r.optInt("id",-1);if(id>=0)selectedSongId=id;
  songState.setText(r.optString("error",SongControls.stateLabel(r.optString("state","Idle")))+(r.optBoolean("muted")?" · 勿扰静音":""));
  songTime.setText(clock(r.optInt("position"))+" / "+clock(r.optInt("duration")));
  songToggle.setText(r.optBoolean("active")&&!r.optString("state").equals("Paused")?"暂停":"播放");
  songTimer.setText(SongControls.timerLabel(r.optBoolean("sleep_active"),r.optInt("sleep_remaining_seconds")));selectSongMode(r.optString("play_mode","sequence"));if(!tracking)songVolume.setProgress(r.optInt("volume",75));
 }
 void createRadioPage(LinearLayout parent){
  LinearLayout now=card(parent);now.setBackground(shape(Color.rgb(49,39,29),22));
  TextView tag=label("网络电台  ·  LIVE",14);tag.setTextColor(Color.rgb(255,201,128));now.addView(tag);
  radioTitle=label("选一个频道，听见好时光",25);radioTitle.setTypeface(null,1);now.addView(radioTitle);
  radioDetail=label("中文优先 · 少量英语陪伴",14);radioDetail.setTextColor(muted);now.addView(radioDetail);
  radioState=label("连接设备后选择频道",17);now.addView(radioState);
  radioNetwork=label("蓝牙遥控 · 开发板通过 Wi-Fi 收听",13);radioNetwork.setTextColor(muted);now.addView(radioNetwork);
  LinearLayout transport=row();now.addView(transport);cell(transport,"上一台",()->moveRadio(-1));
  radioToggle=cell(transport,"播放",()->toggleRadio());radioToggle.setTextColor(Color.rgb(255,201,128));
  cell(transport,"下一台",()->moveRadio(1));
  LinearLayout extra=row();now.addView(extra);cell(extra,"停止",()->radioCommand(json("cmd","radio_stop")));
  radioTimer=cell(extra,"定时关闭",()->{if(!requireRadio())return;new AlertDialog.Builder(this).setTitle("电台定时关闭").setItems(new String[]{"关闭定时","15 分钟","30 分钟","45 分钟"},(d,which)->{int[] minutes={0,15,30,45};radioCommand(json("cmd","radio_timer","minutes",minutes[which]));}).show();});
  LinearLayout sound=card(parent);radioVolume=slider(sound,"电台音量",0,"volume");
  LinearLayout list=card(parent);list.addView(label("选择频道",20));LinearLayout cats=row();list.addView(cats);
  String[] names={"儿童","音乐","资讯"};for(int i=0;i<3;i++){final String name=names[i];radioCategories[i]=cell(cats,name,()->{radioCategory=name;renderRadioStations();});}
  radioEmpty=label("连接后加载频道",14);radioEmpty.setTextColor(muted);list.addView(radioEmpty);
  radioStations=column();list.addView(radioStations);button(list,"刷新频道与状态",()->{if(requireRadio())loadRadioStations();});renderRadioStations();
 }
 boolean requireRadio(){if(!connected){text("请先输入配对码并连接设备");return false;}if(!radioSupported){text("请先更新开发板至 s3.45 或更新固件");return false;}return true;}
 void radioCommand(JSONObject request){if(requireRadio())command(request,r->laterRefresh());}
 void playRadio(String id){if(!requireRadio())return;command(json("cmd","radio_play","id",id),r->{radioSelected=id;renderRadioStations();laterRefresh();});}
 void toggleRadio(){
  if(!requireRadio())return;final String selected=radioSelected;
  runCommand(()->{JSONObject state=sendRequest(json("cmd","radio_status"));String cmd=RadioControls.toggleCommand(state.optBoolean("active"),state.optBoolean("paused"));if(cmd.equals("radio_play")&&selected.isEmpty())throw new IllegalArgumentException("请先从频道列表选择一台");return sendRequest(cmd.equals("radio_play")?json("cmd",cmd,"id",selected):json("cmd",cmd));},r->laterRefresh());
 }
 void moveRadio(int step){if(!requireRadio())return;try{playRadio(RadioControls.next(radioIds,radioGroups,radioSelected,radioCategory,step));}catch(IllegalArgumentException e){text(e.getMessage());}}
 void loadRadioStations(){
  if(!requireRadio())return;
  runCommand(()->{
   JSONArray all=new JSONArray();for(int page=0;;page++){JSONObject r=sendRequest(json("cmd","radio_stations","page",page));JSONArray items=r.getJSONArray("items");for(int i=0;i<items.length();i++)all.put(items.getJSONObject(i));if(!r.optBoolean("more"))break;if(page>=31)throw new IllegalArgumentException("频道列表过大，请更新应用");}return json("items",all);
  },r->{radioIds.clear();radioNames.clear();radioGroups.clear();radioSubs.clear();JSONArray items=r.getJSONArray("items");for(int i=0;i<items.length();i++){JSONObject item=items.getJSONObject(i);radioIds.add(item.getString("id"));radioNames.add(item.getString("name"));radioGroups.add(item.getString("group"));radioSubs.add(item.getString("sub"));}radioReady=true;if(radioSelected.isEmpty()&&!radioIds.isEmpty())radioSelected=radioIds.get(0);renderRadioStations();laterRefresh();});
 }
 void renderRadioStations(){
  if(radioStations==null)return;radioStations.removeAllViews();int shown=0;
  String[] names={"儿童","音乐","资讯"};for(int i=0;i<3;i++){boolean chosen=names[i].equals(radioCategory);radioCategories[i].setTextColor(chosen?accent:muted);radioCategories[i].setBackground(shape(chosen?Color.rgb(25,66,62):Color.rgb(30,46,65),13));}
  for(int i=0;i<radioIds.size();i++){
   if(!radioGroups.get(i).equals(radioCategory))continue;shown++;final String id=radioIds.get(i);
   Button b=button(radioStations,radioNames.get(i)+"\n"+radioSubs.get(i),()->playRadio(id));b.setTextSize(15);b.setGravity(Gravity.CENTER_VERTICAL|Gravity.LEFT);b.setPadding(dp(12),dp(10),dp(12),dp(10));b.setMinHeight(dp(78));b.getLayoutParams().height=-2;
   if(id.equals(radioSelected)){b.setTextColor(accent);b.setBackground(shape(Color.rgb(25,66,62),14));}
  }
  radioEmpty.setText(!radioReady?"连接后加载频道":shown==0?"这个分类暂无频道":shown+" 个频道 · 点击收听");
  int index=radioIds.indexOf(radioSelected);if(index>=0){radioTitle.setText(radioNames.get(index));radioDetail.setText(radioSubs.get(index));}
 }
 void updateRadio(JSONObject r){
  String id=r.optString("station","");if(!id.isEmpty()&&radioIds.contains(id)&&!id.equals(radioSelected)){radioSelected=id;renderRadioStations();}
  radioState.setText(r.optString("error",RadioControls.stateLabel(r.optString("state","Idle"))));radioToggle.setText(r.optBoolean("active")&&!r.optBoolean("paused")?"暂停":"播放");
  radioTimer.setText(RadioControls.timerLabel(r.optBoolean("sleep_active"),r.optInt("sleep_remaining_seconds")));radioNetwork.setText((r.optBoolean("wifi_connected")?"Wi-Fi 已连接":"开发板 Wi-Fi 未连接")+(r.optBoolean("muted")?" · 勿扰静音":""));if(!tracking)radioVolume.setProgress(r.optInt("volume",75));
 }
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
 void connect(BluetoothDevice device){String pop=code.getText().toString().trim();if(!pop.matches("[0-9]{4}")){text("请输入设备当前显示的4位数字配对码");return;}stopScan();disconnect();apps.removeAllViews();stories.removeAllViews();radioStations.removeAllViews();radioReady=radioSupported=songsSupported=false;songPage=-1;songTotal=0;selectedSongId=-1;songRows.removeAllViews();songTitle.setText("选择一首儿歌");songState.setText("连接设备后查看儿歌");songTime.setText("00:00 / 00:00");songPages.setText("连接设备后查看曲库");radioIds.clear();radioNames.clear();radioGroups.clear();radioSubs.clear();radioSelected="";radioEmpty.setText("连接后加载频道");text("正在连接设备…");protocol=new Protocol(pop);gatt=device.connectGatt(this,false,callbacks,BluetoothDevice.TRANSPORT_LE);ui.postDelayed(()->{if(!connected&&gatt!=null){disconnect();text("连接超时，请重新扫描");}},25000);}
 final BluetoothGattCallback callbacks=new BluetoothGattCallback(){
  public void onConnectionStateChange(BluetoothGatt g,int status,int state){if(g!=gatt)return;if(state==BluetoothProfile.STATE_CONNECTED&&status==0){if(!g.requestMtu(512))g.discoverServices();}else if(state==BluetoothProfile.STATE_DISCONNECTED){connected=false;signal(null,-1);g.close();if(g==gatt)gatt=null;text("已断开连接");ui.post(()->setConnectedUi(false));}}
  public void onMtuChanged(BluetoothGatt g,int mtu,int status){if(g==gatt)g.discoverServices();}
  public void onServicesDiscovered(BluetoothGatt g,int gattStatus){if(g!=gatt)return;if(gattStatus!=0||g.getService(SERVICE)==null||g.getService(SERVICE).getCharacteristic(endpoint(0x55))==null){disconnect();text("设备未开启蓝牙遥控，或固件版本过旧");return;}busy=true;jobs.execute(()->{workerGatt=g;try{byte[] r=exchange(0x51,protocol.hello());r=exchange(0x51,protocol.prove(r));protocol.verify(r);if(gatt!=g)throw new Exception();connected=true;busy=false;ui.post(()->{code.setText("");appPage=storyPage=songPage=-1;setConnectedUi(true);status.setText("已连接 · 加密蓝牙通道");refreshStatus();});}catch(Exception e){if(gatt==g){disconnect();text("配对失败，请核对设备上的配对码");}}finally{busy=false;}});}
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
