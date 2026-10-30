#pragma once
#include "brookesia/service_manager/service/manager.hpp"
#include "brookesia/hal_interface.hpp"
#include "../child_mode/child_mode.hpp"
#include "navigation.hpp"
#include <cmath>
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
 if(command=="status")return {{"ok",true},{"locked",locked},{"volume",data(call("AudioPlayback","GetVolume"))},{"brightness",modes.as_object().at("brightness_percent")}};
 if(locked && command!="lock")return fail("设备已锁屏，请双按音量＋解锁");
 FunctionResult result{.success=false,.error_message="不支持的指令"};
 auto integer=[&](const char *key,int low,int high)->int {
  const auto *v=request.if_contains(key);if(!v || !v->is_number())return -1;
  const double n=v->is_double()?v->as_double():v->is_int64()?double(v->as_int64()):double(v->as_uint64());
  return std::isfinite(n) && std::floor(n)==n && n>=low && n<=high?int(n):-1;
 };
 if(command=="volume") {int n=integer("value",0,100);if(n<0)return fail("音量范围为0至100");result=call("AudioPlayback","SetVolume",{{"Volume",n}});}
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
  return {{"ok",true},{"items",std::move(items)},{"more",size_t(page*3+3)<array.size()}};
 } else if(command=="open") {
  auto policy=data(call("ChildMode","GetState"));
  if(!policy.is_object() || policy.as_object().at("enabled").as_bool())return fail("儿童模式下请在设备上打开应用");
  int id=integer("id",1,10000);if(id<0)return fail("应用编号无效");result=open_app(id);
 }
 else if(command=="play") {
  if(!child_mode_audiobook_allowed())return fail("听书已被家长限制");
  int index=integer("id",0,511);auto list=data(call("Audiobook","List"));
  if(index<0 || !list.is_object() || size_t(index)>=list.as_object().at("tracks").as_array().size())return fail("故事编号无效");
  auto path=list.as_object().at("tracks").as_array()[index].as_object().at("path");result=call("Audiobook","Play",{{"Path",path},{"Position",0}});
 } else if(command=="pause" || command=="resume" || command=="stop") {
  if(command=="resume" && !child_mode_audiobook_allowed())return fail("听书已被家长限制");
  result=call("Audiobook",command=="pause"?"Pause":command=="resume"?"Resume":"Stop");
 } else if(command=="lock" || command=="sleep" || command=="wake")result=call("DeviceModes",command=="lock"?"LockScreen":command=="sleep"?"SleepNow":"Wake");
 return {{"ok",result.success},{"error",result.success?"":result.error_message}};
}
}
