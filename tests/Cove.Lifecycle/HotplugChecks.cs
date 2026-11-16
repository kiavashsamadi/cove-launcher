using System;
using System.Linq;
using Tizen.NUI;
using Tizen.Applications;
internal static partial class LifecycleChecks {
 const string OneInput="[{\"sourceType\":13,\"connectionState\":true,\"detectedName\":\"Apple TV\"}]";
 const string AudioInput="{\"sourceType\":15,\"connectionState\":true,\"detectedName\":\"Soundbar\",\"iconPath\":\"/usr/apps/com.samsung.tv.theme-resource/shared/res/VD_ICONS/i_icon_device_m_speaker.svg\"}";
 const string LastInput="{\"sourceType\":16,\"connectionState\":true,\"detectedName\":\"Console\",\"powerState\":2}";
 static void Changed(FakeDevice device,NeutralWindow app,string json){device.Inventory=json;device.SourcesChanged!();Until(()=>app.ProbeInventoryIdle);app.ProbeTick();}
 static void RunHotplugChecks(){
  var device=new FakeDevice();
  using(var app=Create(device)){
   app.ProbeRight();Changed(device,app,OneInput);
   Check(app.ProbePorts.SequenceEqual(new[]{1})&&app.ProbeSelected==0,"Unplug while focused removes the card and repairs focus");
   Check(!app.ProbeNotice.Contains("Checking"),"Partial inventory cannot leave a checking-inputs dead end");
   Changed(device,app,OneInput.TrimEnd(']')+","+AudioInput+","+LastInput+"]");
   Check(app.ProbePorts.SequenceEqual(new[]{1,4}),"Connected sleeping console is shown, soundbar is separate");
   Check(app.ProbeAudioVisible&&app.ProbeAudioName=="Soundbar"&&app.ProbeAudioConnection=="HDMI 3 · eARC","Audio control names the device and physical return port");
   app.ProbeUp();app.ProbeLeft();Check(app.ProbeSelected==4,"Audio sits immediately left of Brightness in remote order");
   Changed(device,app,OneInput);
   Check(!app.ProbeAudioVisible&&app.ProbeSelected==3,"Unplugged focused audio control moves to Brightness");
   app.ProbeInput(1);Until(()=>!app.ProbeActive&&app.ProbeIdle);
   Check(device.ConnectCalls==1,"Remaining input can be selected after partial inventories");
   int raises=Window.Default.Raises,writes=device.PictureWrites;
   device.Inventory=OneInput.TrimEnd(']')+","+AudioInput+","+LastInput+"]";device.SourcesChanged!();Until(()=>app.ProbeInventoryIdle);
   Check(!Window.Default.Visible&&Window.Default.Raises==raises&&device.PictureWrites==writes,"Hidden hotplug updates never steal focus or alter settings");
   bool atShow=false;Window.Default.BeforeShow=()=>atShow=app.ProbePorts.SequenceEqual(new[]{1,4})&&app.ProbeAudioVisible;
   app.ProbeLaunch("smarthub_key");Check(atShow,"Warm first frame already contains the hidden hotplug result");Until(()=>app.ProbeReady);
   app.ProbeSound();Check(AppControl.LastRequest?.ApplicationId=="org.tizen.menu"&&AppControl.LastRequest.ExtraData.TryGet("menuitem",out var category)&&category=="sound","Audio launches Samsung's Sound category");
   Check(device.ConnectCalls==1&&device.PictureWrites==writes,"Sound control never switches to the audio HDMI port");
  }
  Check(device.Unsubscribed==1,"Native source watcher ends with window lifetime");
  device=new FakeDevice();using(var app=Create(device)){
   Changed(device,app,"bad");Check(app.ProbePorts.Length==2,"Malformed report retains only temporary visual hints");
   device.Inventory=OneInput;app.ProbeInput(1);Until(()=>!app.ProbeActive&&app.ProbeIdle);
   Check(device.ConnectCalls==1,"A stale card may retry against fresh native inventory instead of blocking forever");
  }
  device=new FakeDevice();using(var app=Create(device)){
   Changed(device,app,"[]");Check(app.ProbePorts.Length==0&&app.ProbeSelected==2,"Empty inventory leaves Settings reachable");
   Changed(device,app,"["+AudioInput+"]");Check(app.ProbeAudioVisible&&app.ProbePorts.Length==0,"Audio remains usable with no video inputs");
   Check(device.PictureWrites==0&&device.ConnectCalls==0,"Repeated source reports perform no TV writes");
  }
 }
}
