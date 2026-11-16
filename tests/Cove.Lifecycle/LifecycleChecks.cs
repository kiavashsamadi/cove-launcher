using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Threading;
using Cove.Launcher;
using Tizen.NUI;
using Tizen.Applications;

internal sealed partial class NeutralWindow {
 internal void ProbeCreate()=>OnCreate();internal void ProbePause()=>OnPause();internal void ProbeResume()=>OnResume();
 internal void ProbeLaunch(string? entry=null,string? operation=null){var c=new ReceivedAppControl{Operation=operation};if(entry!=null)c.ExtraData.Add("entry_point",entry);OnAppControlReceived(new(){ReceivedAppControl=c});}
 internal bool ProbeReady=>state.Picture!=null&&!state.PicturePending&&updates.IsEmpty&&Volatile.Read(ref workerBusy)==0;
 // Picture and inventory workers finish independently. Navigation fixtures
 // must also wait for the first input-focus assignment, not only data reads.
 internal bool ProbeInitialReady=>ProbeReady&&ProbeInventoryIdle&&hasState&&inputFocusRequested;
 internal bool ProbeIdle=>Volatile.Read(ref workerBusy)==0;
 internal bool ProbeFollowIdle=>!inputHandoff.Active;
 internal bool ProbeReturning=>returningToViewer;internal bool ProbeActive=>foreground.Active;
 internal string ProbeBrightness=>brightnessButtonLabel?.Text??"";
 internal int ProbeSelected=>selected;
 internal string ProbeHero=>heroName?.Text??"";internal float ProbeCurrentClaim=>heroCurrent?.Opacity??0;
 internal bool ProbeCachedControlsBlocked=>state.Picture==null&&Array.TrueForAll(state.Ports,p=>!p.CanSelect);
 internal void ProbeLeft()=>Window.Default.SendKey("Left",Key.StateType.Down);
 internal void ProbeBack(){Window.Default.SendKey("XF86Back",Key.StateType.Down);Window.Default.SendKey("XF86Back",Key.StateType.Up);Tizen.NUI.Timer.Pump();}
 internal void ProbeRight()=>Window.Default.SendKey("Right",Key.StateType.Down);
 internal int[] ProbePorts=>Array.ConvertAll(state.Ports,p=>p.Port);internal bool ProbeAudioVisible=>AudioVisible;internal string ProbeAudioConnection=>audioConnection?.Text??"";internal string ProbeAudioName=>audioName?.Text??"";internal string ProbeNotice=>notice?.Text??"";internal bool ProbeInventoryIdle=>sourceMonitor?.Busy==false;internal void ProbeSound()=>OpenTvSettings(true);
 internal void ProbeTick()=>Tick();internal void ProbeSettings()=>OpenTvSettings();
 internal void ProbeRefresh()=>QueueRefresh();internal void ProbeBrightnessOpen()=>OpenBrightness();internal bool ProbePanelOpen=>brightnessEditor.IsOpen;
 internal void ProbeProfile(Appearance profile){focusRow=1;selected=profile==Appearance.Day?0:1;Window.Default.SendKey("Return",Key.StateType.Down);Window.Default.SendKey("Return",Key.StateType.Up);}
 internal string ProbeSliderTitle=>brightnessTitle?.Text??"";
 internal bool ProbeSettled=>!actionInFlight&&pending==null&&Volatile.Read(ref workerBusy)==0;
 internal void ProbeInput(int port){focusRow=0;selected=Array.FindIndex(state.Ports,p=>p.Port==port);Window.Default.SendKey("Return",Key.StateType.Down);Window.Default.SendKey("Return",Key.StateType.Up);}
 internal void ProbeUp()=>Window.Default.SendKey("Up",Key.StateType.Down);
 internal void ProbeDown()=>Window.Default.SendKey("Down",Key.StateType.Down);
 internal bool ProbeScopeFocused=>scopeFocused;
 internal string ProbeScopeReadOnly=>scopeReadOnly?.Opacity==1?scopeReadOnly.Text:"";
}
internal sealed class FakeDevice:IDevice {
 public bool CanFollowBrightness(DeviceSnapshot state)=>true;
 internal readonly ManualResetEventSlim ConnectEntered=new(false),ConnectRelease=new(true),InventoryEntered=new(false),InventoryRelease=new(true);
 internal string? Inventory;internal Action? SourcesChanged;internal int Unsubscribed;
 public IDisposable WatchSources(Action changed){SourcesChanged=changed;return new SourceSubscription(()=>{SourcesChanged=null;Unsubscribed++;});}sealed class SourceSubscription:IDisposable{readonly Action done;internal SourceSubscription(Action done){this.done=done;}public void Dispose()=>done();}
 public string ReadAudioReturnChannel()=>"eARC";
 internal int ConnectCalls,Source=13,LastSource,PictureWrites,PictureReads,ConnectCode=1;internal bool ThrowAfterConnect,TransitionAfterConnect,ThrowPicture;
 internal string Mode="655361";internal int Brightness=50;internal bool UpdateSourceOnConnect,ScopeAvailable=true;
 public DeviceSnapshot ReadPicture(){Interlocked.Increment(ref PictureReads);if(ThrowPicture)throw new InvalidOperationException();return new(Source,Mode,Brightness,new HashSet<string>{"655361","393217"},Stopwatch.GetTimestamp()*1000/Stopwatch.Frequency,false,PictureScope.AllSources,true,ScopeAvailable);}
 public (int Source,bool SourceTransition) ReadSourceContext(){if(ThrowAfterConnect&&ConnectCalls>0)throw new InvalidOperationException();return(Source,TransitionAfterConnect&&ConnectCalls>0);}
 public string ReadSources(){InventoryEntered.Set();if(!InventoryRelease.Wait(2000))throw new TimeoutException();return Inventory??"[{\"sourceType\":13,\"connectionState\":true,\"editName\":\"Apple TV\"},{\"sourceType\":14,\"connectionState\":true,\"editName\":\"Console\"},{\"sourceType\":15,\"connectionState\":false},{\"sourceType\":16,\"connectionState\":false}]";}
 public int ConnectHdmi(int source){Interlocked.Increment(ref ConnectCalls);LastSource=source;ConnectEntered.Set();if(!ConnectRelease.Wait(2000))throw new TimeoutException();if(UpdateSourceOnConnect){Source=source;Mode="458769";Brightness=50;}return ConnectCode;}
 public bool SetBrightness(int value){PictureWrites++;Brightness=value;return true;}public bool SetPictureScope(PictureScope scope){PictureWrites++;return false;}public bool HasBrightnessRange()=>true;
}
internal static partial class LifecycleChecks {
 static int checks;
 static void Check(bool ok,string why){checks++;if(!ok)throw new Exception(why);}
 static void Until(Func<bool> predicate,int timeout=3000){var time=Stopwatch.StartNew();while(!predicate()){Tizen.NUI.Timer.Pump();Thread.Sleep(1);if(time.ElapsedMilliseconds>timeout)throw new TimeoutException("UI condition did not settle");}}
 static NeutralWindow Create(FakeDevice device){Window.Reset();var app=new NeutralWindow(device,new BrightnessProfiles());app.ProbeCreate();Until(()=>app.ProbeInitialReady);app.ProbeTick();return app;}
 static void Main(){
  RunHotplugChecks();
  RunLifetimeChecks();
  foreach(bool reopenWithHome in new[]{false,true}){
   var followDevice=new FakeDevice{UpdateSourceOnConnect=true};using var followApp=Create(followDevice);
   followApp.ProbeProfile(Appearance.Night);Until(()=>followApp.ProbeSettled);int writes=followDevice.PictureWrites;
   followDevice.ConnectRelease.Reset();followApp.ProbeInput(2);Until(()=>followDevice.ConnectEntered.IsSet);
   followApp.ProbePause();int raises=Window.Default.Raises;Check(!followApp.ProbeActive&&!Window.Default.Visible,"Card activation pause hides Cove even before source response");
   if(reopenWithHome)followApp.ProbeLaunch("smarthub_key","http://tizen.org/appcontrol/operation/main");
   followDevice.ConnectRelease.Set();Until(()=>followApp.ProbeIdle);
   Check(followDevice.PictureWrites==writes,"Source acknowledgement does not immediately write a provisional context");
   if(reopenWithHome){int beforeReads=followDevice.PictureReads;followApp.ProbeRefresh();Until(()=>followDevice.PictureReads>beforeReads);followApp.ProbeTick();Check(!followApp.ProbeBrightness.Contains("50"),"Reopened pending input cannot claim its provisional brightness");}
   Until(()=>followApp.ProbeFollowIdle,8000);
   if(reopenWithHome){Check(followDevice.PictureWrites==writes+1&&followDevice.Brightness==0,"Home observes rather than cancels the selected profile handoff");Until(()=>followApp.ProbeReady);}
   else{Check(followDevice.Brightness==0&&followDevice.PictureWrites==writes+1,"Chosen Night follows input despite OS pause");Check(!Window.Default.Visible&&Window.Default.Raises==raises,"Hidden follow never raises or redraws Cove");followApp.ProbeResume();Check(!Window.Default.Visible&&!followApp.ProbeActive,"Source return resume cannot reopen Cove");followDevice.InventoryEntered.Reset();followDevice.InventoryRelease.Reset();followApp.ProbeLaunch("smarthub_key");Check(followApp.ProbeHero=="Console"&&followApp.ProbeCurrentClaim==0,"Warm frame uses accepted destination without a stale current claim");followDevice.InventoryRelease.Set();Until(()=>followApp.ProbeReady);}
  }
  // The accepted input handoff must not wait for a settings read at all.
  {
   var blocked=new FakeDevice{UpdateSourceOnConnect=true};using var ui=Create(blocked);blocked.ThrowPicture=true;
   ui.ProbeInput(2);Until(()=>!ui.ProbeActive&&ui.ProbeIdle);
   Check(blocked.ConnectCalls==1&&!Window.Default.Visible,"Accepted card hides even when picture getters are unavailable");
   Check(blocked.PictureWrites==0&&AppControl.Launches.Count==0,"Source acceptance does not trigger another source or app launch");
  }
  // Back and Settings supersede an unsent profile continuation. Home alone does not.
  foreach(bool settings in new[]{false,true}){
   var followDevice=new FakeDevice{UpdateSourceOnConnect=true};using var followApp=Create(followDevice);
   followApp.ProbeProfile(Appearance.Night);Until(()=>followApp.ProbeSettled);int writes=followDevice.PictureWrites;
   followApp.ProbeInput(2);Until(()=>!followApp.ProbeActive&&followApp.ProbeIdle);followApp.ProbeLaunch("smarthub_key");
   if(settings)followApp.ProbeSettings();else followApp.ProbeBack();
   Until(()=>followApp.ProbeFollowIdle&&followApp.ProbeIdle);
   Check(followDevice.PictureWrites==writes,"New navigation cancels an unsent automatic brightness write");
  }
  {
   var uiDevice=new FakeDevice{ScopeAvailable=false};using var ui=Create(uiDevice);ui.ProbeRight();Check(ui.ProbeHero=="Console","Input focus previews the highlighted device");ui.ProbeUp();Check(ui.ProbeHero=="Apple TV"&&ui.ProbeCurrentClaim==1,"Toolbar shows the actual controlled input");ui.ProbeDown();Check(ui.ProbeHero=="Console","Returning to cards preserves the preview focus");
   ui.ProbeBrightnessOpen();ui.ProbeDown();Check(!ui.ProbeScopeFocused&&ui.ProbeScopeReadOnly=="All sources","Unavailable scope is a readable status, never a dead focus target");ui.ProbeRight();Until(()=>ui.ProbeSettled);Check(uiDevice.Brightness==50,"Maximum brightness clamps without redundant native writes");
  }
  foreach(int source in new[]{13,14}){
   var profileDevice=new FakeDevice{Source=source,Mode=source==13?"655361":"393225"};using var profileApp=Create(profileDevice);
   profileApp.ProbeProfile(Appearance.Night);Until(()=>profileApp.ProbeSettled);Check(profileDevice.Brightness==0,"Night changes brightness only");Check(profileDevice.Mode==(source==13?"655361":"393225"),"Native preset preserved");
   profileApp.ProbeBrightnessOpen();Check(profileApp.ProbeSliderTitle=="Dim level","Editor names active brightness memory");profileApp.ProbeRight();Until(()=>profileApp.ProbeSettled&&profileDevice.Brightness==1);profileApp.ProbeBack();Until(()=>profileApp.ProbeSettled&&!profileApp.ProbePanelOpen);
   profileApp.ProbeProfile(Appearance.Day);Until(()=>profileApp.ProbeSettled);Check(profileDevice.Brightness==50,"Day retains its independent level");
   profileApp.ProbeProfile(Appearance.Night);Until(()=>profileApp.ProbeSettled);Check(profileDevice.Brightness==1,"Night recalls the customized value");
   int otherSource=source==13?14:13;profileDevice.Source=otherSource;profileDevice.Mode=otherSource==13?"655361":"458769";profileDevice.Brightness=50;profileApp.ProbeRefresh();Until(()=>profileApp.ProbeReady);profileApp.ProbeTick();
   Check(profileDevice.Brightness==50,"Changing input alone never applies a brightness profile");
   profileApp.ProbeProfile(Appearance.Night);Until(()=>profileApp.ProbeSettled);Check(profileDevice.Brightness==1,"Customized Night is shared with the other input");
   Check(profileDevice.Mode==(otherSource==13?"655361":"458769"),"Shared profile retains destination native preset");
   profileDevice.Source=source;profileApp.ProbeRefresh();Until(()=>profileApp.ProbeReady);profileApp.ProbeTick();
   profileApp.ProbeBack();Until(()=>!profileApp.ProbeActive&&profileApp.ProbeIdle);Check(profileDevice.LastSource==source,"Profiles preserve Back source routing");
  }
  var device=new FakeDevice();using(var app=Create(device)){
  Check(app.ProbeBrightness.Contains("50"),"Initial picture caption");
  app.ProbeRight();int focus=app.ProbeSelected;device.ConnectRelease.Reset();app.ProbeBack();
  Until(()=>device.ConnectEntered.IsSet);app.ProbePause();app.ProbeResume();
  int raised=Window.Default.Raises;
  app.ProbeLaunch("source_return","http://tizen.org/appcontrol/operation/default");
  Check(Window.Default.Raises==raised,"Unsolicited source-return launch must not raise Cove");
  Check(!Window.Default.Visible,"Back followed by OS pause must keep Cove hidden");
  device.ConnectRelease.Set();Until(()=>app.ProbeIdle);Tizen.NUI.Timer.Pump();
  Check(device.LastSource==13,"Back must ignore highlighted card");Check(device.PictureWrites==0,"Back must not change picture settings");
  app.ProbeLaunch("smarthub_key","http://tizen.org/appcontrol/operation/main");Until(()=>app.ProbeReady);
  Check(Window.Default.Visible&&app.ProbeActive,"Real Home must reopen Cove");
  }
  foreach(bool readThrows in new[]{false,true}){
   device=new FakeDevice();using var app=Create(device);device.ThrowAfterConnect=readThrows;device.TransitionAfterConnect=!readThrows;
   app.ProbeBack();Until(()=>app.ProbeIdle&&device.ConnectCalls==1&&!app.ProbeActive);
   Check(AppControl.Launches.Count==0,"Accepted source activation must not also relaunch viewer after unsettled/failed readback");
   Check(!Window.Default.Visible,"Accepted return hides window");Check(device.PictureWrites==0,"No picture setter during return");
  }
  device=new FakeDevice();using(var app=Create(device)){
   device.ConnectRelease.Reset();app.ProbeBack();Until(()=>device.ConnectEntered.IsSet);
   app.ProbeLaunch("smarthub_key");device.ConnectRelease.Set();Until(()=>app.ProbeReady);Tizen.NUI.Timer.Pump();
   Check(Window.Default.Visible&&app.ProbeActive,"A late return completion must not hide a newer Home");
   Check(AppControl.Launches.Count==0,"A late result cannot trigger fallback");
  }
  device=new FakeDevice();using(var app=Create(device)){
   device.InventoryEntered.Reset();device.InventoryRelease.Reset();app.ProbeRefresh();Until(()=>device.InventoryEntered.IsSet);
   int before=device.PictureReads;string caption=app.ProbeBrightness;app.ProbeBack();
   Check(app.ProbeBrightness==caption,"Back must not redraw its outgoing caption");
   device.InventoryRelease.Set();Until(()=>app.ProbeIdle&&device.ConnectCalls==1&&!app.ProbeActive);
   Check(device.PictureReads==before,"Back cancels the obsolete poll before picture reads");
   Check(device.LastSource==13,"Back behind a poll returns to current source");
  }
  device=new FakeDevice();using(var app=Create(device)){
   app.ProbeBrightnessOpen();Check(app.ProbePanelOpen,"Brightness panel opened");app.ProbeBack();
   Check(!app.ProbePanelOpen&&device.ConnectCalls==0,"First Back dismisses only the panel");
   app.ProbeBack();Until(()=>!app.ProbeActive&&app.ProbeIdle);
   Check(device.ConnectCalls==1&&device.PictureWrites==0,"Second Back returns without brightness writes");
  }
  device=new FakeDevice();using(var app=Create(device)){
   app.ProbeSettings();Check(AppControl.Launches.Count==1&&AppControl.Launches[0]=="org.tizen.menu","Settings target preserved");
   Window.Default.Hide();app.ProbePause();int raised=Window.Default.Raises;
   app.ProbeLaunch();Check(Window.Default.Raises==raised,"Default app-control must not raise over Settings");
   app.ProbeResume();Until(()=>app.ProbeReady);
   Check(Window.Default.Raises==raised,"Settings resume must not raise over Samsung UI");
  }
  device=new FakeDevice();using(var app=Create(device)){
   device.ConnectCode=0;app.ProbeBack();Until(()=>app.ProbeIdle&&!app.ProbeActive);
   Check(AppControl.Launches.Count==1&&AppControl.Launches[0]=="org.tizen.tv-viewer","Rejected connect has one bounded fallback");
   int raised=Window.Default.Raises;
   for(int i=0;i<8;i++){app.ProbeLaunch();app.ProbeResume();}
   Check(Window.Default.Raises==raised&&!Window.Default.Visible,"Unidentified relaunches cannot form a Home loop");
  }
  device=new FakeDevice();using(var app=Create(device)){
   device.ThrowPicture=true;string caption=app.ProbeBrightness;app.ProbeRefresh();Until(()=>app.ProbeIdle);app.ProbeTick();
   Check(app.ProbeBrightness=="Brightness  …","Unreadable picture does not display a cached value as current");
   Check(device.PictureWrites==0,"Cached caption never writes a value");
  }
  device=new FakeDevice();using(var app=Create(device)){
   for(int i=0;i<40;i++){
    app.ProbeRight();app.ProbeBack();Until(()=>app.ProbeIdle&&!app.ProbeActive);
    app.ProbeResume();Check(!Window.Default.Visible,"Unsolicited resume remains hidden");
    app.ProbeLaunch("smarthub_key");Until(()=>app.ProbeReady);
    Check(Window.Default.Visible&&app.ProbeActive,"Warm Home remains available");
   }
   Check(device.ConnectCalls==40&&device.PictureWrites==0,"Repeated lifecycle has exactly one source call per Back");
  }
  foreach(bool pauseFirst in new[]{false,true}){
   device=new FakeDevice();using var app=Create(device);app.ProbeRight();
   Check(app.ProbeSelected==1&&app.ProbeHero=="Console","Different input preview is visible before Back");
   if(pauseFirst)device.ConnectRelease.Reset();app.ProbeBack();
   if(pauseFirst){Until(()=>device.ConnectEntered.IsSet);app.ProbePause();device.ConnectRelease.Set();}
   Until(()=>app.ProbeIdle&&!app.ProbeActive);
   Check(!Window.Default.Visible&&app.ProbeSelected==0&&app.ProbeHero=="Apple TV","Hidden scene resets the old hover before warm Home");
   Check(app.ProbeCachedControlsBlocked&&app.ProbeCurrentClaim==0,"Hidden preview cannot authorize controls or claim a current source");
   device.InventoryEntered.Reset();device.InventoryRelease.Reset();
   bool preparedAtShow=false;Window.Default.BeforeShow=()=>preparedAtShow=app.ProbeHero=="Apple TV"&&app.ProbeSelected==0&&app.ProbeCachedControlsBlocked;
   app.ProbeLaunch("smarthub_key");
   Check(preparedAtShow&&Window.Default.Visible,"Correct cached scene exists at Show before native refresh completes");
   Check(app.ProbeBrightness=="Brightness  …","Warm frame never labels a cached brightness as current");
   device.InventoryRelease.Set();Until(()=>app.ProbeReady);
   Check(device.ConnectCalls==1&&device.PictureWrites==0,"Hidden scene preparation makes no source or picture writes");
  }
  device=new FakeDevice{Source=14};using(var app=Create(device)){
   app.ProbeLeft();app.ProbeBack();Until(()=>app.ProbeIdle&&!app.ProbeActive);
   Check(app.ProbeSelected==1&&app.ProbeHero=="Console","Warm preview uses the last observed current input, not always the first card");
   device.Source=13;app.ProbeLaunch("smarthub_key");Until(()=>app.ProbeReady);
   Check(app.ProbeSelected==0&&app.ProbeHero=="Apple TV","Fresh state replaces a cached preview after an external source change");
   Check(device.PictureWrites==0,"Reopen never changes a saved picture value");
  }
  device=new FakeDevice();using(var app=Create(device)){
   app.ProbeBack();Until(()=>app.ProbeIdle&&!app.ProbeActive);
   Window.Default.Minimized=true;int activated=Window.Default.Activations;
   app.ProbeLaunch("recovery","http://tizen.org/appcontrol/operation/default");app.ProbeResume();
   Check(Window.Default.Minimized&&!Window.Default.Visible&&Window.Default.Activations==activated,"Recovery and incidental resume cannot activate a hidden viewer return");
   app.ProbeLaunch("smarthub_key","http://tizen.org/appcontrol/operation/default");Until(()=>app.ProbeReady);
   Check(!Window.Default.Minimized&&Window.Default.Visible&&Window.Default.Activations==activated+1,"First explicit Home restores an iconified window");
   Check(device.PictureWrites==0,"Window activation never changes brightness");
  }
  foreach(string finish in new[]{"resume","back","settings","pause","input","exhaust"}){
   device=new FakeDevice();using var app=Create(device);app.ProbeBack();Until(()=>app.ProbeIdle&&!app.ProbeActive);app.ProbePause();
   Window.Default.Minimized=true;Window.Default.IgnoredActivations=1;app.ProbeLaunch("smarthub_key","http://tizen.org/appcontrol/operation/default");
   Check(Window.Default.Minimized,"Simulated native callback consumes the first activation");
   if(finish=="back")app.ProbeBack();else if(finish=="settings")app.ProbeSettings();else if(finish=="pause")app.ProbePause();else if(finish=="input"){Until(()=>app.ProbeReady);app.ProbeInput(2);}
   int activated=Window.Default.Activations;Tizen.NUI.Timer.Pump();
   if(finish is "back" or "settings" or "pause" or "input")Check(Window.Default.Activations==activated,"Leaving Home cancels pending activation: "+finish);
   else{
    Check(Window.Default.Visible&&!Window.Default.Minimized&&Window.Default.Activations==activated+1,"Deferred activation restores without a second Home press");
    if(finish=="resume")app.ProbeResume();else Tizen.NUI.Timer.Pump();
    activated=Window.Default.Activations;for(int i=0;i<5;i++)Tizen.NUI.Timer.Pump();
    Check(Window.Default.Activations==activated,"Resume acknowledgement or two attempts ends activation retries");
   }
   Check(device.PictureWrites==0,"Home activation does not write settings");
  }
  {
   device=new FakeDevice();using var app=Create(device);app.ProbeBack();Until(()=>app.ProbeIdle&&!app.ProbeActive);app.ProbePause();
   Window.Default.Minimized=true;Window.Default.IgnoredActivations=1;Window.Default.AfterActivate=app.ProbeResume;
   app.ProbeLaunch("smarthub_key","http://tizen.org/appcontrol/operation/default");Tizen.NUI.Timer.Pump();
   Check(Tizen.NUI.Timer.DisposalsDuringCallback==0,"Reentrant native resume must not destroy its currently dispatching activation timer");
   Check(Window.Default.Visible&&!Window.Default.Minimized&&app.ProbeActive,"Reentrant activation acknowledgement keeps Home active");
   int count=Window.Default.Activations;for(int i=0;i<5;i++)Tizen.NUI.Timer.Pump();
   Check(Window.Default.Activations==count,"Reentrant acknowledgement ends deferred activation");
  }
  Check(LaunchIntentPolicy.Classify(null,null)==LaunchIntent.Open,"Unqualified default is not Home evidence");
  Check(LaunchIntentPolicy.Classify("http://tizen.org/appcontrol/operation/main",null)==LaunchIntent.Home,"Main operation is Home intent");
  Check(LaunchIntentPolicy.Classify("unknown","smarthub_key")==LaunchIntent.Other,"Conflicting operation rejected");
  Check(LaunchIntentPolicy.Classify("http://tizen.org/appcontrol/operation/main","source_return")==LaunchIntent.Other,"Conflicting entry rejected");
  Console.WriteLine(System.Text.Json.JsonSerializer.Serialize(new{checks,passed=true,real_window_code=true,platform_simulated=true,tv_contacted=false}));
 }
}
