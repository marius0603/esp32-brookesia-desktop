package com.xiaoma.remote;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Random;

/** Resolve the device's current story against its freshly fetched BLE book list. */
final class StoryNavigation {
 static String displayName(String title){
  String name=title.substring(title.lastIndexOf('/')+1);int dot=name.lastIndexOf('.');
  if(dot>=0)name=name.substring(0,dot);
  while(name.getBytes(StandardCharsets.UTF_8).length>60)name=name.substring(0,name.offsetByCodePoints(name.length(),-1));
  return name;
 }
 static int next(List<String> names,String current,String mode,Random random){
  if(names.isEmpty())throw new IllegalArgumentException("SD卡中没有故事");
  int at=-1;String name=displayName(current);
  for(int i=0;i<names.size();i++)if(names.get(i).equals(name)){
   if(at>=0)throw new IllegalArgumentException("存在同名故事，请从书架选择下一篇");at=i;
  }
  if(at<0){if(current.isEmpty())return 0;throw new IllegalArgumentException("当前故事不在书架中，请刷新后选择故事");}
  if("random".equals(mode)&&names.size()>1){int chosen=random.nextInt(names.size()-1);return chosen>=at?chosen+1:chosen;}
  return (at+1)%names.size();
 }
}
