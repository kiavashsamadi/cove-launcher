using System;
using System.Threading;
namespace Cove.Launcher;

internal sealed record InputBrightnessPlan(int Source,Appearance Profile,int Value);

// One short continuation belongs to an explicit HDMI-card selection. OS pause
// must not cancel it. Home observes it; Back, Settings, Exit or a newer control
// cancels it. The worker owns
// disposal so cancelling from the UI cannot dispose a wait handle in use.
internal sealed class InputHandoffSession:IDisposable {
 readonly object gate=new();CancellationTokenSource? current;
 internal bool Active{get{lock(gate)return current!=null&&!current.IsCancellationRequested;}}
 internal CancellationTokenSource Begin(){lock(gate){current?.Cancel();return current=new();}}
 internal void Cancel(){lock(gate)current?.Cancel();}
 internal void End(CancellationTokenSource lease){lock(gate){if(ReferenceEquals(current,lease))current=null;lease.Dispose();}}
 public void Dispose()=>Cancel();
}

// Bounded settling after source activation, never a repeating hidden poll.
internal sealed class InputBrightnessSettling {
 // The recorded PS5 transition changed again at ~2.8 seconds. Do not write
 // into its earlier, apparently stable context. Timing is a guard, not proof
 // of signal readiness: an unsteady destination receives no automatic write.
 internal const int Budget=6500,Interval=150,MinimumAge=3200,StableFor=1000,MaximumSamples=44;
 readonly int source;readonly long started;DeviceSnapshot? last;long stableSince;bool seenDestination;
 internal InputBrightnessSettling(int source,long now){this.source=source;started=now;}
 internal void Invalidate(){last=null;}
 internal bool Expired(long now)=>now<started||now-started>=Budget;
 internal int NextWait(long now)=>Expired(now)?0:(int)Math.Min(Interval,Budget-(now-started));
 internal bool LeftDestination(DeviceSnapshot state)=>seenDestination&&state.Source!=source&&!state.SourceTransition;
 internal bool Ready(DeviceSnapshot state,long now){
  if(state.Source==source)seenDestination=true;
  if(Expired(now)||state.Source!=source||!BrightnessPolicy.Eligible(state)||!BrightnessPolicy.Fresh(state,now)){last=null;return false;}
  if(last==null||!BrightnessPolicy.SameContext(last,state)){last=state;stableSince=now;return false;}
  return now-started>=MinimumAge&&now-stableSince>=StableFor;
 }
}

// The firmware distinguishes source connection from video availability. EP source
// IDs are a separate enum from source-api IDs. Never treat an unknown/paused
// signal, a stale EP source or disagreement with AVOC's active mode as ready.
internal static class InputSignalSampling {
 internal static bool Read(DeviceSnapshot state,Func<int> source,Func<(int Code,int Value)> nativeSource,Func<(int Code,int Value)> signal,Func<(int Code,int Value)> activeMode,Func<long> now){
  int expected=state.Source switch{13=>2,14=>3,15=>11,16=>12,_=>-1};
  if(expected<0||!int.TryParse(state.Mode,System.Globalization.NumberStyles.None,System.Globalization.CultureInfo.InvariantCulture,out int mode))return false;
  long started=now();int before=source();var firstSource=nativeSource();var firstSignal=signal();var firstMode=activeMode();
  var lastMode=activeMode();var lastSignal=signal();var lastSource=nativeSource();int after=source();long finished=now(),elapsed=finished-started;
  return before==state.Source&&after==before&&firstSource==(0,expected)&&lastSource==firstSource&&firstSignal==(0,0)&&lastSignal==firstSignal&&firstMode==(0,mode)&&lastMode==firstMode&&elapsed>=0&&elapsed<=250&&BrightnessPolicy.Fresh(state,finished);
 }
}
