#pragma once
#include <string>
#include <vector>
#include <string_view>
#include <cstdint>
namespace radio_playlist {
struct Segment {uint64_t sequence;std::string url;};
inline std::string resolve(const std::string &base,std::string_view path){
 if(path.starts_with("https://")||path.starts_with("http://"))return std::string(path);
 if(path.empty()||path.starts_with("//")||path.find(':')!=path.npos)return {};
 const auto scheme=base.find("://"),hostend=base.find('/',scheme==base.npos?0:scheme+3);
 if(scheme==base.npos)return {};
 const auto origin=hostend==base.npos?base:base.substr(0,hostend);
 if(path.front()=='/')return origin+std::string(path);
 const auto clean=base.substr(0,base.find('?'));return clean.substr(0,clean.find_last_of('/')+1)+std::string(path);
}
struct Playlist {std::vector<Segment> segments;std::string nested,error;};
inline Playlist parse(const std::string &base,std::string_view text){
 Playlist out;uint64_t seq=0;bool variant=false;
 if(!text.starts_with("#EXTM3U")){out.error="Invalid HLS playlist";return out;}
 for(size_t at=0;at<text.size();){
  auto end=text.find('\n',at);if(end==text.npos)end=text.size();auto line=text.substr(at,end-at);at=end+1;
  if(!line.empty()&&line.back()=='\r')line.remove_suffix(1);
  if(line.starts_with("#EXT-X-KEY:")&&line.find("METHOD=NONE")==line.npos){out.error="Encrypted HLS unsupported";return out;}
  if(line.starts_with("#EXT-X-MAP:")||line.starts_with("#EXT-X-BYTERANGE:")){out.error="Only MPEG-TS HLS supported";return out;}
  if(line.starts_with("#EXT-X-MEDIA-SEQUENCE:")){auto value=line.substr(22);if(value.empty()){out.error="Invalid HLS sequence";return out;}for(char c:value){if(c<'0'||c>'9'||seq>UINT64_MAX/10-10){out.error="Invalid HLS sequence";return out;}seq=seq*10+c-'0';}}
  if(line.starts_with("#EXT-X-STREAM-INF:")){variant=true;continue;}
  if(line.empty()||line.front()=='#')continue;
  auto url=resolve(base,line);if(url.empty()){out.error="Invalid HLS URI";return out;}
  if(variant){out.nested=url;return out;}
  out.segments.push_back({seq++,std::move(url)});if(out.segments.size()>128){out.error="HLS playlist too large";return out;}
 }
 return out;
}
}
