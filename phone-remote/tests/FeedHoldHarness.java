package com.xiaoma.remote;

public final class FeedHoldHarness {
    private static void require(boolean condition) {
        if (!condition) throw new AssertionError("Feed hold state mismatch");
    }

    public static void main(String[] args) {
        FeedHold hold = new FeedHold(-25);
        for (int rssi : new int[]{-37,-32,-41,-27,-28,-26,0}) require(!hold.observe(rssi));
        require(!hold.claimSend());
        require(!hold.observe(-24));
        require(!hold.observe(-23));
        require(!hold.observe(-27)); // Break a partially held streak.
        require(!hold.observe(-25));
        require(!hold.observe(-22));
        require(hold.observe(-23) && hold.claimSend() && hold.sent());
        require(!hold.observe(-22) && !hold.claimSend());

        FeedHold cancelled = new FeedHold(-25);
        require(!cancelled.observe(-25));
        require(!cancelled.observe(-24));
        require(cancelled.observe(-23));
        cancelled.release();
        require(!cancelled.claimSend() && !cancelled.sent() && !cancelled.observe(-23));
        System.out.println("Feed gesture: weak samples, stable threshold, one dispatch and pre-write release passed.");
    }
}
