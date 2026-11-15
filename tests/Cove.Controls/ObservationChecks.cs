using System;using System.Collections.Generic;using System.Threading;using System.Threading.Tasks;
namespace Cove.Launcher;
internal static class ObservationChecks {
 internal static int Run(){
  int count=0;void Check(bool value,string why){count++;if(!value)throw new Exception(why);}
  DeviceSnapshot State(int brightness=50,int source=13,string mode="655361",PictureScope scope=PictureScope.AllSources,long time=0)=>new(source,mode,brightness,new HashSet<string>(),time,false,scope,true,true);
  var observation=new PictureObservation();var original=State();observation.Accept(original);
  var transient=observation.Observe(State(0,time:100),100,out bool manual);
  Check(transient.SourceTransition&&!manual,"One zero sample is pending, not a confirmed manual edit");
  Check(!observation.Observe(State(time:200),200,out manual).SourceTransition&&!manual,"Transient zero recovers without losing selection");
  observation.Observe(State(0,time:300),300,out manual);
  Check(observation.Observe(State(0,time:500),500,out manual).SourceTransition&&!manual,"Short mismatch remains pending");
  Check(!observation.Observe(State(0,time:900),900,out manual).SourceTransition&&manual,"Sustained legitimate zero is accepted as manual edit");
  observation.Observe(State(17,14,time:1000),1000,out manual);
  Check(!observation.Observe(State(17,14,time:1600),1600,out manual).SourceTransition&&!manual,"Different source is not a manual change to previous source");
  observation.Observe(State(9,14,time:1700),1700,out manual);
  observation.Observe(State(9,14,time:1800) with{SourceTransition=true},1800,out manual);
  Check(observation.Observe(State(9,14,time:2300),2300,out manual).SourceTransition,"Unstable sample resets the confirmation window");
  Check(observation.Observe(State(9,14,time:2300),2600,out manual).SourceTransition,"Stale samples cannot confirm changes");
  // Exercise actual sampler order, including same-source mode/scope/value drift.
  foreach(string changed in new[]{"none","picturemode","brightness","applypicmode","source","slow"}){
   var reads=new Dictionary<string,int>();int sources=0,times=0;
   string Get(string key){reads.TryGetValue(key,out int n);reads[key]=++n;return key switch{"picturemode"=>changed==key&&n==2?"458769":"655361","brightness"=>changed==key&&n==2?"17":"0",_=>changed==key&&n==2?"1":"0"};}
   var read=PictureSampling.Read(()=>++sources==2&&changed=="source"?14:13,Get,()=>true,()=>false,()=>++times==2&&changed=="slow"?251:0);
   Check(read.SourceTransition==(changed!="none"),"Bracketed sample detects "+changed);
   Check(!read.ScopeAvailable&&read.BrightnessAvailable,"Capabilities are independent");
   Check(reads["picturemode"]==2&&reads["brightness"]==2&&reads["applypicmode"]==2,"Both ends of the native context are checked");
  }
  var zero=PictureSampling.Read(()=>13,k=>k=="picturemode"?"655361":"0",()=>true,()=>true,()=>0);
  Check(BrightnessPolicy.Eligible(zero)&&zero.Brightness==0,"A coherent zero remains valid");
  bool rejected=false;try{PictureSampling.Read(()=>13,k=>k=="brightness"?"invalid":k=="picturemode"?"655361":"0",()=>true,()=>true,()=>0);}catch(InvalidOperationException){rejected=true;}
  Check(rejected,"Malformed brightness is not coerced to zero");
  return count;
 }
}
