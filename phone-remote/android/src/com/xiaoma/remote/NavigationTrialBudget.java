package com.xiaoma.remote;

/** Limits this experimental app's explicit online attempts, including failures. */
final class NavigationTrialBudget {
 static final int DAILY_LIMIT=5;
 static int used(String recordedDay,int recordedCount,String today){
  if(recordedDay.compareTo(today)>0)return DAILY_LIMIT; // Clock rollback never grants more requests.
  return recordedDay.equals(today)?Math.max(0,recordedCount):0;
 }
 static boolean allowed(boolean confirmed,boolean busy,int count){return confirmed&&!busy&&count<DAILY_LIMIT;}
}
