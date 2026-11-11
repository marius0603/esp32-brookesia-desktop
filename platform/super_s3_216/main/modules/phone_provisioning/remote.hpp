#pragma once
#include "brookesia/service_manager/service/manager.hpp"
#include "brookesia/hal_interface.hpp"
#include "../child_mode/child_mode.hpp"
#include "navigation.hpp"
#include "navigation_data.hpp"
#include "radio_catalog.hpp"
#include <cmath>
#include "esp_random.h"
namespace phone_remote {
using namespace esp_brookesia::service;
inline boost::json::object execute(const boost::json::object &request) {
 auto call=[](const char *service,const char *fn,const boost::json::object &args=boost::json::object{}) {
  auto s=ServiceManager::get_instance().get_service(service);
  return s && s->is_running()?s->call_function_sync(fn,args,6000):FunctionResult{.success=false,.error_message="服务未就绪"};
 };
 auto data=[](const FunctionResult &r)->boost::json::value {
  if(!r.success || !r.data)return nullptr;
  return std::visit([](const auto &v)->boost::json::value{if constexpr(std::is_same_v<std::decay_t<decltype(v)>,RawBuffer>)return nullptr;else return boost::json::value(v);},*r.data);
 };
 auto fail=[](const char *message){return boost::json::object{{"ok",false},{"error",message}};};
 const auto *c=request.if_contains("cmd");if(!c || !c->is_string())return fail("缺少指令");
 const auto command=c->as_string();auto modes=data(call("DeviceModes","GetState"));
 if(!modes.is_object())return fail("设备尚未就绪");
 const bool locked=modes.as_object().at("screen_locked").as_bool();
 auto play_mode=[&]()->std::string {
  auto book=data(call("Audiobook","GetState"));
  if(book.is_object())if(auto *mode=book.as_object().if_contains("play_mode");mode&&mode->is_string())return std::string(mode->as_string());
  return "sequence";
 };
 if(command=="nav") {
  auto child=data(call("ChildMode","GetState"));
  const bool allowed=!locked&&child.is_object()&&!child.as_object().at("enabled").as_bool();
  const auto result=phone_navigation::receive(request,allowed);
  return {{"ok",result.success},{"error",result.error_message}};
 }
 if(command=="status") {
  boost::json::object answer{{"ok",true},{"locked",locked},{"volume",modes.as_object().at("resume_volume")},{"radio_supported",true},{"songs_supported",true},{"brightness",modes.as_object().at("brightness_percent")},{"play_mode",play_mode()}};
  auto book=data(call("Audiobook","GetState"));if(book.is_object()){
   for(const auto &[source,target]:{std::pair{"speed","story_speed"},std::pair{"title","story_title"},{"state","story_state"},{"active","story_active"},{"position","story_position"}})
    if(auto *v=book.as_object().if_contains(source))answer[target]=*v;
   if(auto *p=book.as_object().if_contains("path");p&&p->is_string()&&p->as_string().starts_with("/sdcard/audiobooks/songs/")){
    answer["story_title"]="";answer["story_state"]="Idle";answer["story_active"]=false;answer["story_position"]=0;
   }
  }
  answer["navigation_supported"]=true;
  return answer;
 }
 if(command=="radio_status") {
  auto radio=data(call("Radio","GetState"));if(!radio.is_object())return fail("电台服务尚未就绪");
  const auto &o=radio.as_object();auto network=data(call("Wifi","GetGeneralState"));
  boost::json::object answer{{"ok",true},{"locked",locked},{"volume",modes.as_object().at("resume_volume")},
   {"muted",modes.as_object().at("do_not_disturb")},{"wifi_connected",network.is_string()&&network.as_string()=="Connected"}};
  for(const char *key:{"state","station","active","paused","sleep_active","sleep_remaining_seconds"})
   if(auto *v=o.if_contains(key))answer[key]=*v;
  if(auto *e=o.if_contains("error");e&&e->is_string()&&!e->as_string().empty())answer["error"]="播放失败，请切换频道或重试";
  return answer;
 }
 if(command=="song_status") {
  auto book=data(call("Audiobook","GetState"));if(!book.is_object())return fail("儿歌服务尚未就绪");
  const auto &o=book.as_object();const auto *path=o.if_contains("path");
  const bool owns=path&&path->is_string()&&path->as_string().starts_with("/sdcard/audiobooks/songs/");
  int song_id=-1;std::string title=owns?std::string(o.at("title").as_string()):"";
  if(title.size()>60){size_t end=60;while(end&&(uint8_t(title[end])&0xc0)==0x80)--end;title.resize(end);}
  if(owns){auto list=data(call("Audiobook","ListSongs"));if(list.is_object()){
   const auto &tracks=list.as_object().at("tracks").as_array();
   for(size_t i=0;i<tracks.size();++i)if(tracks[i].as_object().at("path")==*path){song_id=i;break;}
  }}
  boost::json::object answer{{"ok",true},{"locked",locked},{"volume",modes.as_object().at("resume_volume")},
   {"muted",modes.as_object().at("do_not_disturb")},{"play_mode",o.at("song_play_mode")},
   {"id",song_id},{"title",title},{"state",owns?o.at("state"):boost::json::value("Idle")},
   {"active",owns&&o.at("active").as_bool()},{"position",owns?o.at("position"):boost::json::value(0)},
   {"duration",owns?o.at("duration"):boost::json::value(0)},
   {"sleep_active",owns&&o.at("sleep_active").as_bool()},{"sleep_remaining_seconds",owns?o.at("sleep_remaining_seconds"):boost::json::value(0)}};
  if(owns)if(auto *e=o.if_contains("error");e&&e->is_string()&&!e->as_string().empty())answer["error"]="播放失败，请重新选择儿歌";
  return answer;
 }
 if(locked && command!="lock")return fail("设备已锁屏，请双按音量＋解锁");
 FunctionResult result{.success=false,.error_message="不支持的指令"};
 auto integer=[&](const char *key,int low,int high)->int {
  const auto *v=request.if_contains(key);if(!v || !v->is_number())return -1;
  const double n=v->is_double()?v->as_double():v->is_int64()?double(v->as_int64()):double(v->as_uint64());
  return std::isfinite(n) && std::floor(n)==n && n>=low && n<=high?int(n):-1;
 };
 if(command=="songs" || command=="song_play" || command=="song_previous" || command=="song_next" || command=="song_pause" || command=="song_resume" || command=="song_stop" || command=="song_mode" || command=="song_timer") {
  if(command!="song_stop"&&!child_mode_audiobook_allowed())return fail("儿歌已被家长限制，或已到休息时间");
  if(command=="song_mode"){
   const auto *mode=request.if_contains("value");if(!mode||!mode->is_string())return fail("播放模式无效");
   result=call("Audiobook","SetSongMode",{{"Mode",*mode}});
  } else if(command=="songs"||command=="song_play"||command=="song_previous"||command=="song_next"){
   auto list=data(call("Audiobook","ListSongs"));if(!list.is_object())return fail("儿歌列表暂不可用");
   const auto &tracks=list.as_object().at("tracks").as_array();
   if(command=="songs"){
    int page=integer("page",0,170);if(page<0)return fail("页码无效");boost::json::array items;
    for(size_t i=page*3;i<tracks.size()&&i<size_t(page*3+3);++i){
     std::string name(tracks[i].as_object().at("title").as_string());
     if(name.size()>60){size_t end=60;while(end&&(uint8_t(name[end])&0xc0)==0x80)--end;name.resize(end);}
     items.push_back(boost::json::object{{"id",i},{"name",name}});
    }
    return {{"ok",true},{"items",std::move(items)},{"more",size_t(page*3+3)<tracks.size()},{"total",tracks.size()}};
   }
   if(tracks.empty())return fail("SD 卡中暂无儿歌");
   int at=integer("id",0,511);
   if(command!="song_play"){
    auto book=data(call("Audiobook","GetState"));if(!book.is_object())return fail("播放状态暂不可用");
    at=-1;for(size_t i=0;i<tracks.size();++i)if(tracks[i].as_object().at("path")==book.as_object().at("path")){at=i;break;}
    if(at<0)return fail("请先从列表选择一首儿歌");
    if(book.as_object().at("song_play_mode")=="random"&&tracks.size()>1){const int n=esp_random()%(tracks.size()-1);at=n>=at?n+1:n;}
    else at=(at+(command=="song_next"?1:int(tracks.size())-1))%tracks.size();
   }
   if(at<0||size_t(at)>=tracks.size())return fail("儿歌编号无效");
   result=open_songs();if(!result.success)return {{"ok",false},{"error",result.error_message}};
   result=call("Audiobook","SetSpeed",{{"Speed",1}});if(!result.success)return {{"ok",false},{"error",result.error_message}};
   result=call("Audiobook","Play",{{"Path",tracks[at].as_object().at("path")},{"Position",0}});
  } else {
   auto book=data(call("Audiobook","GetState"));if(!book.is_object())return fail("播放状态暂不可用");
   const auto *path=book.as_object().if_contains("path");
   if(!path||!path->is_string()||!path->as_string().starts_with("/sdcard/audiobooks/songs/"))return fail("当前未播放儿歌");
   if(command=="song_timer"){
    int n=integer("minutes",0,45);if(n!=0&&n!=15&&n!=30&&n!=45)return fail("定时选项为关闭、15、30或45分钟");
    result=call("Audiobook","SetSleepTimer",{{"Minutes",n}});
   } else result=call("Audiobook",command=="song_pause"?"Pause":command=="song_resume"?"Resume":"Stop");
  }
 } else if(command=="radio_stations" || command=="radio_play" || command=="radio_pause" || command=="radio_resume" || command=="radio_stop" || command=="radio_timer") {
  if(command!="radio_stop"&&!child_mode_radio_allowed())return fail("网络电台暂未开放给儿童模式");
  if(command=="radio_stations") {
   int page=integer("page",0,127);if(page<0)return fail("页码无效");
   constexpr size_t count=sizeof(radio_stations)/sizeof(radio_stations[0]);boost::json::array items;
   for(size_t i=page*2;i<count&&i<size_t(page*2+2);++i){const auto &s=radio_stations[i];items.push_back(boost::json::object{{"id",s.id},{"name",s.name},{"group",s.group},{"sub",s.sub}});}
   return {{"ok",true},{"items",std::move(items)},{"more",size_t(page*2+2)<count},{"total",count}};
  }
  if(command=="radio_play") {
   const auto *id=request.if_contains("id");const RadioStation *chosen=nullptr;
   if(id&&id->is_string())for(const auto &s:radio_stations)if(id->as_string()==s.id){chosen=&s;break;}
   if(!chosen)return fail("频道编号无效");
   result=open_radio();if(!result.success)return {{"ok",false},{"error",result.error_message}};
   result=call("Radio","Play",{{"Station",chosen->id}});
  } else if(command=="radio_timer") {
   int n=integer("minutes",0,45);if(n!=0&&n!=15&&n!=30&&n!=45)return fail("定时选项为关闭、15、30或45分钟");
   result=call("Radio","SetSleepTimer",{{"Minutes",n}});
  } else result=call("Radio",command=="radio_pause"?"Pause":command=="radio_resume"?"Resume":"Stop");
 } else if(command=="speed") {
  if(!child_mode_audiobook_allowed())return fail("听书已被家长限制");
  const auto *v=request.if_contains("value");if(!v||!v->is_number())return fail("倍速无效");
  const double speed=v->is_double()?v->as_double():v->is_int64()?double(v->as_int64()):double(v->as_uint64());
  result=call("Audiobook","SetSpeed",{{"Speed",speed}});
 } else if(command=="volume") {int n=integer("value",0,100);if(n<0)return fail("音量范围为0至100");result=call("AudioPlayback","SetVolume",{{"Volume",n}});}
 else if(command=="brightness") {
  int n=integer("value",10,100);if(n<0)return fail("亮度范围为10至100");
  auto backlight=esp_brookesia::hal::acquire_first_interface<esp_brookesia::hal::display::BacklightIface>();
  result.success=backlight && backlight->set_brightness(uint8_t(n));result.error_message="亮度设置失败";
 } else if(command=="apps" || command=="stories") {
  int page=integer("page",0,127);if(page<0)return fail("页码无效");
  auto list=data(call(command=="apps"?"SystemCore":"Audiobook",command=="apps"?"ListApps":"List"));
  if(command=="stories" && list.is_object())list=list.as_object().at("tracks");
  if(!list.is_array())return fail("列表暂不可用");
  boost::json::array items;const auto &array=list.as_array();
  for(size_t i=page*3;i<array.size() && i<size_t(page*3+3);++i) {
   const auto &o=array[i].as_object();
   if(command=="apps")items.push_back(boost::json::object{{"id",o.at("app_id")},{"name",o.at("manifest").as_object().at("name")}});
   else {
    const auto *title=o.if_contains("title");std::string name=title && title->is_string()?std::string(title->as_string()):"故事";
    if(auto slash=name.find_last_of('/');slash!=std::string::npos)name.erase(0,slash+1);
    if(auto dot=name.find_last_of('.');dot!=std::string::npos)name.resize(dot);
    if(name.size()>60){size_t end=60;while(end && (uint8_t(name[end])&0xc0)==0x80)--end;name.resize(end);}
    items.push_back(boost::json::object{{"id",i},{"name",name}});
   }
  }
  return {{"ok",true},{"items",std::move(items)},{"more",size_t(page*3+3)<array.size()},{"total",array.size()}};
 } else if(command=="open") {
  auto policy=data(call("ChildMode","GetState"));
  if(!policy.is_object() || policy.as_object().at("enabled").as_bool())return fail("儿童模式下请在设备上打开应用");
  int id=integer("id",1,10000);if(id<0)return fail("应用编号无效");result=open_app(id);
 }
 else if(command=="mode") {
  if(!child_mode_audiobook_allowed())return fail("听书已被家长限制");
  const auto *mode=request.if_contains("value");if(!mode || !mode->is_string() ||
   (mode->as_string()!="sequence" && mode->as_string()!="random" && mode->as_string()!="repeat_one"))return fail("播放模式无效");
  result=call("Audiobook","SetPlayMode",{{"Mode",*mode}});
  if(result.success)result=open_audiobook();
 } else if(command=="play") {
  if(!child_mode_audiobook_allowed())return fail("听书已被家长限制");
  int index=integer("id",0,511);auto list=data(call("Audiobook","List"));
  if(index<0 || !list.is_object() || size_t(index)>=list.as_object().at("tracks").as_array().size())return fail("故事编号无效");
  result=open_audiobook();if(!result.success)return {{"ok",false},{"error",result.error_message}};
  auto path=list.as_object().at("tracks").as_array()[index].as_object().at("path");result=call("Audiobook","Play",{{"Path",path},{"Position",0}});
 } else if(command=="pause" || command=="resume" || command=="stop") {
  if(command=="resume" && !child_mode_audiobook_allowed())return fail("听书已被家长限制");
  if(child_mode_audiobook_allowed()){result=open_audiobook();if(!result.success)return {{"ok",false},{"error",result.error_message}};}
  result=call("Audiobook",command=="pause"?"Pause":command=="resume"?"Resume":"Stop");
 } else if(command=="lock" || command=="sleep" || command=="wake")result=call("DeviceModes",command=="lock"?"LockScreen":command=="sleep"?"SleepNow":"Wake");
 return {{"ok",result.success},{"error",result.success?"":result.error_message}};
}
}
