package com.xiaoma.remote;
import android.content.Context;
import com.amap.api.maps.MapsInitializer;
import com.amap.api.navi.AMapNavi;
import com.amap.api.navi.model.*;
import com.amap.api.location.*;

/** Compile-only check: never execute against a provider or Android device. */
final class NavigationSdkApiProbe {
 void verify(Context context,AMapNavi n,NaviInfo info)throws Exception{
  MapsInitializer.updatePrivacyShow(context,true,true);MapsInitializer.updatePrivacyAgree(context,true);
  n.calculateWalkRoute(new NaviLatLng(31.23,121.47),new NaviLatLng(31.24,121.49));
  n.setUseInnerVoice(false);n.setTrafficStatusUpdateEnabled(false);n.setTrafficInfoUpdateEnabled(false);n.setTrafficSignalEnable(false);n.setIsNaviTravelView(true);
  n.startNavi(2);n.stopNavi();AMapNavi.destroy();
  info.getNextRoadName();info.getIconType();info.getCurStepRetainDistance();info.getPathRetainDistance();info.getPathRetainTime();
  AMapLocationClient.updatePrivacyShow(context,true,true);AMapLocationClient.updatePrivacyAgree(context,true);
  AMapLocationClient location=new AMapLocationClient(context);
  AMapLocationClientOption option=new AMapLocationClientOption();option.setOnceLocation(true);option.setOnceLocationLatest(true);option.setNeedAddress(false);option.setHttpTimeOut(10000L);option.setSelfStartServiceEnable(false);
  AMapLocationClientOption.setLocationProtocol(AMapLocationClientOption.AMapLocationProtocol.HTTPS);
  location.setLocationOption(option);location.setLocationListener(value->{value.getErrorCode();value.getLatitude();value.getLongitude();value.getAccuracy();});location.startLocation();location.stopLocation();location.onDestroy();
 }
}
