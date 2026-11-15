using System;
using System.Collections.Generic;
using System.Threading;
namespace Cove.Launcher;
internal static class InputBrightnessChecks {
 sealed class Device:IDevice {
  internal long Time;internal int Source=13,Brightness=1,Writes,Connections;internal string Mode="655361";internal bool Available=true,Connected=true,SetterOk=true,SignalReady=true;
  public bool CanFollowBrightness(DeviceSnapshot state)=>SignalReady;
  internal Action? BeforeRead,BeforeRange;internal int DelayedReadback;int oldBrightness;
  public DeviceSnapshot ReadPicture(){BeforeRead?.Invoke();int value=Writes>0&&DelayedReadback-->0?oldBrightness:Brightness;return new(Source,Mode,value,new HashSet<string>(),Time,false,PictureScope.CurrentSource,Available,false);}
  public (int Source,bool SourceTransition) ReadSourceContext()=>(Source,false);
  public string ReadSources()=>"[{\"sourceType\":13,\"connectionState\":true},{\"sourceType\":14,\"connectionState\":"+(Connected?"true":"false")+"},{\"sourceType\":15,\"connectionState\":false},{\"sourceType\":16,\"connectionState\":false}]";
  public bool SetBrightness(int value){oldBrightness=Brightness;Writes++;if(SetterOk)Brightness=value;return SetterOk;}
  public bool HasBrightnessRange(){BeforeRange?.Invoke();return true;}
  public bool SetPictureScope(PictureScope scope)=>throw new Exception("Scope must not be changed by follow");
  public int ConnectHdmi(int source){Connections++;Source=source;Mode="458769";Brightness=50;return 1;}
 }
 internal static int Run(){
  int count=0;void Check(bool ok){count++;if(!ok)throw new Exception("input_follow_"+count);}
  (Device,BrightnessProfiles,ControlAdapter) Setup(){var d=new Device();var p=new BrightnessProfiles();p.Remember(d.ReadPicture(),Appearance.Night,true);var a=new ControlAdapter(d,()=>d.Time,true,p);a.ReadPicture();return(d,p,a);}
  var(d,p,a)=Setup();var result=a.Execute(new(1,"hdmi",2,null));Check(result.SourceRequestAccepted&&result.InputBrightness==new InputBrightnessPlan(14,Appearance.Night,1));Check(d.Writes==0);
  var followed=a.FollowInputBrightness(result.InputBrightness!,default,ms=>d.Time+=ms);Check(followed.Verified&&d.Writes==1&&d.Brightness==1&&d.Mode=="458769"&&d.Connections==1);Check(d.Time<=InputBrightnessSettling.Budget);
  // A connected but signal-less input can report a stable provisional picture
  // context. It must never receive an automatic brightness write.
  (d,p,a)=Setup();result=a.Execute(new(1,"hdmi",2,null));d.Mode="65538";d.Brightness=7;d.SignalReady=false;
  followed=a.FollowInputBrightness(result.InputBrightness!,default,ms=>d.Time+=ms);
  Check(!followed.Verified&&d.Writes==0&&d.Brightness==7);
  // Signal loss restarts the stability interval; late readiness cannot cause
  // an immediate write using the earlier provisional context.
  (d,p,a)=Setup();result=a.Execute(new(1,"hdmi",2,null));d.SignalReady=false;
  followed=a.FollowInputBrightness(result.InputBrightness!,default,ms=>{d.Time+=ms;if(d.Time>=3900)d.SignalReady=true;});
  Check(followed.Verified&&d.Writes==1&&d.Time>=4900);
  // Loss at the final write boundary refuses the setter, even after settling.
  (d,p,a)=Setup();result=a.Execute(new(1,"hdmi",2,null));
  d.BeforeRange=()=>d.SignalReady=false;
  followed=a.FollowInputBrightness(result.InputBrightness!,default,ms=>d.Time+=ms);
  Check(!followed.Verified&&d.Writes==0);
  // Pure exact-firmware signal/source/mode sampling rejects each mismatch.
  var snapshot=new Device().ReadPicture();long clock=0;int calls=0;
  (int,int) ep=(0,2),sig=(0,0),mode=(0,655361);
  bool Sample()=>InputSignalSampling.Read(snapshot,()=>13,()=>ep,()=>sig,()=>mode,()=>clock);
  Check(Sample());foreach(int unavailable in new[]{1,2,3,4,-1}){sig=(0,unavailable);Check(!Sample());}sig=(0,0);
  ep=(0,3);Check(!Sample());ep=(-1,2);Check(!Sample());ep=(0,2);mode=(0,65538);Check(!Sample());mode=(-1,655361);Check(!Sample());mode=(0,655361);
  Check(!InputSignalSampling.Read(snapshot,()=>13,()=>ep,()=>++calls==1?(0,0):(0,1),()=>mode,()=>clock));
  calls=0;Check(!InputSignalSampling.Read(snapshot,()=>13,()=>ep,()=>sig,()=>mode,()=>++calls==1?0:251));
  calls=0;Check(!InputSignalSampling.Read(snapshot,()=>++calls==1?13:14,()=>ep,()=>sig,()=>mode,()=>clock));
  // A later native Game/HDR preset may appear after the first settled context.
  (d,p,a)=Setup();result=a.Execute(new(1,"hdmi",2,null));bool changed=false;
  followed=a.FollowInputBrightness(result.InputBrightness!,default,ms=>{d.Time+=ms;if(!changed&&d.Time>=1200){changed=true;d.Mode="393225";d.Brightness=50;}});
  Check(followed.Verified&&d.Writes==1&&d.Brightness==1&&d.Mode=="393225");
  // Replay the measured PS5 handoff: intermediate native modes precede Game.
  (d,p,a)=Setup();result=a.Execute(new(1,"hdmi",2,null));d.Mode="655360";
  d.BeforeRead=()=>{if(d.Time<300)d.Mode="655360";else if(d.Time<2100)d.Mode="65538";else d.Mode="458769";};
  bool gameReached=false;
  followed=a.FollowInputBrightness(result.InputBrightness!,default,ms=>{d.Time+=ms;if(!gameReached&&d.Time>=2100){gameReached=true;d.Brightness=50;}});
  Check(followed.Verified&&d.Brightness==1&&d.Mode=="458769"&&d.Writes==1&&d.Time<=InputBrightnessSettling.Budget);
  // One transient sample cannot erase explicit intent. A sustained manual
  // change releases following while retaining the two customizable levels.
  (d,p,a)=Setup();d.Brightness=0;var transient=a.ReadPicture();Check(transient.SourceTransition&&p.HasChoice);d.Brightness=1;Check(a.ReadPicture().ProfileSelected==Appearance.Night&&p.HasChoice);
  (d,p,a)=Setup();d.Brightness=17;var manual=a.ReadPicture();Check(manual.SourceTransition&&p.HasChoice);d.Time+=600;manual=a.ReadPicture();Check(manual.ProfileSelected==null&&!p.HasChoice&&p.Target(manual,Appearance.Night)==1);
  p=new();Check(p.Describe(new Device().ReadPicture() with{Brightness=50}).ProfileSelected==null);
  (d,p,a)=Setup();d.Brightness=50;a.ReadPicture();d.Time+=600;Check(a.ReadPicture().ProfileSelected==null&&!p.HasChoice);
  (d,p,a)=Setup();d.Brightness=17;result=a.Execute(new(1,"hdmi",2,null));Check(result.SourceRequestAccepted&&result.InputBrightness==null&&d.Writes==0);
  (d,p,a)=Setup();d.Brightness=17;a.ReadPicture();d.BeforeRead=()=>throw new InvalidOperationException();try{a.ReadPicture();}catch(InvalidOperationException){}d.BeforeRead=null;d.Time+=600;Check(a.ReadPicture().SourceTransition&&p.HasChoice);d.Time+=600;Check(!a.ReadPicture().SourceTransition&&!p.HasChoice);
  // Explicit manual slider adjustment disarms the remembered profile.
  (d,p,a)=Setup();var original=d.ReadPicture() with{ProfileSelected=null};result=a.Execute(new(1,"brightness",null,null,new(original,2)));Check(result.Verified&&!p.HasChoice&&p.Target(d.ReadPicture(),Appearance.Night)==1);
  // Current input card only returns to the viewer: no follow request or write.
  (d,p,a)=Setup();result=a.Execute(new(1,"hdmi",1,null));Check(result.SourceRequestAccepted&&result.InputBrightness==null&&d.Writes==0);
  // No choice, stale choice or unavailable source cannot produce auto writes.
  d=new();a=new(d,()=>d.Time,true,new());result=a.Execute(new(1,"hdmi",2,null));Check(result.InputBrightness==null&&d.Writes==0);
  (d,p,a)=Setup();result=a.Execute(new(1,"hdmi",2,null));p.Remember(d.ReadPicture(),Appearance.Day,false);followed=a.FollowInputBrightness(result.InputBrightness!,default,ms=>d.Time+=ms);Check(!followed.Verified&&d.Writes==0);
  (d,p,a)=Setup();result=a.Execute(new(1,"hdmi",2,null));d.Available=false;followed=a.FollowInputBrightness(result.InputBrightness!,default,ms=>d.Time+=ms);Check(!followed.Verified&&d.Writes==0&&d.Time<=InputBrightnessSettling.Budget);
  (d,p,a)=Setup();result=a.Execute(new(1,"hdmi",2,null));d.Connected=false;followed=a.FollowInputBrightness(result.InputBrightness!,default,ms=>d.Time+=ms);Check(!followed.Verified&&d.Writes==0);
  (d,p,a)=Setup();result=a.Execute(new(1,"hdmi",2,null));d.SetterOk=false;followed=a.FollowInputBrightness(result.InputBrightness!,default,ms=>d.Time+=ms);Check(!followed.Verified&&d.Writes==1);
  // A setter accepted before its getter catches up is verified with reads only.
  (d,p,a)=Setup();d.DelayedReadback=2;var day=d.ReadPicture();result=a.Execute(new(1,"appearance",null,Appearance.Day,new(day,50)));Check(result.Verified&&d.Writes==1&&p.Describe(d.ReadPicture()).ProfileSelected==Appearance.Day);
  (d,p,a)=Setup();d.DelayedReadback=100;day=d.ReadPicture();result=a.Execute(new(1,"appearance",null,Appearance.Day,new(day,50)));Check(!result.Verified&&d.Writes==1);
  // Never chase a destination that keeps changing, or a later manual edit.
  (d,p,a)=Setup();result=a.Execute(new(1,"hdmi",2,null));followed=a.FollowInputBrightness(result.InputBrightness!,default,ms=>{d.Time+=ms;d.Mode=d.Mode=="458769"?"65538":"458769";});Check(!followed.Verified&&d.Writes==0&&d.Time<=InputBrightnessSettling.Budget);
  (d,p,a)=Setup();result=a.Execute(new(1,"hdmi",2,null));followed=a.FollowInputBrightness(result.InputBrightness!,default,ms=>d.Time+=ms);int writes=d.Writes;d.Brightness=17;a.ReadPicture();d.Time+=600;a.ReadPicture();Check(d.Writes==writes&&!p.HasChoice);
  // A foreground observation during settling is allowed but cannot erase intent.
  (d,p,a)=Setup();result=a.Execute(new(1,"hdmi",2,null));int pendingReads=0;followed=a.FollowInputBrightness(result.InputBrightness!,default,ms=>{d.Time+=ms;var observed=a.ReadPicture();if(observed.SourceTransition)pendingReads++;Check(p.HasChoice);});Check(followed.Verified&&pendingReads>2);
  // Destination changed by CEC/owner: never write to another input or switch back.
  (d,p,a)=Setup();result=a.Execute(new(1,"hdmi",2,null));followed=a.FollowInputBrightness(result.InputBrightness!,default,ms=>{d.Time+=ms;d.Source=13;});Check(!followed.Verified&&d.Writes==0&&d.Connections==1);
  (d,p,a)=Setup();result=a.Execute(new(1,"hdmi",2,null));using(var c=new CancellationTokenSource()){followed=a.FollowInputBrightness(result.InputBrightness!,c.Token,ms=>{d.Time+=ms;c.Cancel();});Check(!followed.Verified&&d.Writes==0);}
  // Cancel at the final native guard, not only between settling samples.
  (d,p,a)=Setup();result=a.Execute(new(1,"hdmi",2,null));using(var c=new CancellationTokenSource()){int reads=0;d.BeforeRead=()=>{if(++reads==9)c.Cancel();};followed=a.FollowInputBrightness(result.InputBrightness!,c.Token,ms=>d.Time+=ms);Check(!followed.Verified&&d.Writes==0);}
  using(var sessions=new InputHandoffSession()){var first=sessions.Begin();var second=sessions.Begin();Check(first.IsCancellationRequested&&!second.IsCancellationRequested);sessions.End(first);sessions.Cancel();Check(second.IsCancellationRequested);sessions.End(second);}
  return count;
 }
}
