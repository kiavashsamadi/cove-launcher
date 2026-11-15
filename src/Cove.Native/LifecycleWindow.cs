using System;
using System.Linq;
using System.Threading;
using Tizen.Applications;
using Tizen.NUI;
using Cove.Launcher;

internal sealed partial class NeutralWindow {
 readonly ViewerReturn viewerReturn=new();bool returningToViewer=>viewerReturn.AwaitingHome;
 bool retainAfterReturn=true;string returnReason="";int? warmPreviewSource;
 Tizen.NUI.Timer? homeActivation;bool nativeResumed,homeActivationPending;
 long homeActivationGeneration;int homeActivationRemaining;
 void CancelHomeActivation(){homeActivationPending=false;homeActivation?.Stop();}
 void ShowForHome(){
  CancelHomeActivation();Window.Default.Show();Window.Default.Activate();
  if(nativeResumed)return;
  // Native launch delivery precedes window-manager acknowledgement. A show
  // during that callback can be consumed without resuming the window. Retry
  // only this explicit Home request, on later UI turns, never in the background.
  homeActivationGeneration=foreground.Lease.Generation;homeActivationRemaining=2;homeActivationPending=true;
  // Activation can synchronously acknowledge resume. Keep one lifetime-owned
  // timer so that callback cannot dispose its own native signal while running.
  if(homeActivation==null){homeActivation=new Tizen.NUI.Timer(80);homeActivation.Tick+=(s,e)=>{
   if(!homeActivationPending||stopping||nativeResumed||!foreground.Accepts(homeActivationGeneration)||returningToViewer||settingsHandoff.IsBackground){CancelHomeActivation();return false;}
   Window.Default.Show();Window.Default.Activate();
   if(!homeActivationPending||nativeResumed||!foreground.Accepts(homeActivationGeneration)||returningToViewer||settingsHandoff.IsBackground||--homeActivationRemaining==0){CancelHomeActivation();return false;}return true;
  };}homeActivation.Start();
 }
 void PauseWork(){
  CancelHomeActivation();
  foreground.Pause();tick?.Stop();CancelBack();brightnessEditor.Cancel();pending=null;
  actionInFlight=false;selectDown=false;lastFocused=null;CancelHeroFade();
  while(updates.TryDequeue(out _)){}
 }
 void PrepareWarmScene(){
  // Prepare the next frame only after hiding, or before an explicit Show.
  // This source is a visual hint, never authorization for a native action.
  int acceptedPreview=Interlocked.Exchange(ref inputReturnPreview,0);
  int? observed=acceptedPreview is >=13 and <=16?acceptedPreview:state.Picture?.Source??state.CurrentSource;
  if(observed.HasValue)warmPreviewSource=observed;
  int current=Array.FindIndex(state.Ports,p=>p.Source==warmPreviewSource);
  if(state.Ports.Length>0){focusRow=0;selected=previousInput=current>=0?current:0;}
  else{focusRow=1;selected=2;previousInput=0;}
  hasState=false;notification="";noticeUntil=0;CancelHeroFade();
  state=new(state.Ports.Select(p=>p with{CanSelect=false}).ToArray(),null,0,false,PicturePending:true,Generation:foreground.Lease.Generation);
  Draw();
 }
 void ResumeWork(bool explicitLaunch){
  if(stopping||!created)return;
  // Home observes an in-progress card selection; it is not a new brightness
  // command. Explicit Settings, Back, another card, or a new edit supersedes it.
  // A return to HDMI may produce intermediate OS resume callbacks. Only a
  // new explicit Home launch may revive Cove after that return was requested.
  if(!viewerReturn.AllowsResume(explicitLaunch)){Window.Default.Hide();return;}
  if(explicitLaunch&&returningToViewer){PauseWork();viewerReturn.Home();}
  if(foreground.Resume()){
   settingsHandoff.Cancel();refreshed=0;picturePendingSince=0;
   // Show the existing artwork immediately, but do not offer stale picture
   // controls or claim a cached source is still current. Refresh asynchronously.
   PrepareWarmScene();tick?.Start();QueueRefresh();
   Bootstrap.Emit(new{@event="warm_resume",explicit_launch=explicitLaunch,polling_resumed=true});
  }
  // An explicit Home launch may target a window hidden by Back. A normal OS
  // resume (including returning from Settings) must never raise over Settings.
  // Raise only changes stacking order. Activate also restores an iconified
  // window after the native viewer has taken foreground ownership.
  if(explicitLaunch){ShowForHome();var pendingNotice=Interlocked.Exchange(ref inputBrightnessNotice,null);if(pendingNotice!=null)Notify(pendingNotice);}
  FocusSelected();
 }
 void HideToViewer(string reason,bool retain=true){
  if(stopping||returningToViewer||!foreground.Active)return;
  CancelHomeActivation();
  viewerReturn.Begin();retainAfterReturn=retain;returnReason=reason;
  settingsHandoff.Cancel();CancelHeroFade();brightnessEditor.Cancel();pending=null;
  if(!retain){CompleteViewerReturn(true);return;}
  // HDMI-card selection already performed and verified connect_source.
  if(reason=="hdmi_selected"){CompleteViewerReturn(false);return;}
  if(requestId==int.MaxValue){CompleteViewerReturn(true);return;}
  // Invalidate the obsolete poll before it starts further picture reads.
  // Keep the outgoing scene unchanged and retain one serialized worker.
  PauseWork();foreground.Resume();tick?.Start();
  pending=new(++requestId,"return_current",null,null);actionInFlight=true;
  if(QueueAction(pending))pending=null;
 }
 void CompleteViewerReturn(bool launchFallback){
  try{
   settingsHandoff.Cancel();PauseWork();
   Window.Default.Hide();PrepareWarmScene();
   if(launchFallback)LaunchViewer();
   Bootstrap.Emit(new{@event="viewer_return_requested",application="org.tizen.tv-viewer",route=launchFallback?"launch_fallback":"current_source",source_selection_scope="fresh_current_hdmi_only"});
   if(!retainAfterReturn){Stop("remote_exit");return;}
   Bootstrap.Emit(new{@event="warm_suspended",reason=returnReason,polling_paused=true,worker_finishing=Volatile.Read(ref workerBusy)!=0});
  }catch(Exception error){Bootstrap.Emit(new{@event="viewer_return_failed",kind=error.GetType().Name});Stop("viewer_return_failed");}
 }
 static void LaunchViewer(){
  var request=new AppControl{ApplicationId="org.tizen.tv-viewer"};
  AppControl.SendLaunchRequest(request);
 }
 void Stop(string reason){
  if(stopping)return;CancelInputHandoff();PauseWork();stopping=true;exitReason=reason;settingsHandoff.Cancel();
  Bootstrap.Emit(new{@event="exit_requested",reason});TestStopping();Exit();
 }
 protected override void OnPause(){
  nativeResumed=false;
  if(!returningToViewer&&Volatile.Read(ref inputSelectionPending)!=0){viewerReturn.Begin();retainAfterReturn=true;returnReason="hdmi_selected";}
  Volatile.Write(ref inputSelectionPending,0);
  // Source activation can background us before its worker returns. Finish
  // the visibility handoff here; do not wait for a now-cancelled UI reply.
  if(returningToViewer){Window.Default.Hide();Bootstrap.Emit(new{@event="viewer_background_acknowledged"});}
  PauseWork();if(returningToViewer)PrepareWarmScene();bool settings=settingsHandoff.Pause();base.OnPause();
  // One bounded data-file save, not a background poll or service. It never
  // calls a TV setter and does not delay the HDMI/Settings window handoff.
  System.Threading.Tasks.Task.Run(()=>controls?.FlushProfiles());
  Bootstrap.Emit(new{@event=settings?"settings_handoff_backgrounded":"os_backgrounded",polling_paused=true});
 }
 protected override void OnResume(){nativeResumed=true;CancelHomeActivation();base.OnResume();ResumeWork(false);}
 protected override void OnAppControlReceived(AppControlReceivedEventArgs e){
  base.OnAppControlReceived(e);
  string? operation=null,entry=null;bool readable=true;
  try{operation=e.ReceivedAppControl.Operation;e.ReceivedAppControl.ExtraData.TryGet("entry_point",out entry);}catch{readable=false;}
  var intent=readable?LaunchIntentPolicy.Classify(operation,entry):LaunchIntent.Other;
  // Record classifications, never arbitrary app-control values or user data.
  Bootstrap.Emit(new{@event="launch_intent",intent=intent.ToString(),return_pending=returningToViewer,metadata_readable=readable});
  if((returningToViewer||settingsHandoff.IsBackground)&&intent!=LaunchIntent.Home){if(returningToViewer)Window.Default.Hide();return;}
  if(intent==LaunchIntent.Other)return;
  ResumeWork(true);
 }
 protected override void OnLowMemory(LowMemoryEventArgs e){
  base.OnLowMemory(e);
  // Release the whole cache if the OS needs it. Foreground Settings may depend
  // on the caller, so never terminate that handoff merely to free our cache.
  if(!foreground.Active&&!settingsHandoff.IsBackground)Stop("background_memory_pressure");
 }
 protected override void OnTerminate(){
  inputHandoff.Dispose();PauseWork();controls?.FlushProfiles();foreground.Dispose();if(!stopping){stopping=true;exitReason="system_termination";}
  tick?.Dispose();tick=null;homeActivation?.Dispose();homeActivation=null;try{FocusManager.Instance.ClearFocus();}catch{}
  backDispatch?.Dispose();backDispatch=null;
  focusDecoration?.Dispose();foreach(var view in views.AsEnumerable().Reverse())view.Dispose();views.Clear();
  foreach(var item in art.Values)item.Dispose();art.Clear();
  Bootstrap.Emit(new{@event="terminated",window_created=created,exit_requested=stopping,assets_ready=assetsReady,worker_pending=Volatile.Read(ref workerBusy)!=0});base.OnTerminate();
 }
}
