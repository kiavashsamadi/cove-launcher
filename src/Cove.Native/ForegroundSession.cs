using System;
using System.Collections.Concurrent;
using System.Threading;

// Owned by the UI thread. A worker keeps its original lease even when a new
// foreground session starts, so late replies cannot redraw or dismiss it.
internal readonly record struct ForegroundLease(long Generation,CancellationToken Cancellation);
internal sealed class ForegroundSession:IDisposable {
 CancellationTokenSource cancellation=new();
 long generation;
 internal bool Active {get;private set;}=true;
 internal ForegroundLease Lease=>new(generation,cancellation.Token);
 internal bool Accepts(long replyGeneration)=>Active&&replyGeneration==generation;
 internal bool TryTakeCurrent<T>(ConcurrentQueue<T> replies,Func<T,long> replyGeneration,out T value){
  // Check the item actually removed, never a separate Peek: a producer can
  // enqueue or replace the head between Peek and Dequeue, including after
  // cancellation. Only the UI thread changes the foreground generation.
  while(replies.TryDequeue(out var item))if(Accepts(replyGeneration(item))){value=item;return true;}
  value=default!;return false;
 }
 internal bool Pause(){if(!Active)return false;Active=false;cancellation.Cancel();return true;}
 internal bool Resume(){if(Active)return false;cancellation.Dispose();cancellation=new();generation++;Active=true;return true;}
 public void Dispose(){Pause();cancellation.Dispose();}
}
