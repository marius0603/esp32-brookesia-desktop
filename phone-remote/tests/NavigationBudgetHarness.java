package com.xiaoma.remote;
public class NavigationBudgetHarness {
 static void check(boolean value){if(!value)throw new AssertionError();}
 public static void main(String[] args){
  check(NavigationTrialBudget.used("2026-11-11",4,"2026-11-11")==4);
  check(NavigationTrialBudget.used("2026-11-11",5,"2026-11-12")==0);
  check(NavigationTrialBudget.used("2026-11-12",1,"2026-11-11")==5);
  for(int n=0;n<5;n++)check(NavigationTrialBudget.allowed(true,false,n));
  check(!NavigationTrialBudget.allowed(true,false,5));
  check(!NavigationTrialBudget.allowed(true,true,0));
  check(!NavigationTrialBudget.allowed(false,false,0));
  System.out.println("Navigation trial budget: five manual attempts, consent/busy gate, new day and clock rollback passed.");
 }
}
