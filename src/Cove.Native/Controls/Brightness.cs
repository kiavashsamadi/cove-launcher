using System;
using System.Threading;
namespace Cove.Launcher;

internal sealed record BrightnessChange(DeviceSnapshot Original,int Value,CancellationToken Cancellation=default);
// UI-thread state machine: one in-flight write plus one replaceable target.
// The existing UI tick pumps it; remote repeats allocate no tasks or timers.
internal sealed class BrightnessEditor {
 internal const int MinimumWriteInterval=120;
 internal const int WriteDeadline=3000;
 internal DeviceSnapshot? Original {get;private set;}
 internal int Value {get;private set;}
 internal bool IsOpen=>Original!=null;
 internal bool Closing {get;private set;}
 internal bool InFlight=>flight!=null||scopeFlight!=null;
 internal bool ChangingScope=>scopeFlight!=null;
 BrightnessChange? flight;PictureScopeChange? scopeFlight;CancellationTokenSource? cancellation;long nextWriteAt,startedAt;
 internal bool Open(DeviceSnapshot? state){
  if(IsOpen||!BrightnessPolicy.Eligible(state))return false;
  Original=state;Value=state!.Brightness;Closing=false;nextWriteAt=0;cancellation=new();return true;
 }
 internal void Move(int direction){if(IsOpen&&!Closing&&!ChangingScope&&direction is -1 or 1)Value=Math.Clamp(Value+direction,0,50);}
 internal BrightnessChange? Begin(long now){
  if(!IsOpen||InFlight||Value==Original!.Brightness||now<nextWriteAt)return null;
  flight=new(Original!,Value,cancellation!.Token);startedAt=now;nextWriteAt=now+MinimumWriteInterval;return flight;
 }
 internal void ReleaseUnsent(BrightnessChange change){if(ReferenceEquals(flight,change))flight=null;}
 internal PictureScopeChange? BeginScope(PictureScope target,long now){
  if(!IsOpen||InFlight||Closing||!BrightnessPolicy.ScopeEligible(Original)||Value!=Original!.Brightness||target==Original.Scope||target is not (PictureScope.CurrentSource or PictureScope.AllSources))return null;
  scopeFlight=new(Original,target,cancellation!.Token);startedAt=now;return scopeFlight;
 }
 internal void ReleaseUnsent(PictureScopeChange change){if(ReferenceEquals(scopeFlight,change))scopeFlight=null;}
 internal bool CompleteScope(ControlResult result){
  if(scopeFlight==null)return false;
  var sent=scopeFlight;scopeFlight=null;
  if(!result.Verified||!BrightnessPolicy.Eligible(result.State)||result.State!.Source!=sent.Original.Source||result.State.Mode!=sent.Original.Mode||result.State.Scope!=sent.Target){Cancel();return false;}
  Original=result.State;Value=Original.Brightness;if(Closing)Cancel();return true;
 }
 internal bool Complete(ControlResult result){
  if(flight==null)return false;
  var sent=flight;flight=null;
  if(!result.Verified||!BrightnessPolicy.SameIdentity(sent.Original,result.State)||result.State!.Brightness!=sent.Value){Cancel();return false;}
  Original=result.State;
  if(Closing&&Value==Original.Brightness)Cancel();
  return true;
 }
 internal bool Observe(DeviceSnapshot? state){
  if(!IsOpen)return false;
  if(!BrightnessPolicy.SameIdentity(Original!,state)||state!.Brightness!=Original!.Brightness&&(flight==null||state.Brightness!=flight.Value)){Cancel();return false;}
  return true;
 }
 internal void Close(){if(!IsOpen)return;Closing=true;if(!InFlight&&Value==Original!.Brightness)Cancel();}
 internal bool Expire(long now){if(!InFlight||now-startedAt<WriteDeadline)return false;Cancel();return true;}
 internal void Cancel(){cancellation?.Cancel();cancellation?.Dispose();cancellation=null;flight=null;scopeFlight=null;Original=null;Closing=false;}
}
internal static class BrightnessPolicy {
 internal static bool InRange(int value)=>value>=0&&value<=50;
 internal static PictureScope ReadScope(string? value)=>value switch{"0"=>PictureScope.AllSources,"1"=>PictureScope.CurrentSource,_=>PictureScope.Unknown};
 internal static string ScopeLabel(PictureScope scope)=>scope switch{PictureScope.AllSources=>"All sources",PictureScope.CurrentSource=>"Current source",_=>"Scope unavailable"};
 internal static bool ModeIdentity(string? mode)=>uint.TryParse(mode,System.Globalization.NumberStyles.None,System.Globalization.CultureInfo.InvariantCulture,out uint id)&&id>0&&id.ToString(System.Globalization.CultureInfo.InvariantCulture)==mode;
 internal static bool Eligible(DeviceSnapshot? state)=>state!=null&&state.Source is >=13 and <=16&&state.BrightnessAvailable&&state.Scope is PictureScope.AllSources or PictureScope.CurrentSource&&!state.SourceTransition&&InRange(state.Brightness)&&ModeIdentity(state.Mode);
 internal static bool ScopeEligible(DeviceSnapshot? state)=>Eligible(state)&&state!.ScopeAvailable;
 internal static bool Fresh(DeviceSnapshot state,long now)=>now-state.ObservedAt>=0&&now-state.ObservedAt<=250;
 internal static bool SameIdentity(DeviceSnapshot original,DeviceSnapshot? state)=>Eligible(original)&&Eligible(state)&&original.Source==state!.Source&&original.Mode==state.Mode&&original.Scope==state.Scope;
 internal static bool SameContext(DeviceSnapshot original,DeviceSnapshot? state)=>SameIdentity(original,state)&&original.Brightness==state!.Brightness;
}
