#include "navigation.hpp"
#include "brookesia/system_super/system.hpp"
#include <atomic>
namespace phone_remote {
namespace {std::atomic<esp_brookesia::system::super::System *> owner{nullptr};}
void attach_system(esp_brookesia::system::super::System *system){owner=system;}
esp_brookesia::service::FunctionResult open_audiobook(){
 auto *system=owner.load();if(!system)return {.success=false,.error_message="桌面尚未就绪"};
 for(const auto &app:system->list_apps())
  if(app.manifest.id=="local.audiobook")return open_app(app.app_id);
 return {.success=false,.error_message="听书应用尚未安装"};
}
esp_brookesia::service::FunctionResult open_app(int id){
 using namespace esp_brookesia::system::core;
 auto *system=owner.load();if(!system)return {.success=false,.error_message="桌面尚未就绪"};
 const auto app=system->get_app(id);if(!app)return {.success=false,.error_message="应用不存在，请刷新列表"};
 auto result=std::expected<void,std::string>{};
 if(app->manifest.id=="brookesia.system.super.shell")result=system->navigate_home();
 else {
  // Native apps can stay Running after losing the foreground. start_app()
  // intentionally no-ops in that state; restart the native view to mount it
  // again and run Super's foreground hook. Runtime apps already handle this.
  if(app->manifest.kind==AppKind::Native && (app->state==AppState::Running || app->state==AppState::Paused)){
   result=system->stop_app(id);if(!result)return {.success=false,.error_message=result.error()};
  }
  result=system->start_app(id);
 }
 return {.success=bool(result),.error_message=result?"":result.error()};
}
}
