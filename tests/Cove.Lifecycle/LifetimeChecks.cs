using System;
using Tizen.NUI;
using Tizen.Applications;

internal sealed partial class NeutralWindow {
 internal void ProbeExit(){Window.Default.SendKey("XF86Exit",Key.StateType.Down);Window.Default.SendKey("XF86Exit",Key.StateType.Up);Tizen.NUI.Timer.Pump();}
 internal void ProbeLowMemory()=>OnLowMemory(new LowMemoryEventArgs());
}
internal static partial class LifecycleChecks {
 static void RunLifetimeChecks(){
  foreach(bool panel in new[]{false,true}){
   var device=new FakeDevice();using(var app=Create(device)){
    if(panel)app.ProbeBrightnessOpen();app.ProbeExit();Until(()=>app.Exited&&app.ProbeIdle);
    Check(!Window.Default.Visible&&device.ConnectCalls==0&&AppControl.Launches.Count==1&&AppControl.Launches[0]=="org.tizen.tv-viewer","Full Exit hands off once to the native viewer and releases the app, including from the slider");
    Check(device.PictureWrites==0,"Exit without edits does not change brightness or scope");
   }
   Check(device.Unsubscribed==1,"Full Exit unregisters source observation during termination");
  }
  foreach(bool settings in new[]{false,true}){
   var device=new FakeDevice();using(var app=Create(device)){
    app.ProbeLowMemory();Check(!app.Exited,"Memory pressure cannot close a foreground launcher");
    if(settings){app.ProbeSettings();app.ProbePause();}else{app.ProbeBack();Until(()=>!app.ProbeActive&&app.ProbeIdle);}
    int connections=device.ConnectCalls;app.ProbeLowMemory();
    Check(app.Exited!=settings,"Memory pressure releases hidden cache but preserves a Settings handoff");
    Check(device.PictureWrites==0&&device.ConnectCalls==connections,"Memory cleanup never writes settings or changes input");
   }
   Check(device.Unsubscribed==1,"Teardown removes exactly one source subscription");
  }
  foreach(bool sound in new[]{false,true}){
   var device=new FakeDevice();using var app=Create(device);
   if(sound)app.ProbeSound();else app.ProbeSettings();
   Check(AppControl.LastRequest?.ApplicationId=="org.tizen.menu","Both settings entry points use the native menu");
   bool specified=AppControl.LastRequest!.ExtraData.TryGet("menuitem",out var category);
   Check(sound?specified&&category=="sound":!specified,"Sound deep link cannot contaminate the general Settings cog");
   app.ProbePause();int raised=Window.Default.Raises;for(int i=0;i<5;i++)app.ProbeLaunch();
   Check(Window.Default.Raises==raised&&device.PictureWrites==0,"Default launch callbacks while Settings owns the foreground cannot raise Cove");
   app.ProbeResume();Check(Window.Default.Raises==raised,"The subsequent OS resume does not itself raise Cove");
  }
 }
}
