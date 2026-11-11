#include "navigation_data.hpp"
#include "navigation.hpp"
#include "esp_timer.h"
#include <mutex>
#include <cmath>
#include <cctype>
namespace phone_navigation {
namespace {
// Only RAM; no directions, phone locations or credentials written to Flash.
std::mutex mutex;
std::string session, road;
int sequence=0, source=0, turn=0, distance=0, remaining=0, seconds=0, phase=2;
int64_t received=0;
int integer(const boost::json::object &o,const char *key,int high,int low=0){
 const auto *v=o.if_contains(key);if(!v || !v->is_number())return -2;
 const double n=v->is_double()?v->as_double():v->is_int64()?double(v->as_int64()):double(v->as_uint64());
 return std::isfinite(n)&&std::floor(n)==n&&n>=low&&n<=high?int(n):-2;
}
}
boost::json::object snapshot(){
 std::lock_guard<std::mutex> lock(mutex);
 const int64_t age=received?std::max<int64_t>(0,(esp_timer_get_time()-received)/1000):-1;
 const bool stale=age<0 || age>=15000;
 return {{"received",received!=0},{"stale",stale},{"age_ms",age},{"source",source},
  {"turn",turn},{"distance",distance},{"remaining",remaining},{"seconds",seconds},
  {"road",road},{"phase",phase},{"sequence",sequence},{"active",received!=0&&!stale&&phase==0}};
}
void disconnect(){std::lock_guard<std::mutex> lock(mutex);if(received)phase=2;}
bool usable(){std::lock_guard<std::mutex> lock(mutex);return received&&phase!=2&&esp_timer_get_time()-received<15000000;}
esp_brookesia::service::FunctionResult receive(const boost::json::object &o,bool allow_start){
 using esp_brookesia::service::FunctionResult;
 auto fail=[](const char *s)->FunctionResult{return {.success=false,.error_message=s};};
 const auto *s=o.if_contains("s"),*n=o.if_contains("n");
 if(!s||!s->is_string()||s->as_string().size()!=16||!n||!n->is_string()||n->as_string().size()>72)return fail("导航数据格式无效");
 for(unsigned char c:s->as_string())if(!std::isxdigit(c))return fail("导航会话无效");
 for(unsigned char c:n->as_string())if(c<32||c==127)return fail("道路名称无效");
 const int q=integer(o,"q",1000000000),m=integer(o,"m",2),t=integer(o,"t",7),d=integer(o,"d",100000,-1),r=integer(o,"r",1000000,-1),e=integer(o,"e",604800,-1),z=integer(o,"z",2);
 if(q<1||m<0||t<0||d< -1||r< -1||e< -1||z<0)return fail("导航数值无效");
 const std::string incoming(s->as_string());
 // Only the existing BLE worker writes. Do not hold the mutex during
 // start_app(): its runtime reads GetNavigationState on another task.
 bool start=false;
 {std::lock_guard<std::mutex> lock(mutex);
  start=incoming!=session;
  if(start?(q!=1||z!=0):q<=sequence||phase==2||m!=source)return fail("导航会话已结束或数据顺序无效");
 }
 if(z!=2&&!allow_start)return fail("请先解锁并退出儿童模式");
 if(start){
  if(!allow_start)return fail("导航不能启动");
  auto opened=phone_remote::open_navigation();if(!opened.success)return opened;
 }
 {std::lock_guard<std::mutex> lock(mutex);
  session=incoming;sequence=q;source=m;turn=t;distance=d;remaining=r;seconds=e;phase=z;
  road=std::string(n->as_string());received=esp_timer_get_time();
 }
 return {.success=true};
}
}
