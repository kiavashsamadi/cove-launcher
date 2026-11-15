using System;using System.Collections.Generic;using System.Linq;using System.Text.Json;
namespace Cove.Launcher;
internal static class Checks {
 static int count;
 static void Require(bool value){count++;if(!value)throw new Exception("check_failed_"+count);}
 static DeviceSnapshot Snapshot(int source=13,string mode="655360",int brightness=50,long observed=100,bool transition=false)=>new(source,mode,brightness,new HashSet<string>{"655360","65538","655361","393217"},observed,transition);
 sealed class Fake:IDevice {
  internal Queue<DeviceSnapshot> Reads=new();internal List<string> Writes=new();internal List<int> Connections=new();internal bool SetterResult=true;internal int SourceResult=1;
  internal Action? OnReadPicture,OnReadSources;
  public DeviceSnapshot ReadPicture(){OnReadPicture?.Invoke();return Reads.Dequeue();}public string ReadSources(){OnReadSources?.Invoke();return Sources;}
  public bool SelectPreset(string target){Writes.Add(target);return SetterResult;}
  public bool HasBrightnessRange()=>true;
  public bool SetBrightness(int value){Writes.Add("brightness:"+value);return SetterResult;}
  public bool SetPictureScope(PictureScope scope){Writes.Add("scope:"+scope);return SetterResult;}
  public int ConnectHdmi(int source){Connections.Add(source);return SourceResult;}
 }
 const string Sources="[{\"sourceType\":13,\"connectionState\":true,\"detectedName\":\"Apple%20TV\",\"powerState\":0},{\"sourceType\":14,\"connectionState\":true,\"detectedName\":\"PS5\"},{\"sourceType\":15,\"connectionState\":false},{\"sourceType\":16,\"connectionState\":true,\"detectedName\":\"Switch\"}]";
 static void Main(){
  foreach(string message in new[]{"{}","[]","{\"v\":1,\"id\":1,\"action\":\"shell\"}","{\"v\":1,\"id\":1,\"action\":\"hdmi\",\"port\":5}","{\"v\":1,\"id\":1,\"action\":\"hdmi\",\"port\":1,\"command\":\"x\"}","{\"v\":1,\"id\":1,\"action\":\"appearance\",\"value\":\"night\",\"value\":\"day\"}",new string('x',513)}){
   bool rejected=false;try{ControlProtocol.Parse(message);}catch{rejected=true;}Require(rejected);
  }
  Require(ControlProtocol.Parse("{\"v\":1,\"id\":1,\"action\":\"appearance\",\"value\":\"night\"}").Appearance==Appearance.Night);
  var inventory=new SourceInventory();var ports=inventory.Update(Sources);Require(ports.Count==3);Require(ports[0].Label=="Apple TV"&&ports[0].CanSelect);Require(ports.Any(p=>p.Port==4));
  ports=inventory.Update("bad");Require(ports.Count==3&&ports.All(p=>!p.CanSelect));
  ports=inventory.Update(Sources.Replace("\"connectionState\":true,\"detectedName\":\"Switch\"","\"connectionState\":false,\"detectedName\":\"\""));Require(ports.Count==2);
  ports=inventory.Update(Sources.Replace("\"Switch\"","\"\""));Require(ports.Single(p=>p.Port==4).Label=="Switch");
  // A fresh launcher must not invent a product name for a nameless connected
  // device. Connection alone controls visibility, not name or standby power.
  string unnamed=Sources.Replace("\"detectedName\":\"Switch\"","\"editName\":\"\",\"detectedName\":\"\",\"powerState\":2");
  var freshInventory=new SourceInventory();ports=freshInventory.Update(unnamed);
  Require(ports.Count==3&&ports.Single(p=>p.Port==4).Label=="HDMI 4");
  Require(ports.Single(p=>p.Port==4).CanSelect);
  string unplugged=unnamed.Replace("\"sourceType\":16,\"connectionState\":true","\"sourceType\":16,\"connectionState\":false");
  Require(freshInventory.Update(unplugged).All(p=>p.Port!=4));
  Require(freshInventory.Update(unnamed).Single(p=>p.Port==4).Label=="HDMI 4");
  {
   var fake=new Fake();fake.Reads.Enqueue(Snapshot(source:16));var result=new ControlAdapter(fake,()=>100).Execute(new(1,"hdmi",4,null));Require(result.SourceRequestAccepted&&!result.Verified&&fake.Connections.Single()==16&&fake.Writes.Count==0);
  }
  {
   var fake=new Fake();var result=new ControlAdapter(fake,()=>100).Execute(new(1,"hdmi",3,null));Require(!result.Verified&&fake.Connections.Count==0);
  }
  foreach(int code in new[]{0,-1,2}){
   var fake=new Fake{SourceResult=code};fake.Reads.Enqueue(Snapshot(source:13));var result=new ControlAdapter(fake,()=>100).Execute(new(1,"hdmi",1,null));Require(!result.Verified);
  }
  string withAudio=Sources.Replace("\"sourceType\":15,\"connectionState\":false","\"sourceType\":15,\"connectionState\":true,\"iconPath\":\"/usr/apps/com.samsung.tv.theme-resource/shared/res/VD_ICONS/i_icon_device_m_speaker.svg\"");
  var audioInventory=new SourceInventory();Require(audioInventory.Update(withAudio).All(p=>p.Port!=3));
  Require(audioInventory.Update(withAudio.Replace("i_icon_device_m_speaker.svg","i_icon_device_m_gamepad.svg")).Any(p=>p.Port==3&&p.CanSelect));
  // Suspending during native getters cancels unsent changes of every kind.
  foreach(string action in new[]{"hdmi","appearance","brightness","picture_scope"}){
   using var cancel=new System.Threading.CancellationTokenSource();
   var original=Snapshot() with{Scope=PictureScope.CurrentSource};
   var fake=new Fake();fake.Reads.Enqueue(original);fake.Reads.Enqueue(original);
   if(action=="hdmi")fake.OnReadSources=cancel.Cancel;else fake.OnReadPicture=cancel.Cancel;
   var request=action switch{
    "hdmi"=>new Request(1,action,1,null),
    "appearance"=>new Request(1,action,null,Appearance.Night),
    "brightness"=>new Request(1,action,null,null,new BrightnessChange(original,49)),
    _=>new Request(1,action,null,null,null,new PictureScopeChange(original,PictureScope.AllSources))};
   var result=new ControlAdapter(fake,()=>100,adjustableBrightness:true).Execute(request,cancel.Token);
   Require(!result.Verified&&fake.Writes.Count==0&&fake.Connections.Count==0);
   // Cancellation at dispatch must not even consume a getter.
   var unread=fake.Reads.Count;
   result=new ControlAdapter(fake,()=>100,adjustableBrightness:true).Execute(request,cancel.Token);
   Require(!result.Verified&&fake.Reads.Count==unread&&fake.Writes.Count==0&&fake.Connections.Count==0);
  }
  count+=BrightnessChecks.Run();count+=ProfileChecks.Run();count+=InputBrightnessChecks.Run();count+=ObservationChecks.Run();
  // Back uses fresh current-source context, with no highlighted/cached port.
  foreach(int source in new[]{13,14,16}){
   var fake=new Fake();for(int i=0;i<3;i++)fake.Reads.Enqueue(Snapshot(source));
   var result=new ControlAdapter(fake).Execute(new(1,"return_current",null,null));
   Require(result.Verified);Require(fake.Connections.SequenceEqual(new[]{source}));Require(fake.Writes.Count==0);
  }
  foreach(var pair in new[]{(13,14),(14,13),(13,16)}){
   var fake=new Fake();fake.Reads.Enqueue(Snapshot(pair.Item1));fake.Reads.Enqueue(Snapshot(pair.Item2));
   Require(!new ControlAdapter(fake).Execute(new(1,"return_current",null,null)).Verified);
   Require(fake.Connections.Count==0&&fake.Writes.Count==0);
  }
  foreach(int source in new[]{0,12,15,17}){
   var fake=new Fake();fake.Reads.Enqueue(Snapshot(source));
   Require(!new ControlAdapter(fake).Execute(new(1,"return_current",null,null)).Verified);Require(fake.Connections.Count==0);
  }
  {
   var fake=new Fake();fake.Reads.Enqueue(Snapshot(13));fake.Reads.Enqueue(Snapshot(13));fake.Reads.Enqueue(Snapshot(14));
   Require(!new ControlAdapter(fake).Execute(new(1,"return_current",null,null)).Verified);Require(fake.Connections.SequenceEqual(new[]{13}));
   // Never try to restore the earlier source after a changed readback.
   Require(fake.Reads.Count==0&&fake.Writes.Count==0);
  }
  {
   var fake=new Fake();Require(!new ControlAdapter(fake).Execute(new(1,"return_current",2,null)).Verified);Require(fake.Reads.Count==0&&fake.Connections.Count==0);
   bool rejected=false;try{ControlProtocol.Parse("{\"v\":1,\"id\":1,\"action\":\"return_current\"}");}catch{rejected=true;}Require(rejected);
  }
  {
   using var cancellation=new System.Threading.CancellationTokenSource();
   var fake=new Fake{OnReadSources=()=>cancellation.Cancel()};fake.Reads.Enqueue(Snapshot());fake.Reads.Enqueue(Snapshot());
   Require(!new ControlAdapter(fake).Execute(new(1,"return_current",null,null),cancellation.Token).Verified);Require(fake.Connections.Count==0&&fake.Writes.Count==0);
  }
  {
   var fake=new Fake{SourceResult=0};for(int i=0;i<3;i++)fake.Reads.Enqueue(Snapshot());
   Require(!new ControlAdapter(fake).Execute(new(1,"return_current",null,null)).Verified);Require(fake.Connections.Count==1&&fake.Writes.Count==0);
   fake=new Fake();fake.Reads.Enqueue(Snapshot(transition:true));
   Require(!new ControlAdapter(fake).Execute(new(1,"return_current",null,null)).Verified);Require(fake.Connections.Count==0);
  }
  Console.WriteLine(JsonSerializer.Serialize(new{checks=count,passed=true,native_executed=false,tv_contacted=false}));
 }
}
