#include "phone_provisioning.hpp"
#include "rules.hpp"
#include "remote.hpp"
#include "../audio_ownership.hpp"
#include "../device_modes/deep_sleep.hpp"
#include <algorithm>
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstdio>
#include <cstring>
#include <future>
#include <mutex>
#include <optional>
#include <string>
#include <vector>
#include "brookesia/service_manager/service/manager.hpp"
#include "esp_event.h"
#include "esp_heap_caps.h"
#include "esp_mac.h"
#include "esp_netif.h"
#include "esp_random.h"
#include "esp_timer.h"
#include "esp_wifi.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/idf_additions.h"
#include "brookesia/lib_utils/task_scheduler.hpp"
#include "mbedtls/platform_util.h"
extern "C" {
#include "protocomm.h"
#include "protocomm_ble.h"
#include "protocomm_security1.h"
#include "network_provisioning/network_config.h"
#include "network_provisioning/network_scan.h"
}
static std::atomic<const char *> app_lifecycle_stage{"idle"};
static std::mutex app_error_mutex;
static char app_task_error[256]{};
extern "C" void brookesia_board_app_task_error(const char *message){
    std::lock_guard<std::mutex> lock(app_error_mutex);
    const auto count=std::min(std::strlen(message),sizeof(app_task_error)-1);
    std::memcpy(app_task_error,message,count);app_task_error[count]=0;
}
extern "C" void brookesia_board_app_phase(const char *stage){app_lifecycle_stage=stage;}
using namespace esp_brookesia::service;
namespace {
constexpr unsigned STACK=8192;
std::shared_ptr<esp_brookesia::lib_utils::TaskScheduler> transport_scheduler;
std::mutex mutex;
std::condition_variable scan_ready;
std::atomic<bool> live{false},active{false},cancel{false},ble_connected{false},apply_pending{false},scan_pending{false};
std::atomic<bool> worker_exit{false};
std::atomic<bool> remote_mode{false};
std::mutex remote_mutex;
std::optional<boost::json::object> remote_command;
std::shared_ptr<std::promise<boost::json::object>> remote_reply;
void process_remote_command(bool stopping=false) {
    std::optional<boost::json::object> command;
    std::shared_ptr<std::promise<boost::json::object>> reply;
    {std::lock_guard<std::mutex> lock(remote_mutex);command=std::move(remote_command);remote_command.reset();reply=std::move(remote_reply);}
    if(!reply)return;
    try{reply->set_value(stopping?boost::json::object{{"ok",false},{"error","蓝牙遥控正在关闭"}}:phone_remote::execute(*command));}
    catch(...){reply->set_value(boost::json::object{{"ok",false},{"error","操作失败，请稍后重试"}});}
}
TaskHandle_t worker_task=nullptr;
std::atomic<int> disconnect_reason{0};
std::atomic<unsigned> stack_free{STACK},starts{0},successes{0},ip_events{0};
std::string device_name,pop,status="尚未开启手机配网",ssid,password,old_ssid,old_password;
bool scan_finished=true,attempted=false,connected=false,status_reported=false;
unsigned ip_before=0;
int64_t opened_at=0,applied_at=0,close_at=0;
std::vector<network_prov_scan_wifi_result_t> scans;
protocomm_t *pc=nullptr;
protocomm_security1_params_t security{};
esp_event_handler_instance_t ble_events=nullptr,wifi_events=nullptr,ip_handler=nullptr;
void wipe(std::string &s){if(!s.empty())mbedtls_platform_zeroize(s.data(),s.size());s.clear();}
FunctionResult invoke(const char *name,const boost::json::object &args={}) {
    auto wifi=ServiceManager::get_instance().get_service("Wifi");
    if(!wifi || !wifi->is_running())return {.success=false,.error_message="Wi-Fi service unavailable"};
    return wifi->call_function_sync(name,args,6000);
}
bool action(const char *name){return invoke("TriggerGeneralAction",{{"Action",name}}).success;}
void set_status(std::string text){std::lock_guard<std::mutex> lock(mutex);status=std::move(text);}
void events(void *,esp_event_base_t base,int32_t id,void *data) {
    if(base==PROTOCOMM_TRANSPORT_BLE_EVENT) {
        if(id==PROTOCOMM_TRANSPORT_BLE_CONNECTED)ble_connected=true;
        if(id==PROTOCOMM_TRANSPORT_BLE_DISCONNECTED)ble_connected=false;
    } else if(base==WIFI_EVENT && id==WIFI_EVENT_STA_DISCONNECTED && data)
        disconnect_reason=static_cast<wifi_event_sta_disconnected_t *>(data)->reason;
    else if(base==IP_EVENT && id==IP_EVENT_STA_GOT_IP)++ip_events;
}
esp_err_t get_status(network_prov_config_get_wifi_data_t *out,network_prov_ctx_t **) {
    std::memset(out,0,sizeof(*out));std::lock_guard<std::mutex> lock(mutex);
    if(connected) {
        out->wifi_state=NETWORK_PROV_WIFI_STA_CONNECTED;
        wifi_ap_record_t ap{};esp_netif_ip_info_t ip{};
        if(esp_wifi_sta_get_ap_info(&ap)==ESP_OK){std::memcpy(out->conn_info.bssid,ap.bssid,6);std::memcpy(out->conn_info.ssid,ap.ssid,32);out->conn_info.channel=ap.primary;out->conn_info.auth_mode=ap.authmode;}
        auto *netif=esp_netif_get_handle_from_ifkey("WIFI_STA_DEF");
        if(netif && esp_netif_get_ip_info(netif,&ip)==ESP_OK)std::snprintf(out->conn_info.ip_addr,sizeof(out->conn_info.ip_addr),IPSTR,IP2STR(&ip.ip));
        if(!status_reported){status_reported=true;close_at=esp_timer_get_time()+2000000;}
    } else if(attempted && !applied_at) {
        out->wifi_state=NETWORK_PROV_WIFI_STA_DISCONNECTED;
        out->fail_reason=disconnect_reason==WIFI_REASON_NO_AP_FOUND?NETWORK_PROV_WIFI_STA_AP_NOT_FOUND:NETWORK_PROV_WIFI_STA_AUTH_ERROR;
    } else out->wifi_state=NETWORK_PROV_WIFI_STA_CONNECTING;
    return ESP_OK;
}
esp_err_t set_config(const network_prov_config_set_wifi_data_t *in,network_prov_ctx_t **) {
    const std::string next_ssid(in->ssid,strnlen(in->ssid,sizeof(in->ssid)));
    const std::string_view pass(in->password,strnlen(in->password,sizeof(in->password)));
    if(!active || !phone_provisioning::valid_credentials(next_ssid,pass))return ESP_ERR_INVALID_ARG;
    std::lock_guard<std::mutex> lock(mutex);if(applied_at || apply_pending)return ESP_ERR_INVALID_STATE;
    ssid=next_ssid;wipe(password);password=pass;connected=false;attempted=false;status_reported=false;
    status="已收到网络，等待手机确认";return ESP_OK;
}
esp_err_t apply_config(network_prov_ctx_t **) {
    std::lock_guard<std::mutex> lock(mutex);
    if(!active || !phone_provisioning::valid_credentials(ssid,password) || applied_at || apply_pending)return ESP_ERR_INVALID_STATE;
    apply_pending=true;status="正在连接 Wi-Fi";return ESP_OK;
}
esp_err_t scan_start(bool blocking,bool,uint8_t,uint32_t,network_prov_scan_ctx_t **) {
    std::unique_lock<std::mutex> lock(mutex);if(!active || applied_at || apply_pending)return ESP_ERR_INVALID_STATE;
    scan_finished=false;scan_pending=true;scans.clear();
    if(blocking && !scan_ready.wait_for(lock,std::chrono::seconds(12),[]{return scan_finished || !active;}))return ESP_ERR_TIMEOUT;
    return ESP_OK;
}
esp_err_t scan_status(bool *done,uint16_t *count,network_prov_scan_ctx_t **) {
    std::lock_guard<std::mutex> lock(mutex);*done=scan_finished;*count=static_cast<uint16_t>(scans.size());return ESP_OK;
}
esp_err_t scan_result(uint16_t index,network_prov_scan_wifi_result_t *out,network_prov_scan_ctx_t **) {
    std::lock_guard<std::mutex> lock(mutex);if(index>=scans.size())return ESP_ERR_INVALID_ARG;*out=scans[index];return ESP_OK;
}
network_prov_config_handlers_t config_handlers{.wifi_get_status_handler=get_status,.wifi_set_config_handler=set_config,.wifi_apply_config_handler=apply_config,.ctx=nullptr};
network_prov_scan_handlers_t scan_handlers{.wifi_scan_start=scan_start,.wifi_scan_status=scan_status,.wifi_scan_result=scan_result,.ctx=nullptr};
esp_err_t config_endpoint(uint32_t session,const uint8_t *in,ssize_t size,uint8_t **out,ssize_t *out_size,void *) {
    if(!active || remote_mode || size<=0 || size>2048)return ESP_ERR_INVALID_ARG;
    return network_prov_config_data_handler(session,in,size,out,out_size,&config_handlers);
}
esp_err_t scan_endpoint(uint32_t session,const uint8_t *in,ssize_t size,uint8_t **out,ssize_t *out_size,void *) {
    if(!active || remote_mode || size<=0 || size>512)return ESP_ERR_INVALID_ARG;
    return network_prov_scan_handler(session,in,size,out,out_size,&scan_handlers);
}
esp_err_t remote_endpoint(uint32_t,const uint8_t *in,ssize_t size,uint8_t **out,ssize_t *out_size,void *) {
    if(!active || !remote_mode || size<=0 || size>256)return ESP_ERR_INVALID_ARG;
    boost::system::error_code error;auto request=boost::json::parse(std::string_view(reinterpret_cast<const char *>(in),size),error);
    if(error || !request.is_object())return ESP_ERR_INVALID_ARG;
    auto pending=std::make_shared<std::promise<boost::json::object>>();auto future=pending->get_future();
    {std::lock_guard<std::mutex> lock(remote_mutex);
     if(!active || !remote_mode || remote_reply)return ESP_ERR_INVALID_STATE;
     remote_command=std::move(request.as_object());remote_reply=pending;}
    auto response=boost::json::serialize(future.get());
    if(response.size()>480)response=R"({"ok":false,"error":"列表名称过长"})";
    *out=static_cast<uint8_t *>(malloc(response.size()));if(!*out)return ESP_ERR_NO_MEM;
    memcpy(*out,response.data(),response.size());*out_size=response.size();return ESP_OK;
}
bool begin() {
    // S3's ROM controller needs a contiguous 0x7800-byte DMA block. Failing
    // this allocation can assert inside the ROM rather than return NO_MEM.
    if(heap_caps_get_largest_free_block(MALLOC_CAP_INTERNAL|MALLOC_CAP_DMA)<0x7800 ||
       heap_caps_get_free_size(MALLOC_CAP_INTERNAL|MALLOC_CAP_DMA)<40*1024){
        set_status("内存不足，请先关闭其他应用再重试");return false;
    }
    if(!remote_mode && !action("Start")){set_status("请先打开 Wi-Fi");return false;}
    uint8_t mac[6]{};esp_read_mac(mac,ESP_MAC_WIFI_STA);char name[24];std::snprintf(name,sizeof(name),"%s_%02X%02X%02X",remote_mode?"CTRL":"PROV",mac[3],mac[4],mac[5]);
    char code[9];std::snprintf(code,sizeof(code),"%08lX",static_cast<unsigned long>(esp_random()));
    {std::lock_guard<std::mutex> lock(mutex);device_name=name;pop=code;attempted=connected=status_reported=false;applied_at=close_at=0;scan_finished=true;scans.clear();wipe(password);ssid.clear();
     security.data=reinterpret_cast<const uint8_t *>(pop.data());security.len=static_cast<uint16_t>(pop.size());}
    mbedtls_platform_zeroize(code,sizeof(code));
    auto previous=remote_mode?FunctionResult{.success=false}:invoke("GetConnectAp");
    if(previous.success && previous.data && std::holds_alternative<boost::json::object>(*previous.data)){
        const auto &value=std::get<boost::json::object>(*previous.data);std::lock_guard<std::mutex> lock(mutex);
        if(const auto *v=value.if_contains("ssid");v && v->is_string())old_ssid=v->as_string().c_str();
        if(const auto *v=value.if_contains("password");v && v->is_string())old_password=v->as_string().c_str();
    }
    pc=protocomm_new();if(!pc){set_status("配网内存不足");return false;}
    static protocomm_ble_name_uuid_t endpoints[]={{"prov-session",0xff51},{"prov-config",0xff52},{"proto-ver",0xff53},{"prov-scan",0xff54}};
    static protocomm_ble_name_uuid_t controls[]={{"prov-session",0xff51},{"proto-ver",0xff53},{"remote-control",0xff55}};
    protocomm_ble_config_t cfg{};std::memcpy(cfg.device_name,name,strlen(name)+1);
    const uint8_t uuid[16]={0x07,0xed,0x9b,0x2d,0x0f,0x06,0x7c,0x87,0x9b,0x43,0x43,0x6b,0x4d,0x24,0x75,0x17};
    std::memcpy(cfg.service_uuid,uuid,16);cfg.nu_lookup=remote_mode?controls:endpoints;cfg.nu_lookup_count=remote_mode?3:4;
    if(esp_event_handler_instance_register(PROTOCOMM_TRANSPORT_BLE_EVENT,ESP_EVENT_ANY_ID,events,nullptr,&ble_events)!=ESP_OK ||
       esp_event_handler_instance_register(WIFI_EVENT,WIFI_EVENT_STA_DISCONNECTED,events,nullptr,&wifi_events)!=ESP_OK ||
       esp_event_handler_instance_register(IP_EVENT,IP_EVENT_STA_GOT_IP,events,nullptr,&ip_handler)!=ESP_OK){set_status("无法监听配网状态");return false;}
    const auto err=protocomm_ble_start(pc,&cfg);if(err!=ESP_OK){set_status(std::string("蓝牙启动失败：")+esp_err_to_name(err));return false;}
    if(protocomm_set_version(pc,"proto-ver",R"({"prov":{"ver":"v1.1","sec_ver":1,"sec_patch_ver":0,"cap":["wifi_scan"]}})")!=ESP_OK ||
       protocomm_set_security(pc,"prov-session",&protocomm_security1,&security)!=ESP_OK ||
       (remote_mode?protocomm_add_endpoint(pc,"remote-control",remote_endpoint,nullptr):protocomm_add_endpoint(pc,"prov-config",config_endpoint,nullptr))!=ESP_OK ||
       (!remote_mode && protocomm_add_endpoint(pc,"prov-scan",scan_endpoint,nullptr)!=ESP_OK)){set_status("蓝牙协议启动失败");return false;}
    opened_at=esp_timer_get_time();active=true;set_status(remote_mode?"请在小马遥控中连接设备":"请在 ESP BLE Prov 中添加设备");++starts;return true;
}
void finish() {
    active=false;ble_connected=false;
    scan_ready.notify_all();
    process_remote_command(true);
    if(pc){protocomm_ble_stop(pc);protocomm_delete(pc);pc=nullptr;}
    if(ble_events){esp_event_handler_instance_unregister(PROTOCOMM_TRANSPORT_BLE_EVENT,ESP_EVENT_ANY_ID,ble_events);ble_events=nullptr;}
    if(wifi_events){esp_event_handler_instance_unregister(WIFI_EVENT,WIFI_EVENT_STA_DISCONNECTED,wifi_events);wifi_events=nullptr;}
    if(ip_handler){esp_event_handler_instance_unregister(IP_EVENT,IP_EVENT_STA_GOT_IP,ip_handler);ip_handler=nullptr;}
    std::string restore_ssid,restore_password;
    {std::lock_guard<std::mutex> lock(mutex);if(attempted && !connected){restore_ssid=old_ssid;restore_password=old_password;}if(cancel && !connected)status=remote_mode?"蓝牙遥控已关闭":"手机配网已关闭";
     wipe(pop);wipe(password);wipe(old_password);old_ssid.clear();security={};applied_at=0;apply_pending=false;scan_pending=false;scan_finished=true;scans.clear();}
    if(!restore_ssid.empty() && phone_provisioning::valid_credentials(restore_ssid,restore_password)){
        invoke("SetConnectAp",{{"SSID",restore_ssid},{"Password",restore_password}});action("Connect");
    }wipe(restore_password);scan_ready.notify_all();
}
bool transport(bool start) {
    // Controller/PHY initialization may access Flash. Execute it on the
    // existing internal-RAM service scheduler, never on the PSRAM coordinator.
    std::promise<bool> result;auto ready=result.get_future();
    if(!transport_scheduler || !transport_scheduler->post([start,&result]{
        if(start)result.set_value(begin());else{finish();result.set_value(true);}
    }))return false;
    return ready.get();
}
void run() {
    auto wifi=ServiceManager::get_instance().get_service("Wifi");EventSignalConnection scan_connection;
    if(wifi)scan_connection=wifi->subscribe_event("ScanApInfosUpdated",[](const std::string &,const EventItemMap &items){
        const auto it=items.find("ApInfos");if(it==items.end())return;const auto *list=std::get_if<boost::json::array>(&it->second);if(!list)return;
        std::lock_guard<std::mutex> lock(mutex);if(scan_finished)return;scans.clear();
        for(const auto &entry:*list){if(scans.size()>=16)break;if(!entry.is_object())continue;const auto &obj=entry.as_object();const auto *n=obj.if_contains("ssid");if(!n||!n->is_string()||n->as_string().empty())continue;
            network_prov_scan_wifi_result_t value{};const auto &text=n->as_string();std::memcpy(value.ssid,text.data(),std::min(size_t(32),text.size()));
            if(const auto *r=obj.if_contains("rssi");r&&r->is_int64())value.rssi=int(r->as_int64());
            if(const auto *r=obj.if_contains("channel");r&&r->is_int64())value.channel=uint8_t(r->as_int64());
            const auto *locked=obj.if_contains("is_locked");value.auth=locked && locked->is_bool() && locked->as_bool()?WIFI_AUTH_WPA2_PSK:WIFI_AUTH_OPEN;scans.push_back(value);
        }scan_finished=true;scan_ready.notify_all();
    });
    const bool started=transport(true);int64_t scan_at=0;
    while(started && active && !cancel) {
        // Reuse the PSRAM coordinator instead of blocking a ServiceManager
        // worker while app lifecycles make nested synchronous service calls.
        process_remote_command();
        const auto now=esp_timer_get_time();
        if(phone_provisioning::expired(now,opened_at,remote_mode?1800:phone_provisioning::WINDOW_SECONDS)){set_status("蓝牙连接已超时，请重新开始");break;}
        if(scan_pending.exchange(false)){scan_at=now;if(!invoke("TriggerScanStart").success){std::lock_guard<std::mutex> lock(mutex);scan_finished=true;scan_ready.notify_all();}}
        if(apply_pending.exchange(false)) {
            std::string target,pass;{std::lock_guard<std::mutex> lock(mutex);target=ssid;pass=password;wipe(password);attempted=true;connected=false;disconnect_reason=0;ip_before=ip_events;applied_at=now;}
            invoke("TriggerScanStop");bool ok=invoke("SetConnectAp",{{"SSID",target},{"Password",pass}}).success;wipe(pass);if(ok)ok=action("Connect");
            if(!ok){std::lock_guard<std::mutex> lock(mutex);applied_at=0;status="连接未开始，请在手机重试";}
        }
        {std::lock_guard<std::mutex> lock(mutex);
         if(!scan_finished && scan_at && now-scan_at>10000000){scan_finished=true;scan_ready.notify_all();}
         if(applied_at && now-applied_at>500000) {
            wifi_ap_record_t ap{};esp_netif_ip_info_t ip{};auto *netif=esp_netif_get_handle_from_ifkey("WIFI_STA_DEF");
            const bool matches=ip_events>ip_before && esp_wifi_sta_get_ap_info(&ap)==ESP_OK && ssid==std::string(reinterpret_cast<char *>(ap.ssid),strnlen(reinterpret_cast<char *>(ap.ssid),32));
            if(matches && netif && esp_netif_get_ip_info(netif,&ip)==ESP_OK && ip.ip.addr){connected=true;applied_at=0;close_at=now+30000000;status="配网完成，已连接 Wi-Fi";++successes;}
            else if(phone_provisioning::expired(now,applied_at,phone_provisioning::CONNECT_SECONDS)){applied_at=0;status="连接失败，请检查密码后重试";}
         }if(connected && close_at && now>=close_at)break;
        }
        stack_free=std::min(stack_free.load(),static_cast<unsigned>(uxTaskGetStackHighWaterMark(nullptr)));vTaskDelay(pdMS_TO_TICKS(100));
    }
    scan_connection.disconnect();transport(false);live=false;
}
bool request_start(bool remote=false) {
    if(brookesia_board_deep_sleep_pending() || local_audio::busy()){set_status("请先停止播放或录音");return false;}
    bool expected=false;if(!live.compare_exchange_strong(expected,true))return remote_mode==remote;
    remote_mode=remote;
    cancel=false;set_status(remote?"正在开启蓝牙遥控":"正在开启手机配网");
    if(!worker_task){live=false;set_status("手机配网服务尚未就绪");return false;}
    xTaskNotifyGive(worker_task);return true;
}
boost::json::object snapshot(bool setup=false) {
    std::lock_guard<std::mutex> lock(mutex);
    boost::json::object result{{"active",active.load()},{"starting",live.load()&&!active.load()},{"ble_connected",ble_connected.load()},{"status",status},{"device_name",device_name},{"security",1},{"starts",starts.load()},{"successes",successes.load()},{"connected",connected},{"stack_free_min_bytes",stack_free.load()},{"internal_free_bytes",heap_caps_get_free_size(MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT)},{"largest_dma_block",heap_caps_get_largest_free_block(MALLOC_CAP_INTERNAL|MALLOC_CAP_DMA)},{"psram_free_bytes",heap_caps_get_free_size(MALLOC_CAP_SPIRAM)}};
    result["app_lifecycle_stage"]=app_lifecycle_stage.load();
    {std::lock_guard<std::mutex> lock(app_error_mutex);result["last_task_error"]=app_task_error;}
    result["dma_free_bytes"]=heap_caps_get_free_size(MALLOC_CAP_INTERNAL|MALLOC_CAP_DMA);
    result["mode"]=remote_mode?"remote":"provisioning";
    if(active)result["remaining_seconds"]=std::max<int64_t>(0,(remote_mode?1800:phone_provisioning::WINDOW_SECONDS)-(esp_timer_get_time()-opened_at)/1000000);
    if(setup && active)result["pop"]=pop;
    return result;
}
class PhoneProvisioning final: public ServiceBase {
public: PhoneProvisioning():ServiceBase({.name="PhoneProvisioning",.description="Encrypted phone BLE Wi-Fi provisioning",.version="0.1.0",.dependencies={}}){}
private:
    bool on_start()override{
        // The coordinator only waits and calls services. Keep its stack out of
        // scarce DMA RAM; Flash-sensitive transport work uses the scheduler.
        worker_exit=false;
        transport_scheduler=get_task_scheduler();
        const bool created=xTaskCreatePinnedToCoreWithCaps([](void *){
            while(!worker_exit){ulTaskNotifyTake(pdTRUE,portMAX_DELAY);if(!worker_exit && live)run();}
            worker_task=nullptr;vTaskDeleteWithCaps(nullptr);
        },"phone_prov",STACK,nullptr,3,&worker_task,0,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT)==pdPASS;
        return created;
    }
    void on_stop()override{cancel=true;worker_exit=true;scan_ready.notify_all();if(worker_task)xTaskNotifyGive(worker_task);while(worker_task)vTaskDelay(pdMS_TO_TICKS(20));}
    std::vector<FunctionSchema> get_function_schemas()override{return {{"GetState","Read provisioning status without credentials",{},true,std::nullopt,FunctionReturnSchema{FunctionValueType::Object,"Status"}},{"GetSetup","Read temporary local pairing code while open",{},true,std::nullopt,FunctionReturnSchema{FunctionValueType::Object,"Setup"}},{"GetWifiScreen","Read a reviewed Settings JSON document for migration",{{"Document","Settings document",FunctionValueType::String,std::string("screens/wifi.json")}},true,std::nullopt,FunctionReturnSchema{FunctionValueType::Object,"Wi-Fi screen"}},{"StartRemote","Open encrypted Bluetooth remote control",{}},{"Start","Open a five-minute phone provisioning window",{}},{"Stop","Close the provisioning window",{}}};}
    FunctionHandlerList get_function_handlers()override{return {{"GetState",[](FunctionParameterMap&&)->FunctionResult{return {.success=true,.data=FunctionValue(snapshot())};}},{"GetSetup",[](FunctionParameterMap&&)->FunctionResult{return {.success=true,.data=FunctionValue(snapshot(true))};}},{"GetWifiScreen",[](FunctionParameterMap&&params)->FunctionResult{
        const auto document=std::get<std::string>(params.at("Document"));
        if(document!="root.json" && document!="flows/content.json" && document!="screens/settings_home.json" && document!="screens/bluetooth.json" && document!="screens/wifi.json")return {.success=false,.error_message="Unsupported Settings document"};
        auto storage=ServiceManager::get_instance().get_service("Storage");
        if(!storage || !storage->is_running())return {.success=false,.error_message="Storage unavailable"};
        auto result=storage->call_function_sync("FSReadText",boost::json::object{{"Path",std::string("/littlefs/apps/brookesia.general.settings/res/")+document}},6000);
        if(!result.success || !result.data || !std::holds_alternative<std::string>(*result.data))return {.success=false,.error_message="Wi-Fi screen unavailable"};
        boost::system::error_code error;auto value=boost::json::parse(std::get<std::string>(*result.data),error);
        if(error || !value.is_object())return {.success=false,.error_message="Invalid Wi-Fi screen"};
        return {.success=true,.data=FunctionValue(std::move(value.as_object()))};
    }},{"StartRemote",[](FunctionParameterMap&&)->FunctionResult{return {.success=request_start(true)};}},{"Start",[](FunctionParameterMap&&)->FunctionResult{const bool ok=request_start();return {.success=ok,.error_message=ok?"":"Please stop audio or close other apps"};}},{"Stop",[](FunctionParameterMap&&)->FunctionResult{cancel=true;return {.success=true};}}};}
};
}
std::shared_ptr<ServiceBase> make_phone_provisioning_service(){return std::make_shared<PhoneProvisioning>();}
extern "C" bool brookesia_board_phone_provisioning_start(){return request_start();}
extern "C" bool brookesia_board_phone_remote_start(){return request_start(true);}
extern "C" void brookesia_board_phone_provisioning_stop(){cancel=true;}
extern "C" bool brookesia_board_phone_provisioning_active(){return live;}
extern "C" const char *brookesia_board_phone_provisioning_text(){thread_local std::string text;std::lock_guard<std::mutex> lock(mutex);text=status;if(active)text+="\n设备："+device_name+"\n配对码："+pop;return text.c_str();}
