using System;
using System.Collections.Generic;
namespace Cove.Launcher;
internal static class BrightnessChecks {
 internal static int Run(){
  int count=0;void Check(bool value){count++;if(!value)throw new Exception("brightness_check_"+count);}
  DeviceSnapshot State(int value=35,string mode="655360",int source=13,long time=100,bool transition=false,PictureScope scope=PictureScope.CurrentSource)=>new(source,mode,value,new HashSet<string>{"655360","65538","655361","393217"},time,transition,scope,true,true);
  Check(BrightnessPolicy.ReadScope("0")==PictureScope.AllSources);Check(BrightnessPolicy.ReadScope("1")==PictureScope.CurrentSource);
  foreach(string? value in new string?[]{null,"","01","true","-1","2"," 0"})Check(BrightnessPolicy.ReadScope(value)==PictureScope.Unknown);
  var editor=new BrightnessEditor();Check(!editor.Open(null));Check(!editor.Open(State(source:0)));Check(!editor.Open(State(scope:PictureScope.Unknown)));
  Check(editor.Open(State()));for(int i=0;i<100;i++)editor.Move(1);Check(editor.Value==50);for(int i=0;i<100;i++)editor.Move(-1);Check(editor.Value==0);editor.Move(2);Check(editor.Value==0);
  editor.Cancel();Check(!editor.IsOpen&&editor.Begin(100)==null);
  editor.Open(State());Check(editor.Begin(100)==null);editor.Close();Check(!editor.IsOpen);
  foreach(var state in new DeviceSnapshot?[]{null,State(scope:PictureScope.Unknown),State(scope:PictureScope.AllSources),State(source:16),State(mode:"655361"),State(value:36),State(transition:true)}){editor.Open(State());Check(!editor.Observe(state)&&!editor.IsOpen&&editor.Begin(100)==null);}
  editor.Open(State());Check(editor.Observe(State(time:200))&&editor.IsOpen);editor.Cancel();
  foreach(var scope in new[]{PictureScope.CurrentSource,PictureScope.AllSources}){
   Check(editor.Open(State(scope:scope)));editor.Move(-1);var sent=editor.Begin(100);Check(sent?.Value==34&&sent.Original.Brightness==35);
   for(int i=0;i<10000;i++)editor.Move(-1);Check(editor.Value==0&&editor.Begin(1000)==null); // One latest target, no repeat queue.
   Check(editor.Complete(new(true,"ok",State(34,scope:scope))));Check(editor.Begin(219)==null);
   sent=editor.Begin(220);Check(sent?.Value==0&&sent.Original.Brightness==34);
   editor.Move(1);editor.Move(1);editor.Close();editor.Move(1);Check(editor.Closing&&editor.Value==2&&editor.IsOpen);
   Check(editor.Complete(new(true,"ok",State(0,scope:scope))));Check(editor.IsOpen&&editor.Closing);
   sent=editor.Begin(340);Check(sent?.Value==2&&sent.Original.Brightness==0);
   Check(editor.Complete(new(true,"ok",State(2,scope:scope)))&&!editor.IsOpen);Check(editor.Begin(10000)==null);
  }
  editor.Open(State());editor.Move(-1);var cancelled=editor.Begin(100)!;editor.Cancel();Check(cancelled.Cancellation.IsCancellationRequested&&editor.Begin(1000)==null);
  editor.Open(State());editor.Move(-1);var unsent=editor.Begin(100)!;editor.ReleaseUnsent(unsent);Check(!editor.InFlight&&editor.Value==34);Check(editor.Begin(220)?.Value==34);Check(!editor.Complete(new(false,"readback_failed",State(34)))&&!editor.IsOpen&&editor.Begin(1000)==null);
  editor.Open(State());editor.Move(-1);editor.Begin(100);Check(!editor.Complete(new(true,"ok",State(34,scope:PictureScope.AllSources)))&&!editor.IsOpen);
  editor.Open(State());editor.Move(-1);editor.Begin(100);Check(editor.Observe(State(34)));Check(!editor.Observe(State(33))&&!editor.IsOpen);
  editor.Open(State());editor.Move(-1);var timed=editor.Begin(100)!;editor.Move(-1);Check(!editor.Expire(3099));Check(editor.Expire(3100)&&timed.Cancellation.IsCancellationRequested&&!editor.IsOpen&&editor.Begin(5000)==null);Check(!editor.Complete(new(true,"late",State(34))));
  editor.Open(State());editor.Move(-1);Check(editor.BeginScope(PictureScope.AllSources,100)==null);var step=editor.Begin(100)!;Check(editor.BeginScope(PictureScope.AllSources,100)==null);Check(editor.Complete(new(true,"ok",State(34))));
  var switchScope=editor.BeginScope(PictureScope.AllSources,200);Check(switchScope!=null&&editor.ChangingScope&&editor.Begin(200)==null);editor.Move(1);Check(editor.Value==34);Check(editor.CompleteScope(new(true,"ok",State(33,scope:PictureScope.AllSources)))&&editor.Value==33);editor.Move(1);Check(editor.Begin(400)?.Original.Scope==PictureScope.AllSources);editor.Cancel();
  editor.Open(State());switchScope=editor.BeginScope(PictureScope.AllSources,100)!;editor.Close();Check(editor.CompleteScope(new(true,"ok",State(scope:PictureScope.AllSources)))&&!editor.IsOpen);Check(switchScope.Cancellation.IsCancellationRequested);
  editor.Open(State());editor.BeginScope(PictureScope.AllSources,100);Check(!editor.CompleteScope(new(true,"ok",State()))&&!editor.IsOpen);
  editor.Open(State());switchScope=editor.BeginScope(PictureScope.AllSources,100)!;Check(editor.Expire(3100)&&switchScope.Cancellation.IsCancellationRequested);Check(!editor.CompleteScope(new(true,"late",State(scope:PictureScope.AllSources))));
  foreach(int value in new[]{-1,51,int.MaxValue,int.MinValue}){var f=new Fake();var result=new ControlAdapter(f,()=>100,true).Execute(new(1,"brightness",null,null,new(State(),value)));Check(!result.Verified&&f.Writes.Count==0);}
  foreach(var bad in new[]{State(source:14),State(source:16),State(source:0),State(mode:"327705"),State(time:-151),State(time:101),State(transition:true),State(value:36),State(value:51)}){
   var f=new Fake();f.Reads.Enqueue(bad);var result=new ControlAdapter(f,()=>100,true).Execute(new(1,"brightness",null,null,new(State(),20)));Check(!result.Verified&&f.Writes.Count==0);
  }
  foreach(var bad in new[]{State(scope:PictureScope.Unknown),State(scope:PictureScope.AllSources),State(source:14),State(mode:"655361"),State(value:34),State(time:-151),State(transition:true)}){
   var f=new Fake();f.Reads.Enqueue(State());f.Reads.Enqueue(bad);var result=new ControlAdapter(f,()=>100,true).Execute(new(1,"brightness",null,null,new(State(),20)));Check(!result.Verified&&f.Writes.Count==0);
  }
  foreach(var scope in new[]{PictureScope.CurrentSource,PictureScope.AllSources})foreach(string mode in new[]{"655360","65538","655361","393217"})foreach(int value in new[]{0,1,25,49,50}){
   var f=new Fake();var original=State(mode:mode,scope:scope);f.Reads.Enqueue(original);f.Reads.Enqueue(original);f.Reads.Enqueue(State(value,mode,scope:scope));var adapter=new ControlAdapter(f,()=>100,true);var request=new Request(1,"brightness",null,null,new(original,value));Check(adapter.Execute(request).Verified&&f.Writes.Count==1&&f.Writes[0]==value);Check(!adapter.Execute(request).Verified&&f.Writes.Count==1);
  }
  foreach(var after in new[]{State(value:20,scope:PictureScope.AllSources),State(value:20,scope:PictureScope.Unknown),State(source:16,value:20),State(mode:"655361",value:20),State(value:21),State(value:20,transition:true),State(value:20,time:-151)}){
   var f=new Fake();f.Reads.Enqueue(State());f.Reads.Enqueue(State());f.Reads.Enqueue(after);var result=new ControlAdapter(f,()=>100,true).Execute(new(1,"brightness",null,null,new(State(),20)));Check(!result.Verified&&f.Writes.Count==1); // Never restore into changed context.
  }
  {var f=new Fake();f.Reads.Enqueue(State());Check(new ControlAdapter(f,()=>100,true).Execute(new(1,"brightness",null,null,new(State(),35))).Verified&&f.Writes.Count==0);}
  {var f=new Fake();Check(!new ControlAdapter(f,()=>100).Execute(new(1,"brightness",null,null,new(State(),20))).Verified&&f.Writes.Count==0);}
  {var f=new Fake{Returned=false};f.Reads.Enqueue(State());f.Reads.Enqueue(State());f.Reads.Enqueue(State(value:20));Check(!new ControlAdapter(f,()=>100,true).Execute(new(1,"brightness",null,null,new(State(),20))).Verified&&f.Writes.Count==1);}
  {var f=new Fake{RangeSupported=false};f.Reads.Enqueue(State());Check(!new ControlAdapter(f,()=>100,true).Execute(new(1,"brightness",null,null,new(State(),20))).Verified&&f.Writes.Count==0);}
  {var f=new Fake();Check(!new ControlAdapter(f,()=>100,true).Execute(new(1,"brightness",null,null,new(State(scope:PictureScope.Unknown),20))).Verified&&f.Writes.Count==0);}
  {using var token=new System.Threading.CancellationTokenSource();token.Cancel();var f=new Fake();Check(!new ControlAdapter(f,()=>100,true).Execute(new(1,"brightness",null,null,new(State(),20,token.Token))).Verified&&f.Writes.Count==0);}
  {using var token=new System.Threading.CancellationTokenSource();var f=new Fake{BeforeSecondRead=token.Cancel};f.Reads.Enqueue(State());f.Reads.Enqueue(State());Check(!new ControlAdapter(f,()=>100,true).Execute(new(1,"brightness",null,null,new(State(),20,token.Token))).Verified&&f.Writes.Count==0);}
  foreach(var target in new[]{PictureScope.CurrentSource,PictureScope.AllSources}){
   var start=State(scope:target==PictureScope.AllSources?PictureScope.CurrentSource:PictureScope.AllSources);var f=new Fake();f.Reads.Enqueue(start);f.Reads.Enqueue(start);f.Reads.Enqueue(State(34,scope:target));var adapter=new ControlAdapter(f,()=>100,true);var request=new Request(1,"picture_scope",null,null,null,new(start,target));Check(adapter.Execute(request).Verified&&f.Scopes.Count==1&&f.Writes.Count==0);Check(!adapter.Execute(request).Verified&&f.Scopes.Count==1);
  }
  foreach(var bad in new[]{State(scope:PictureScope.Unknown),State(source:14),State(mode:"327705"),State(value:36),State(time:-151),State(transition:true)}){
   var f=new Fake();f.Reads.Enqueue(State());f.Reads.Enqueue(bad);Check(!new ControlAdapter(f,()=>100,true).Execute(new(1,"picture_scope",null,null,null,new(State(),PictureScope.AllSources))).Verified&&f.Scopes.Count==0&&f.Writes.Count==0);
  }
  foreach(var after in new[]{State(),State(scope:PictureScope.Unknown),State(source:14,scope:PictureScope.AllSources),State(mode:"393217",scope:PictureScope.AllSources)}){
   var f=new Fake();f.Reads.Enqueue(State());f.Reads.Enqueue(State());f.Reads.Enqueue(after);Check(!new ControlAdapter(f,()=>100,true).Execute(new(1,"picture_scope",null,null,null,new(State(),PictureScope.AllSources))).Verified&&f.Scopes.Count==1&&f.Writes.Count==0);
  }
  {using var token=new System.Threading.CancellationTokenSource();var f=new Fake{BeforeSecondRead=token.Cancel};f.Reads.Enqueue(State());f.Reads.Enqueue(State());Check(!new ControlAdapter(f,()=>100,true).Execute(new(1,"picture_scope",null,null,null,new(State(),PictureScope.AllSources,token.Token))).Verified&&f.Scopes.Count==0);}
  {var f=new Fake();Check(!new ControlAdapter(f,()=>100,true).Execute(new(1,"picture_scope",null,null,null,new(State(),PictureScope.Unknown))).Verified&&f.Scopes.Count==0);}
  {var f=new Fake();f.Reads.Enqueue(State());Check(new ControlAdapter(f,()=>100,true).Execute(new(1,"picture_scope",null,null,null,new(State(),PictureScope.CurrentSource))).Verified&&f.Scopes.Count==0);}
  bool rejected=false;try{ControlProtocol.Parse("{\"v\":1,\"id\":1,\"action\":\"brightness\",\"value\":20}");}catch{rejected=true;}Check(rejected); // No remote or arbitrary-setting protocol added.
  rejected=false;try{ControlProtocol.Parse("{\"v\":1,\"id\":1,\"action\":\"picture_scope\",\"value\":0}");}catch{rejected=true;}Check(rejected);
  return count;
 }
 sealed class Fake:IDevice {
  internal readonly Queue<DeviceSnapshot> Reads=new();internal readonly List<int> Writes=new();internal int Presets;internal bool Returned=true,RangeSupported=true;
  internal readonly List<PictureScope> Scopes=new();
  internal Action? BeforeSecondRead;int reads;
  public DeviceSnapshot ReadPicture(){if(++reads==2)BeforeSecondRead?.Invoke();return Reads.Dequeue();}public string ReadSources()=>throw new Exception("unexpected inventory read");
  public bool HasBrightnessRange()=>RangeSupported;
  public bool SetBrightness(int value){Writes.Add(value);return Returned;}
  public bool SetPictureScope(PictureScope scope){Scopes.Add(scope);return Returned;}
  public bool SelectPreset(string value){Presets++;return true;}public int ConnectHdmi(int value)=>throw new Exception("unexpected source write");
 }
}
