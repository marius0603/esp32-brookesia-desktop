#pragma once
#include <cmath>
namespace offline_commands {
struct Phrase { int id; const char *pinyin; };
inline constexpr Phrase phrases[]={
 {1,"jiang gu shi"},{1,"ting gu shi"},{1,"gu shi"},{1,"jiang gu si"},{1,"wo yao ting gu shi"},{1,"gei wo jiang ge gu shi"},{1,"bo fang gu shi"},
 {2,"zan ting"},{2,"ting ting"},{2,"bu ting le"},{2,"ting yi xia"},{2,"zan ting gu shi"},
 {3,"ji xu"},{3,"hai yao ting"},{3,"ji su"},{3,"ji xu bo fang"},{3,"ji xu jiang gu shi"},
 {4,"xia yi pian"},{4,"huan yi ge"},{4,"huan yi ge gu shi"},{4,"xia yi ge gu shi"},
 {5,"da sheng dian"},{5,"da yi dian"},{5,"da shen dian"},{5,"da sheng yi dian"},{5,"sheng yin da yi dian"},
 {6,"xiao sheng dian"},{6,"xiao yi dian"},{6,"xiao shen dian"},{6,"xiao sheng yi dian"},{6,"sheng yin xiao yi dian"},
 {7,"wan an"},{7,"shui jiao jiao"},{7,"shui jiao le"},{7,"wo yao shui jiao le"},{7,"wo yao shui jiao"},
 {8,"hai you duo jiu"},{8,"hai duo jiu"},{8,"hai sheng duo shao shi jian"},{8,"hai sheng ji fen zhong"}
};
// Competing variants of the same intent are harmless; ambiguous intents need a retry.
inline constexpr bool accept(int id,float score,int runner,float other) {
 // Short benign intents use a lower floor after WakeNet; starting/changing
 // playback and changing volume keep the higher floor. Both require a margin.
 const float minimum=(id==2 || id==3 || id==7 || id==8)?0.45f:0.62f;
 return id>=1 && id<=8 && score>=minimum && score<=1.0f &&
        (runner==id || runner==0 || (other>=0 && other<=1 && score-other>=0.15f));
}
inline constexpr const char *names[]={"","讲故事","暂停","继续","下一篇","大声点","小声点","晚安","还有多久"};
}
