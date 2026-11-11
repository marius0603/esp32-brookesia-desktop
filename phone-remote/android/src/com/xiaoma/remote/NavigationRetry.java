package com.xiaoma.remote;

/** Bounded recovery; never changes notification consent or reuses failed sequence numbers. */
final class NavigationRetry {
 private int failures=0;private long after=0;
 boolean ready(long now){return failures<3&&now>=after;}
 void failed(long now){failures++;after=now+5000;}
 void reset(){failures=0;after=0;}
 boolean blocked(){return failures>=3;}
}
