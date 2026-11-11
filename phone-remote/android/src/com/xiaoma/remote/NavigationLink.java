package com.xiaoma.remote;
import org.json.JSONObject;

/** UI-thread bridge to MainActivity's one authenticated, serialized GATT session. */
final class NavigationLink {
 interface Reply { void done(String error); }
 interface Transport {
  boolean available();
  boolean send(JSONObject packet, Reply reply);
 }
 static Transport transport;
 private NavigationLink() {}
}
