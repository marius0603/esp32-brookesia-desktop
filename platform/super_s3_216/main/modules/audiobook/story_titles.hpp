#pragma once
#include <string>
#include <string_view>
#include <utility>
namespace story_titles {
inline std::string title(std::string_view path) {
    const auto slash=path.find_last_of('/');const auto file=slash==path.npos?path:path.substr(slash+1);
    static constexpr std::pair<std::string_view,std::string_view> names[]={
        {"01-xiaoma-yueliang.mp3", "小马和月亮灯"},
        {"02-gudong.mp3", "咕咚"},
        {"03-xiaokedou-zhao-mama.mp3", "小蝌蚪找妈妈"},
        {"04-wuya-heshui.mp3", "乌鸦喝水"},
        {"05-xiaohouzi-xiashan.mp3", "小猴子下山"},
        {"06-hujiahuwei.mp3", "狐假虎威"},
        {"07-zuojingguantian.mp3", "坐井观天"},
        {"08-xiaoma-guohe.mp3", "小马过河"},
        {"09-xuehaizi.mp3", "雪孩子"},
        {"10-wangyangbulao.mp3", "亡羊补牢"},
    };
    for(const auto &[name,title]:names)if(file==name)return std::string(title);
    const auto dot=file.find_last_of('.');return std::string(dot==file.npos?file:file.substr(0,dot));
}
}
