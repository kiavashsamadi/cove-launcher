using System;
using System.Threading;
using System.Threading.Tasks;
namespace Cove.Launcher;

// One coalesced inventory reader. Notifications remain subscribed while the
// window is hidden; no background timer, picture read or TV setter is involved.
internal sealed class SourceMonitor:IDisposable {
 readonly Func<SourceSnapshot> read;readonly object gate=new();
 SourceSnapshot? latest;IDisposable? subscription;bool busy,dirty,disposed;
 internal SourceMonitor(IDevice device,Func<SourceSnapshot> read){this.read=read;try{subscription=device.WatchSources(Request);}catch{}Request();}
 internal SourceSnapshot? Latest=>Volatile.Read(ref latest);
 internal bool Busy {get{lock(gate)return busy;}}
 internal void Request(){lock(gate){if(disposed)return;dirty=true;if(busy)return;busy=true;}_=Task.Run(ReadPending);}
 async Task ReadPending(){
  while(true){
   lock(gate){if(disposed||!dirty){busy=false;return;}dirty=false;}
   try{var result=read();lock(gate){if(!disposed)Volatile.Write(ref latest,result);}}catch{}
   // Coalesce hotplug/CEC bursts. The first event is handled immediately.
   lock(gate){if(disposed||!dirty){busy=false;return;}}
   await Task.Delay(100).ConfigureAwait(false);
  }
 }
 public void Dispose(){lock(gate){if(disposed)return;disposed=true;dirty=false;}try{subscription?.Dispose();}catch{}subscription=null;}
}
