#include "sd_resources.hpp"
#include <atomic>
#include <cstring>
#include <sys/stat.h>
#include "brookesia/service_helper/system/storage.hpp"

using namespace esp_brookesia::service;
namespace {
struct Asset {const char *name,*flash,*sd,*fallback;};
#define ASSET(name,app,ext) {name ".png","/littlefs/themes/cream-handdrawn-v1/" name ".png", \
    "/sdcard/themes/cartoon-q-v1/" name ".png","/littlefs/apps/" app "/res/images/launcher_icon." ext}
constexpr Asset assets[]{
    ASSET("settings","brookesia.general.settings","jpg"),
    ASSET("files","brookesia.general.files","jpg"),
    ASSET("app-store","brookesia.general.app_store","jpg"),
    ASSET("quota","local.codex.quota","png"),
    ASSET("weather","local.weather","png"),
    ASSET("audiobook","local.audiobook","png"),
    ASSET("flipclock","local.flipclock","png"),
    ASSET("assistant","local.voiceassistant","png"),
    ASSET("child-mode","local.childmode","png"),
    {"wallpaper-486-rgb565.bin","/littlefs/themes/cream-handdrawn-v1/wallpaper-486-rgb565.bin",
     "/sdcard/themes/cartoon-q-v1/wallpaper-486-rgb565.bin","/littlefs/themes/cream-handdrawn-v1/wallpaper.jpg"},
    {"wallpaper.jpg","/littlefs/themes/cream-handdrawn-v1/wallpaper.jpg",
     "/sdcard/themes/cartoon-q-v1/wallpaper.jpg","/littlefs/themes/cream-handdrawn-v1/wallpaper.jpg"}
};
#undef ASSET
std::atomic<unsigned> sd_resolutions{0},flash_resolutions{0};
bool exists(const char *path) {
    // The GUI thread has a PSRAM stack. Route Flash metadata reads through
    // Storage's internal-stack scheduler, just like the existing image loader.
    auto info=esp_brookesia::service::helper::Storage::fs_stat(path);
    return info && info->exists && info->size>0;
}
const char *choose(const Asset &a) {
    if(exists(a.sd))return a.sd;
    if(exists(a.flash))return a.flash;
    return a.fallback;
}
class SdResources final:public ServiceBase {
public:
    SdResources():ServiceBase({.name="SdResources",.description="SD theme resources with internal fallbacks",.version="0.1.0",.dependencies={}}){}
private:
    std::vector<FunctionSchema> get_function_schemas() override {
        return {{"GetState","Get selected image paths",{},true,std::nullopt,FunctionReturnSchema{FunctionValueType::Object,"Selected assets"}}};
    }
    FunctionHandlerList get_function_handlers() override {
        return {{"GetState",[](FunctionParameterMap &&)->FunctionResult{
            boost::json::array files;
            for(const auto &a:assets) {
                const char *selected=choose(a);
                struct stat st{};const bool present=stat(selected,&st)==0 && S_ISREG(st.st_mode);
                files.push_back(boost::json::object{{"name",a.name},{"selected",selected},
                    {"on_sd",selected==a.sd},{"exists",present},{"bytes",present?st.st_size:0}});
            }
            return {.success=true,.data=FunctionValue(boost::json::object{{"theme","cartoon-q-v1"},{"files",std::move(files)},
                    {"sd_resolutions",sd_resolutions.load()},{"flash_resolutions",flash_resolutions.load()}})};
        }}};
    }
};
}
std::shared_ptr<ServiceBase> make_sd_resources_service(){return std::make_shared<SdResources>();}
extern "C" const char *brookesia_board_image_path(const char *path) {
    for(const auto &a:assets)if(std::strcmp(path,a.flash)==0) {
        const char *selected=choose(a);
        if(selected==a.sd)++sd_resolutions;else ++flash_resolutions;
        return selected;
    }
    return path;
}
extern "C" bool brookesia_board_image_needs_resolution(const char *path) {
    for(const auto &a:assets)if(std::strcmp(path,a.flash)==0)return true;
    return false;
}
