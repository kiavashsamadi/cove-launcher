using System;using System.Collections.Generic;using System.Diagnostics;using System.Globalization;using System.Runtime.InteropServices;using System.Text;
namespace Cove.Launcher;
// Exact-firmware native interop. Broader brightness availability needs a native
// capability check before installation. No native picture-mode setter exists.
internal sealed class NativeDevice:IDevice {
 [DllImport("libsource-api.so",EntryPoint="get_source_list",ExactSpelling=true,CallingConvention=CallingConvention.Cdecl)]static extern IntPtr Sources();
 [DllImport("libsource-api.so",EntryPoint="connect_source")]static extern int Connect(int source);
 [DllImport("libvconf.so.0",EntryPoint="vconf_get_int",ExactSpelling=true,CallingConvention=CallingConvention.Cdecl)]static extern int Source(string key,out int value);
 [DllImport("libvconf.so.0",EntryPoint="vconf_get_bool",ExactSpelling=true,CallingConvention=CallingConvention.Cdecl)]static extern int Flag(string key,out int value);
 [DllImport("libsettings-api.so",EntryPoint="CSharpGetItemValue")]static extern bool Get(string key,out string name,out string value);
 [DllImport("libsettings-api.so",EntryPoint="CSharpSetItemValue")]static extern bool Set(string key,string value);
 [DllImport("libsettings-api.so",EntryPoint="CSharpGetItemMinMaxStepValue",ExactSpelling=true,CallingConvention=CallingConvention.Cdecl)]
 [return:MarshalAs(UnmanagedType.I1)]static extern bool Range(string key,out double minimum,out double maximum,out double step);
 // Cached ARM wrapper forwards (string, bool&, timeout), returning success.
 // Keep native bool widths explicit; do not confuse success with enabled state.
 [DllImport("libsettings-api.so",EntryPoint="CSharpGetItemEnable",ExactSpelling=true,CallingConvention=CallingConvention.Cdecl)]
 [return:MarshalAs(UnmanagedType.I1)]static extern bool Enabled(string key,[MarshalAs(UnmanagedType.I1)]out bool enabled);
 static long Now()=>Stopwatch.GetTimestamp()*1000/Stopwatch.Frequency;
 static string Read(string key){if(!Get(key,out var name,out var value)||name==null||value==null||name.Length>512||value.Length>512)throw new InvalidOperationException("getter_failed");return value;}
 public int ReadCurrentSource(){if(Source("memory/system/source_type",out int source)!=0)throw new InvalidOperationException("source_failed");return source;}
 public IDisposable? WatchSources(Action changed)=>new NativeSourceSubscription(changed);
 public string? ReadAudioReturnChannel()=>Flag("memory/cec-service/receiver_eARC_support",out int supported)==0&&supported==1?"eARC":null;
 public (int Source,bool SourceTransition) ReadSourceContext(){long started=Now();int before=ReadCurrentSource(),after=ReadCurrentSource();return(after,before!=after||Now()-started>250);}
 public DeviceSnapshot ReadPicture()=>PictureSampling.Read(ReadCurrentSource,Read,()=>Capability("brightness")&&HasBrightnessRange(),()=>Capability("applypicmode"),Now);
 static bool Capability(string key){try{return Enabled(key,out bool enabled)&&enabled;}catch{return false;}}
 // Verified against this firmware's managed wrappers and source implementation.
 // EP 0 is a valid video signal; paused (3), missing, unsupported and unknown
 // states are refused. This check runs only for automatic post-card following.
 [DllImport("/usr/lib/libep-system-api.so",EntryPoint="ep_source_get_signal_status")]static extern int Signal(out int state,int profile);
 [DllImport("/usr/lib/libep-system-api.so",EntryPoint="ep_source_get_source")]static extern int EpSource(out int source,int profile,int caller);
 [DllImport("/usr/lib/libavoc-managed.so",EntryPoint="avoc_managed_get_picture_mode")]static extern int ActiveMode(out int mode);
 static (int,int) ReadEpSource(){int code=EpSource(out int source,0,0);return(code,source);}
 static (int,int) ReadSignal(){int code=Signal(out int state,0);return(code,state);}
 static (int,int) ReadActiveMode(){int code=ActiveMode(out int mode);return(code,mode);}
 public bool CanFollowBrightness(DeviceSnapshot state){try{return InputSignalSampling.Read(state,ReadCurrentSource,ReadEpSource,ReadSignal,ReadActiveMode,Now);}catch{return false;}}
 public string ReadSources(){IntPtr p=Sources();if(p==IntPtr.Zero)throw new InvalidOperationException("sources_unavailable");byte[] bytes=new byte[16384];for(int n=0;n<bytes.Length;n++){byte b=Marshal.ReadByte(p,n);if(b==0)return new UTF8Encoding(false,true).GetString(bytes,0,n);bytes[n]=b;}throw new InvalidOperationException("sources_bound");}
 public bool SetBrightness(int value)=>BrightnessPolicy.InRange(value)?Set("brightness",value.ToString(CultureInfo.InvariantCulture)):throw new InvalidOperationException("brightness_not_allowed");
 public bool SetPictureScope(PictureScope scope)=>scope switch{PictureScope.CurrentSource=>Set("applypicmode","1"),PictureScope.AllSources=>Set("applypicmode","0"),_=>throw new InvalidOperationException("scope_not_allowed")};
 public bool HasBrightnessRange()=>Range("brightness",out double minimum,out double maximum,out double step)&&minimum==0&&maximum==50&&step==1;
 public int ConnectHdmi(int fixedSource)=>fixedSource switch{13=>Connect(13),14=>Connect(14),15=>Connect(15),16=>Connect(16),_=>throw new InvalidOperationException("source_not_allowed")};
}

// The firmware callback runs on a native background thread. Keep its delegate
// rooted for process lifetime, and use opaque integer tokens rather than freed
// GCHandles. Late callbacks after removal are harmless dictionary misses.
internal sealed class NativeSourceSubscription:IDisposable {
 [UnmanagedFunctionPointer(CallingConvention.Cdecl)]delegate void Changed(int reason,IntPtr token);
 [DllImport("libsource-api.so",EntryPoint="register_sourcelist_changed_callback",CallingConvention=CallingConvention.Cdecl)]static extern void Register(Changed callback,IntPtr token);
 [DllImport("libsource-api.so",EntryPoint="unregister_sourcelist_changed_callback",CallingConvention=CallingConvention.Cdecl)]static extern void Unregister(IntPtr token);
 static readonly System.Collections.Concurrent.ConcurrentDictionary<IntPtr,Action> listeners=new();
 static readonly Changed callback=Dispatch;static int nextToken;IntPtr token;
 internal NativeSourceSubscription(Action changed){
  token=new IntPtr(System.Threading.Interlocked.Increment(ref nextToken));if(token==IntPtr.Zero)throw new InvalidOperationException("source_subscription_limit");
  listeners[token]=changed;try{Register(callback,token);}catch{listeners.TryRemove(token,out _);token=IntPtr.Zero;throw;}
 }
 static void Dispatch(int reason,IntPtr token){try{if(listeners.TryGetValue(token,out var changed))changed();}catch{}}
 public void Dispose(){var owned=System.Threading.Interlocked.Exchange(ref token,IntPtr.Zero);if(owned==IntPtr.Zero)return;listeners.TryRemove(owned,out _);Unregister(owned);}
}
