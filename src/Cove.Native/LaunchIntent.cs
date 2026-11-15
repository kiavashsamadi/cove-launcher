using System;

internal enum LaunchIntent { Home, Open, Other }
internal static class LaunchIntentPolicy {
 internal static LaunchIntent Classify(string? operation,string? entryPoint){
  // Never equate every app-control callback with a physical Home press.
  // The TV-specific marker still needs verification on the target firmware.
  bool ordinary=String.IsNullOrEmpty(operation)||operation=="http://tizen.org/appcontrol/operation/default";
  bool main=operation=="http://tizen.org/appcontrol/operation/main";
  if(entryPoint=="smarthub_key"&&(ordinary||main))return LaunchIntent.Home;
  if(!String.IsNullOrEmpty(entryPoint))return LaunchIntent.Other;
  if(main)return LaunchIntent.Home;
  return ordinary?LaunchIntent.Open:LaunchIntent.Other;
 }
}
