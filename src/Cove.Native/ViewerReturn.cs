// UI-thread intent, independent of incidental OS pause/resume notifications.
// Returning to HDMI must not revive Cove until an explicit Home app-control.
internal sealed class ViewerReturn {
 internal bool AwaitingHome {get;private set;}
 internal bool Begin(){if(AwaitingHome)return false;AwaitingHome=true;return true;}
 internal bool AllowsResume(bool explicitHome)=>explicitHome||!AwaitingHome;
 internal void Home(){AwaitingHome=false;}
}
