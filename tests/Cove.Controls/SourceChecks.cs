using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
namespace Cove.Launcher;

internal static class SourceChecks {
 static int checks;
 static void Check(bool value,string reason){checks++;if(!value)throw new Exception(reason);}
 static string Row(int port,bool connected=true,string name="Device",string extra="")=>$"{{\"sourceType\":{port+12},\"connectionState\":{connected.ToString().ToLowerInvariant()},\"detectedName\":\"{name}\"{extra}}}";
 static string Rows(params string[] rows)=>"["+string.Join(",",rows)+"]";
 static void Until(Func<bool> condition){if(!SpinWait.SpinUntil(condition,3000))throw new Exception("Source monitor did not settle");}
 sealed class Device:IDevice {
  internal string Json=Rows(Row(1),Row(4));internal Action? Changed;internal int Subscriptions,Unsubscriptions,Reads,Writes,Connections;
  internal Action? Reading;internal bool WatchUnavailable;internal readonly ManualResetEventSlim Entered=new(false),Release=new(true);
  public IDisposable WatchSources(Action changed){if(WatchUnavailable)throw new EntryPointNotFoundException();Changed=changed;Subscriptions++;return new Subscription(()=>{Changed=null;Unsubscriptions++;});}
  sealed class Subscription:IDisposable {readonly Action stop;internal Subscription(Action stop){this.stop=stop;}public void Dispose()=>stop();}
  public string ReadSources(){Interlocked.Increment(ref Reads);Entered.Set();if(!Release.Wait(3000))throw new TimeoutException();Reading?.Invoke();return Json;}
  public string ReadAudioReturnChannel()=>"eARC";
  public DeviceSnapshot ReadPicture()=>throw new Exception("Inventory must not read picture settings");
  public int ConnectHdmi(int source){Connections++;return 1;}
  public bool SetBrightness(int value){Writes++;return true;}public bool SetPictureScope(PictureScope scope){Writes++;return true;}public bool HasBrightnessRange()=>true;
 }
 internal static int Run(){
  var inventory=new SourceInventory();
  for(int mask=0;mask<16;mask++){
   var rows=Enumerable.Range(1,4).Where(p=>(mask&(1<<(p-1)))!=0).Select(p=>Row(p)).ToArray();
   var actual=inventory.Update(Rows(rows));Check(inventory.Verified,"A partial or empty inventory is valid");
   Check(actual.Select(p=>p.Port).SequenceEqual(Enumerable.Range(1,4).Where(p=>(mask&(1<<(p-1)))!=0)),"Omitted ports are removed");
   Check(actual.All(p=>p.CanSelect),"Remaining connected inputs stay selectable");
  }
  inventory.Update(Rows(Row(4,true,"Old console")));inventory.Update("[]");
  Check(inventory.Update(Rows(Row(4,true,""))).Single().Label=="HDMI 4","An omitted unplug ends name retention");
  inventory.Update(Rows(Row(4,true,"Old console")));inventory.Update(Rows(Row(4,false)));
  Check(inventory.Update(Rows(Row(4,true,""))).Single().Label=="HDMI 4","An explicit unplug ends name retention");
  inventory.Update(Rows(Row(4,true,"Console")));
  Check(inventory.Update(Rows(Row(4,true,""))).Single().Label=="Console","A connected device may report its name late");
  foreach(int power in new[]{-1,0,1,2,3})Check(inventory.Update(Rows(Row(2,true,"Console",",\"powerState\":"+power))).Single().CanSelect,"Standby does not mean unplugged");
  string speaker=Row(3,true,"Soundbar",",\"iconPath\":\"/usr/apps/com.samsung.tv.theme-resource/shared/res/VD_ICONS/i_icon_device_m_speaker.svg\"");
  Check(inventory.Update(Rows(Row(1),speaker)).Count==1&&inventory.Audio.Single().Port==3,"Audio endpoint is not a video card");
  Check(!inventory.Audio.Single().CanSelect,"Audio endpoint never selects an HDMI picture");
  inventory.Update(Rows(Row(1)));Check(inventory.Audio.Length==0,"Unplug removes audio endpoint too");
  foreach(string bad in new[]{"broken","null","{}","[",new string('x',16385)}){
   inventory.Update(Rows(Row(1),Row(4)));var old=inventory.Update(bad);
   Check(!inventory.Verified&&old.Count==2&&old.All(p=>!p.CanSelect),"Malformed report retains only unverified hints");
   var recovered=inventory.Update(Rows(Row(1)));Check(inventory.Verified&&recovered.Count==1&&recovered[0].CanSelect,"A fresh report recovers without restarting");
  }
  inventory.Update(Rows(Row(1),Row(4)));
  var partial=inventory.Update(Rows(Row(1),"{\"sourceType\":16,\"connectionState\":\"bad\"}"));
  Check(!inventory.Verified&&partial.Single(p=>p.Port==1).CanSelect&&!partial.Single(p=>p.Port==4).CanSelect,"Malformed port must not disable another input");
  partial=inventory.Update(Rows(Row(1),Row(4),Row(4,false)));
  Check(!inventory.Verified&&partial.Single(p=>p.Port==1).CanSelect&&!partial.Single(p=>p.Port==4).CanSelect,"Duplicate port is isolated");
  partial=inventory.Update(Rows(Row(1),"{\"sourceType\":0,\"connectionState\":\"unrelated\"}"));
  Check(inventory.Verified&&partial.Count==1&&partial[0].CanSelect,"Unrelated source types cannot invalidate HDMI");
  var device=new Device();var controls=new ControlAdapter(device);
  using(var monitor=new SourceMonitor(device,controls.RefreshInventory)){
   Until(()=>monitor.Latest!=null&&!monitor.Busy);Check(device.Subscriptions==1,"One native subscription");
   var stale=monitor.Latest;device.Json=Rows(Row(1));device.Changed!();
   Until(()=>!ReferenceEquals(stale,monitor.Latest)&&!monitor.Busy);
   Check(monitor.Latest!.Video.Length==1,"Hidden monitor receives unplug without foreground polling");
   stale=monitor.Latest;device.Json=Rows(Row(1),speaker,Row(4));device.Changed!();
   Until(()=>!ReferenceEquals(stale,monitor.Latest)&&!monitor.Busy);
   Check(monitor.Latest!.Video.Length==2&&monitor.Latest.Audio.Single().Port==3&&monitor.Latest.AudioReturnChannel=="eARC","Video and audio use the same coherent report");
   device.Entered.Reset();device.Release.Reset();monitor.Request();Until(()=>device.Entered.IsSet);
   int reads=device.Reads;for(int n=0;n<1000;n++)device.Changed!();device.Json="[]";device.Release.Set();
   Until(()=>!monitor.Busy);Check(device.Reads<=reads+1,"A burst coalesces to at most one pending read");
   Check(monitor.Latest!.Video.Length==0&&monitor.Latest.Audio.Length==0,"Latest unplug wins a notification burst");
   Check(device.Writes==0&&device.Connections==0,"Inventory never changes source or picture settings");
  }
  Check(device.Unsubscriptions==1&&device.Changed==null,"Monitor unregisters on exit");
  device=new Device();controls=new ControlAdapter(device);device.Release.Reset();
  var closing=new SourceMonitor(device,controls.RefreshInventory);Until(()=>device.Entered.IsSet);var late=device.Changed!;
  closing.Dispose();device.Release.Set();Until(()=>!closing.Busy);int stoppedReads=device.Reads;late();closing.Request();Thread.Sleep(30);
  Check(closing.Latest==null&&device.Reads==stoppedReads&&device.Unsubscriptions==1,"A late native event or in-flight read cannot revive a disposed monitor");
  device=new Device{WatchUnavailable=true};controls=new ControlAdapter(device);
  using(var fallback=new SourceMonitor(device,controls.RefreshInventory)){
   Until(()=>fallback.Latest!=null&&!fallback.Busy);var initial=fallback.Latest;device.Json="[]";fallback.Request();Until(()=>!ReferenceEquals(initial,fallback.Latest)&&!fallback.Busy);
   Check(fallback.Latest!.Video.Length==0,"Explicit foreground refresh works when native notification registration is unavailable");
   int reads=device.Reads;Thread.Sleep(30);Check(device.Reads==reads,"The monitor has no continuous hidden poll");
  }
  device=new Device();controls=new ControlAdapter(device);int attempts=0;
  device.Reading=()=>{if(++attempts==2)device.Json=Rows(Row(1));};
  var result=controls.Execute(new(1,"hdmi",4,null));
  Check(!result.SourceRequestAccepted&&device.Connections==0,"Unplug during validation cannot connect a stale card");
  device=new Device{Json=Rows(Row(1),speaker)};controls=new ControlAdapter(device);
  Check(!controls.Execute(new(1,"hdmi",3,null)).SourceRequestAccepted&&device.Connections==0,"Audio is inaccessible through the video command");
  return checks;
 }
}
