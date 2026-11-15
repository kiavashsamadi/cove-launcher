internal enum BackDestination { None, BrightnessPanel, Viewer, Exit }

// One gesture belongs to one foreground session and one destination. Resolve it
// on release, then dispatch outside the key callback so the viewer cannot receive
// the release from the same press that dismissed Cove.
internal sealed class BackGesture {
 BackDestination held,queued;long generation;
 internal bool Busy=>held!=BackDestination.None||queued!=BackDestination.None;
 internal void Down(BackDestination destination,long currentGeneration){
  if(destination==BackDestination.None)return;
  if(Busy&&generation!=currentGeneration)Cancel();
  if(queued!=BackDestination.None)return;
  if(held==BackDestination.None){held=destination;generation=currentGeneration;}
  else if(destination==BackDestination.Exit)held=BackDestination.Exit;
 }
 internal bool Up(long currentGeneration){
  if(generation!=currentGeneration){Cancel();return false;}
  if(held==BackDestination.None)return false;
  queued=held;held=BackDestination.None;return true;
 }
 internal BackDestination Take(long currentGeneration){
  if(generation!=currentGeneration){Cancel();return BackDestination.None;}
  var result=queued;queued=BackDestination.None;return result;
 }
 internal void Cancel(){held=queued=BackDestination.None;generation=0;}
}
