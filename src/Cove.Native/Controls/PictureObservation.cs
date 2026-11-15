using System;
namespace Cove.Launcher;

// Separate an observed reading from a confirmed picture context. A single
// changed sample is neither a manual adjustment nor a trustworthy UI value.
internal sealed class PictureObservation {
 internal const int StableFor=600;
 DeviceSnapshot? confirmed,candidate;long candidateSince;
 internal void Accept(DeviceSnapshot state){confirmed=state;candidate=null;}
 internal void ResetCandidate(){candidate=null;}
 internal DeviceSnapshot Observe(DeviceSnapshot state,long now,out bool manualChange){
  manualChange=false;
  if(!BrightnessPolicy.Eligible(state)||!BrightnessPolicy.Fresh(state,now)){candidate=null;return state with{SourceTransition=true};}
  if(confirmed==null||BrightnessPolicy.SameContext(confirmed,state)){Accept(state);return state;}
  if(candidate==null||!BrightnessPolicy.SameContext(candidate,state)||now<candidateSince){candidate=state;candidateSince=now;return state with{SourceTransition=true};}
  if(now-candidateSince<StableFor)return state with{SourceTransition=true};
  manualChange=BrightnessPolicy.SameIdentity(confirmed,state)&&confirmed.Brightness!=state.Brightness;
  Accept(state);return state;
 }
}

// Fixed getter order, usable with deterministic host fakes. There is no native
// transaction API here: bracketing rejects observed drift, not unseen ABA races.
internal static class PictureSampling {
 internal static DeviceSnapshot Read(Func<int> source,Func<string,string> get,Func<bool> brightnessAvailable,Func<bool> scopeAvailable,Func<long> now){
  long started=now();int before=source();string mode=get("picturemode"),scope=get("applypicmode"),level=get("brightness");
  bool hdmi=before is >=13 and <=16,canBrightness=hdmi&&brightnessAvailable(),canScope=hdmi&&scopeAvailable();
  string finalLevel=get("brightness"),finalScope=get("applypicmode"),finalMode=get("picturemode");int after=source();
  if(!int.TryParse(finalLevel,System.Globalization.NumberStyles.None,System.Globalization.CultureInfo.InvariantCulture,out int value))throw new InvalidOperationException("brightness_invalid");
  return new(after,finalMode,value,new System.Collections.Generic.HashSet<string>(),started,before!=after||mode!=finalMode||scope!=finalScope||level!=finalLevel||now()-started>250,BrightnessPolicy.ReadScope(finalScope),canBrightness,canScope);
 }
}
