using Tizen.NUI;

internal sealed partial class NeutralWindow {
 readonly BackGesture backGesture=new();
 Timer? backDispatch;
 static bool IsBackKey(string key)=>key is "XF86Back" or "Back" or "Escape" or "XF86Exit";
 void HandleBackEvent(string key,Key.StateType phase){
  long generation=foreground.Lease.Generation;
  if(phase==Key.StateType.Down){
   CancelInputHandoff();
   var destination=key=="XF86Exit"?BackDestination.Exit:brightnessEditor.IsOpen?BackDestination.BrightnessPanel:BackDestination.Viewer;
   backGesture.Down(destination,generation);
  }else if(phase==Key.StateType.Up&&backGesture.Up(generation)){
   if(backDispatch==null){backDispatch=new Timer(1);backDispatch.Tick+=(_,_)=>DispatchBack();}
   backDispatch.Start();
  }
 }
 bool DispatchBack(){
  if(stopping||!foreground.Active){CancelBack();return false;}
  var destination=backGesture.Take(foreground.Lease.Generation);
  Bootstrap.Emit(new{@event="back_released",destination=destination.ToString(),deferred=true});
  switch(destination){
   case BackDestination.BrightnessPanel:
    // A disappearing panel must not turn this same press into a viewer return.
    HandleBrightnessKey("Back",false,true);break;
   case BackDestination.Viewer:HideToViewer("remote_exit");break;
   case BackDestination.Exit:HideToViewer("explicit_exit",retain:false);break;
  }
  return false; // One dispatch only, never an additional repeating poll.
 }
 void CancelBack(){backDispatch?.Stop();backGesture.Cancel();}
}
