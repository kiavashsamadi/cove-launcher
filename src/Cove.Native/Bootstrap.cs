// System-only entry point; all file access is read-only and fixed to pinned TV framework files.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Runtime.CompilerServices;
using System.Runtime.InteropServices;
using System.Runtime.Loader;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Threading;
internal static class Bootstrap {
 static int resolveCount;
 static readonly object ProofLock=new();
 internal static bool ExactFirmwareValidated;
 static readonly Queue<string> MemoryEvents=new();
 [DllImport("libc.so.6",EntryPoint="getpid")]static extern int ProcessId();
 sealed class FrameworkPin {
  internal readonly string Name,Path,Sha256;internal readonly long Bytes;
  internal FrameworkPin(string name,string path,string sha,long bytes){Name=name;Path=path;Sha256=sha;Bytes=bytes;}
 }
 static readonly FrameworkPin[] Pins={
  new FrameworkPin("Tizen.NUI","/usr/share/dotnet.tizen/framework/Tizen.NUI.dll","5bb87e8eb11ac72b82e9f268d0c330c287726d935d0b03502f265ba8f8b869fa",2391040),
  new FrameworkPin("Tizen.Applications.Common","/usr/share/dotnet.tizen/framework/Tizen.Applications.Common.dll","481067b606ef873deb128bb1319f0ec228855d204314c5f4deea7df4ecc97fb5",118784),
  new FrameworkPin("Tizen.System","/usr/share/dotnet.tizen/framework/Tizen.System.dll","d00a275ca39010a07e0820ab602e6c52056cab1c1f3e22260eb3233352c6f36e",49664),
  new FrameworkPin("Tizen","/usr/share/dotnet.tizen/framework/Tizen.dll","90ff7f4846ef0ec4d4fc01294d38e534ef835c53d49b04912c7e1d5a785b6aeb",13824),
  new FrameworkPin("Tizen.Applications.ComponentBased","/usr/share/dotnet.tizen/framework/Tizen.Applications.ComponentBased.dll","b763a579630b074e8187ec25b11bf867716b7eef0c0c6146e75c45d20e884bd3",37888),
  new FrameworkPin("Tizen.Applications.ThemeManager","/usr/share/dotnet.tizen/framework/Tizen.Applications.ThemeManager.dll","99abf143c1c7871e55ecd7a0ce4684a690789305da128b6768881fac65f2c489",14848),
  new FrameworkPin("Tizen.Log","/usr/share/dotnet.tizen/framework/Tizen.Log.dll","394eceb14363e11b593dd94aeef88a8577f8ff6adf442ce086909d72913a3463",10240),
  new FrameworkPin("Tizen.System.Information","/usr/share/dotnet.tizen/framework/Tizen.System.Information.dll","b11ef64599be5c59a0d63633de0a742d29fd4cb8038fdc2d7769026674aea1c2",27648),
  new FrameworkPin("Tizen.System.SystemSettings","/usr/share/dotnet.tizen/framework/Tizen.System.SystemSettings.dll","4741147ef023ad32461eb2505fcbd10a1e731e65e6046e400ebb73dba7afad2d",60416),
  new FrameworkPin("Tizen.Tracer","/usr/share/dotnet.tizen/framework/Tizen.Tracer.dll","876af4c9e440a14b4fb5db9bd8b0ba941779555e29e1f18d59c0d817516676b4",5120),
 };
 static readonly object ResolverLock=new();
 [DllImport("libc.so.6",EntryPoint="getuid",ExactSpelling=true,CallingConvention=CallingConvention.Cdecl)] static extern uint GetUid();
 [DllImport("libc.so.6",EntryPoint="geteuid",ExactSpelling=true,CallingConvention=CallingConvention.Cdecl)] static extern uint GetEffectiveUid();
 [DllImport("libc.so.6",EntryPoint="_exit",ExactSpelling=true,CallingConvention=CallingConvention.Cdecl)] static extern void ImmediateExit(int status);
 internal static void Emit(object record){lock(ProofLock){
  string line=JsonSerializer.Serialize(record);if(Encoding.UTF8.GetByteCount(line)>4096)return;
  if(MemoryEvents.Count>=64)MemoryEvents.Dequeue();MemoryEvents.Enqueue(line);
 }}
 static string StatusField(string key){foreach(string line in File.ReadLines("/proc/self/status"))if(line.StartsWith(key+":",StringComparison.Ordinal))return line.Substring(key.Length+1).Trim();return "missing";}

 static bool IdentityMatches(AssemblyName name,FrameworkPin pin){
  string token=Convert.ToHexString(name.GetPublicKeyToken()??Array.Empty<byte>()).ToLowerInvariant();
  return name.Name==pin.Name&&name.Version==new Version(4,0,0,0)&&String.IsNullOrEmpty(name.CultureName)&&token=="eba370b203a2e242";
 }
 static void VerifyFramework(FrameworkPin pin){
  using(var file=new FileStream(pin.Path,FileMode.Open,FileAccess.Read,FileShare.Read)){
   if(file.Length!=pin.Bytes)throw new InvalidOperationException("framework_size_changed:"+pin.Name);
   using var hash=SHA256.Create();
   if(Convert.ToHexString(hash.ComputeHash(file)).ToLowerInvariant()!=pin.Sha256)throw new InvalidOperationException("framework_hash_changed:"+pin.Name);
  }
  // GetAssemblyName reads metadata; it does not execute the inspected assembly.
  if(!IdentityMatches(AssemblyName.GetAssemblyName(pin.Path),pin))throw new InvalidOperationException("framework_identity_changed:"+pin.Name);
 }
 static Assembly? Resolve(AssemblyLoadContext context,AssemblyName requested){
  lock(ResolverLock){
   if(++resolveCount>32)throw new InvalidOperationException("framework_resolution_limit");
   FrameworkPin? pin=null;foreach(var candidate in Pins)if(requested.Name==candidate.Name){pin=candidate;break;}
   if(pin==null){Emit(new{@event="dependency_unavailable",name=Short(requested.Name??""),version=Short(requested.Version?.ToString()??"")});return null;}
   if(!IdentityMatches(requested,pin))throw new InvalidOperationException("requested_framework_identity_refused:"+pin.Name);
   VerifyFramework(pin);
   var assembly=context.LoadFromAssemblyPath(pin.Path);
   if(!IdentityMatches(assembly.GetName(),pin)||!String.Equals(assembly.Location,pin.Path,StringComparison.Ordinal))throw new InvalidOperationException("loaded_framework_identity_refused:"+pin.Name);
   Emit(new{@event="framework_resolved",name=pin.Name,path=pin.Path,sha256=pin.Sha256});return assembly;
  }
 }
 static string Short(string value)=>value.Length<=1536?value:value.Substring(0,1536);
 internal static bool FallbackEligible(uint uid,uint euid,string label,string[] caps)=>uid==5001&&euid==5001&&label=="User::Pkg::com.samsung.tv.bixby-promotion"&&caps.Length==4&&Array.TrueForAll(caps,c=>c=="0000000000000000");
 [DllImport("libaul.so.0",EntryPoint="aul_launch_app",CallingConvention=CallingConvention.Cdecl)]static extern int LaunchStockApp(string appid,IntPtr request);
 static int ReturnStock(string reason){
  try{
   string label=File.ReadAllText("/proc/self/attr/current").TrimEnd('\0','\n','\r');
   if(!FallbackEligible(GetUid(),GetEffectiveUid(),label,new[]{StatusField("CapEff"),StatusField("CapPrm"),StatusField("CapInh"),StatusField("CapAmb")}))return 3;
   Emit(new{@event="stock_home_fallback",reason});
   // Use the OS app-launch API without loading any changed NUI framework.
   // This launches the existing stock app; it never edits default routing.
   var worker=new Thread(()=>{try{int code=LaunchStockApp("com.samsung.tv.csfs",IntPtr.Zero);Emit(new{@event="stock_home_launch_requested",native_result=code});}catch{}});
   worker.IsBackground=true;worker.Start();worker.Join(1500);
  }catch{}
  return 3;
 }
 // This boundary must remain non-inlined: no NUI type is touched by Main's JIT before resolver registration.
 [MethodImpl(MethodImplOptions.NoInlining)] static int RunUi(string[] args)=>NeutralWindow.RunDisplay(args);
 public static int Main(string[] args){
  var elapsed=Stopwatch.StartNew();
  try{
   Console.OutputEncoding=new UTF8Encoding(false);
   uint uid=GetUid(),euid=GetEffectiveUid();
   if(uid!=5001||euid!=5001||args.Length>64||System.Linq.Enumerable.Sum(args,a=>Encoding.UTF8.GetByteCount(a))>8192)return 3;
   string label=File.ReadAllText("/proc/self/attr/current").TrimEnd('\0','\n','\r');
   if(label!="User::Pkg::com.samsung.tv.bixby-promotion")return 3;
   string product=File.ReadAllText("/etc/prd_info.ini");
   ExactFirmwareValidated=product.Contains("Version=T-PTMCAKUC-0090-2220.4;",StringComparison.Ordinal)&&product.Contains("Build=TIZEN-TRUNK2025-PontusM-OSU-2023-HOTFIX-RELEASE_20260319.2;",StringComparison.Ordinal);
   if(!ExactFirmwareValidated)return ReturnStock("firmware_guard");
   Emit(new{@event="identity",uid,euid,smack=label,argument_count=args.Length,bootstrap="cove_launcher"});
   foreach(string field in new[]{"CapEff","CapPrm","CapInh","CapAmb"})if(StatusField(field)!="0000000000000000"){Emit(new{@event="refused",reason="privileged_gui_refused",field,value=StatusField(field)});return 3;}
   Emit(new{@event="registered_context",smack_label=label,controls="guarded_hdmi_and_existing_presets"});
   AssemblyLoadContext.Default.Resolving+=Resolve;
   try{
    foreach(var pin in Pins)VerifyFramework(pin);
    Emit(new{@event="framework_guard",status="ok",files=Pins.Length,readonly_load=true});
    int ui=RunUi(args);return ui==0?0:ReturnStock("ui_unverified");
   }finally{AssemblyLoadContext.Default.Resolving-=Resolve;}
  }catch(Exception error){
   Emit(new{@event="failed",kind=error.GetType().Name,message=Short(error.Message),inner_kind=error.InnerException?.GetType().Name,inner_message=Short(error.InnerException?.Message??"")});return ReturnStock("startup_failure");
  }
 }
}
