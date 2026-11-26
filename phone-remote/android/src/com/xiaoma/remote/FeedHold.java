package com.xiaoma.remote;

/** One press owns its RSSI streak and can put at most one command on the wire. */
final class FeedHold {
    private final int threshold;
    private volatile boolean held = true;
    private volatile boolean sent;
    private int consecutive;

    FeedHold(int threshold) { this.threshold = threshold; }

    boolean held() { return held; }
    boolean sent() { return sent; }

    boolean observe(int rssi) {
        if (!held || sent) return false;
        consecutive = rssi >= threshold && rssi < 0 ? consecutive + 1 : 0;
        return consecutive >= 3;
    }

    synchronized boolean claimSend() {
        if (!held || sent || consecutive < 3) return false;
        sent = true;
        return true;
    }

    synchronized void release() { held = false; }
}
