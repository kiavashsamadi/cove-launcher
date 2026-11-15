// Bounded native controls; all writes require fresh context and readback.
using System;using System.Collections.Generic;using System.Diagnostics;using System.Linq;using System.Text;using System.Text.Json;using System.Threading;
namespace Cove.Launcher;
internal sealed record PortState(int Port,int Source,string Label,bool Connected,bool CanSelect,bool AudioEndpoint=false);
internal enum PictureScope {Unknown=-1,AllSources=0,CurrentSource=1}
internal sealed record DeviceSnapshot(int Source,string Mode,int Brightness,IReadOnlySet<string> AvailableModes,long ObservedAt,bool SourceTransition,PictureScope Scope=PictureScope.Unknown,bool BrightnessAvailable=false,bool ScopeAvailable=false,int DayBrightness=50,int NightBrightness=0,Appearance? ProfileSelected=null);
internal interface IDevice {
 DeviceSnapshot ReadPicture();
 (int Source,bool SourceTransition) ReadSourceContext(){var state=ReadPicture();return(state.Source,state.SourceTransition);}
 string ReadSources();
 bool SetBrightness(int value);
 bool SetPictureScope(PictureScope scope);
 bool HasBrightnessRange();
 bool CanFollowBrightness(DeviceSnapshot state)=>false;
 int ConnectHdmi(int fixedSource);
}
internal sealed record ControlResult(bool Verified,string Status,DeviceSnapshot? State=null,bool SourceRequestAccepted=false,InputBrightnessPlan? InputBrightness=null);
internal sealed record PictureScopeChange(DeviceSnapshot Original,PictureScope Target,CancellationToken Cancellation=default);
internal sealed record Request(int Id,string Action,int? Port,Appearance? Appearance,BrightnessChange? Brightness=null,PictureScopeChange? ScopeChange=null);
internal static class ControlProtocol {
 // Reject duplicate/unknown keys, coercion, noncanonical versions, arbitrary
 // settings, app IDs, commands, URLs and oversized requests.
 internal static Request Parse(string text){
  if(Encoding.UTF8.GetByteCount(text)>512)throw new FormatException("message_too_large");
  using var d=JsonDocument.Parse(text,new JsonDocumentOptions{MaxDepth=3});
  if(d.RootElement.ValueKind!=JsonValueKind.Object)throw new FormatException("object_required");
  var fields=new Dictionary<string,JsonElement>(StringComparer.Ordinal);
  foreach(var p in d.RootElement.EnumerateObject())if(!fields.TryAdd(p.Name,p.Value))throw new FormatException("duplicate_key");
  if(!fields.TryGetValue("v",out var v)||!v.TryGetInt32(out int version)||version!=1||!fields.TryGetValue("id",out var id)||!id.TryGetInt32(out int number)||number<1||!fields.TryGetValue("action",out var action)||action.ValueKind!=JsonValueKind.String)throw new FormatException("envelope_required");
  switch(action.GetString()){
   case "hdmi":
    if(fields.Count!=4||!fields.TryGetValue("port",out var port)||!port.TryGetInt32(out int n)||n<1||n>4)throw new FormatException("physical_hdmi_required");
    return new Request(number,"hdmi",n,null);
   case "appearance":
    if(fields.Count!=4||!fields.TryGetValue("value",out var value)||value.ValueKind!=JsonValueKind.String)throw new FormatException("appearance_required");
    return new Request(number,"appearance",null,value.GetString() switch{"day"=>Appearance.Day,"night"=>Appearance.Night,_=>throw new FormatException("appearance_required")});
   default:throw new FormatException("action_not_allowed");
  }
 }
}
internal sealed class SourceInventory {
 readonly Dictionary<int,PortState> remembered=new();
 internal IReadOnlyList<PortState> Update(string? json){
  try{
   if(json==null||Encoding.UTF8.GetByteCount(json)>16384)throw new FormatException();
   using var doc=JsonDocument.Parse(json,new JsonDocumentOptions{MaxDepth=5});
   if(doc.RootElement.ValueKind!=JsonValueKind.Array||doc.RootElement.GetArrayLength()>32)throw new FormatException();
   var next=new Dictionary<int,PortState>();
   foreach(var row in doc.RootElement.EnumerateArray()){
    var fields=new Dictionary<string,JsonElement>(StringComparer.Ordinal);
    foreach(var p in row.EnumerateObject())if(!fields.TryAdd(p.Name,p.Value))throw new FormatException();
    if(!fields.TryGetValue("sourceType",out var type)||!type.TryGetInt32(out int source))throw new FormatException();
    if(source<13||source>16)continue;
    int port=source-12;
    if(!fields.TryGetValue("connectionState",out var connected)||connected.ValueKind!=JsonValueKind.True&&connected.ValueKind!=JsonValueKind.False)throw new FormatException();
    string label="";
    foreach(string key in new[]{"editName","detectedName"}){
     if(fields.TryGetValue(key,out var name)){if(name.ValueKind!=JsonValueKind.String)throw new FormatException();string candidate=name.GetString()!;if(candidate.Length>256)throw new FormatException();if(label.Length==0)label=Uri.UnescapeDataString(candidate);}
    }
    label=new string(label.Where(c=>!char.IsControl(c)).ToArray()).Trim();
    if(label.Length==0)label=remembered.TryGetValue(port,out var previous)?previous.Label:$"HDMI {port}";
    bool audio=false;
    if(fields.TryGetValue("iconPath",out var icon)){
     if(icon.ValueKind!=JsonValueKind.String||icon.GetString()!.Length>1024)throw new FormatException();
     audio=icon.GetString()=="/usr/apps/com.samsung.tv.theme-resource/shared/res/VD_ICONS/i_icon_device_m_speaker.svg"||icon.GetString()=="/opt/usr/apps/com.samsung.tv.theme-resource/shared/res/VD_ICONS/i_icon_device_m_speaker.svg";
    }
    if(!next.TryAdd(port,new PortState(port,source,label,connected.GetBoolean(),connected.GetBoolean()&&!audio,audio)))throw new FormatException();
   }
   // An incomplete response is not evidence that a missing cable was removed.
   if(next.Count!=4)throw new FormatException();
   remembered.Clear();foreach(var p in next)remembered.Add(p.Key,p.Value);
  }catch(Exception e)when(e is JsonException||e is FormatException||e is InvalidOperationException||e is ArgumentException){
   foreach(int key in remembered.Keys.ToArray())remembered[key]=remembered[key] with{CanSelect=false};
  }
  // powerState is deliberately irrelevant: sleeping connected devices stay.
  return remembered.Values.Where(p=>p.Connected&&!p.AudioEndpoint).OrderBy(p=>p.Port).ToArray();
 }
}
internal sealed class ControlAdapter {
 readonly IDevice device;readonly Func<long> now;readonly bool adjustableBrightness;readonly SourceInventory inventory=new();readonly BrightnessProfiles profiles;int busy,lastId;
 internal ControlAdapter(IDevice device,Func<long>? monotonicMilliseconds=null,bool adjustableBrightness=false,BrightnessProfiles? profiles=null){this.device=device;this.adjustableBrightness=adjustableBrightness;this.profiles=profiles??new();now=monotonicMilliseconds??(()=>Stopwatch.GetTimestamp()*1000/Stopwatch.Frequency);}
 readonly object deviceGate=new();readonly PictureObservation observation=new();InputBrightnessPlan? following;
 internal DeviceSnapshot ReadPicture(){lock(deviceGate){
  DeviceSnapshot raw;try{raw=device.ReadPicture();}catch{observation.ResetCandidate();throw;}
  // A follow request has not established the destination's final value yet.
  // UI reads may interleave, but must not clear intent or display provisional data.
  if(following!=null)return profiles.Describe(raw with{SourceTransition=true});
  var observed=observation.Observe(raw,now(),out bool manualChange);
  if(manualChange)profiles.ClearChoice(observed);
  var state=profiles.Describe(observed);profiles.Flush();return state;
 }}
 internal bool FlushProfiles()=>profiles.Flush(true);
 internal (int Source,bool SourceTransition) ReadSourceContext(){lock(deviceGate)return device.ReadSourceContext();}
 internal IReadOnlyList<PortState> RefreshSources(){lock(deviceGate){try{return inventory.Update(device.ReadSources());}catch{return inventory.Update(null);}}}
 internal ControlResult Execute(Request request,CancellationToken foreground=default){lock(deviceGate)return ExecuteLocked(request,foreground);}
 ControlResult ExecuteLocked(Request request,CancellationToken foreground){
  if(Interlocked.CompareExchange(ref busy,1,0)!=0)return new(false,"busy");
  bool sourceAccepted=false;InputBrightnessPlan? inputBrightness=null;
  try{
   if(foreground.IsCancellationRequested)return new(false,"foreground_interrupted");
   if(request.Id<=lastId)return new(false,"duplicate_or_old_request");lastId=request.Id;
   if(request.Action=="profiles_save"&&request.Port==null&&request.Appearance==null&&request.Brightness==null&&request.ScopeChange==null)return new(profiles.Flush(true),"profiles_saved");
   if(request.Action=="picture_scope"&&adjustableBrightness&&request.ScopeChange is PictureScopeChange scope&&request.Brightness==null&&request.Appearance==null&&request.Port==null)return ChangeScope(scope,foreground);
   if(request.ScopeChange!=null)return new(false,"request_not_allowed");
   if(request.Action=="appearance"&&adjustableBrightness&&request.Appearance is Appearance appearance&&request.Brightness is BrightnessChange profileChange&&request.Port==null)return ChangeAppearance(appearance,profileChange,foreground);
   if(request.Action=="brightness"&&adjustableBrightness&&request.Brightness is BrightnessChange change&&request.Appearance==null&&request.Port==null)return FinishBrightness(ChangeBrightness(change,foreground),change.Original.ProfileSelected,true);
   if(request.Brightness!=null)return new(false,"request_not_allowed");
   if(request.Action=="return_current"&&request.Port==null&&request.Appearance==null){
    profiles.Flush(true);
    // Internal Back action: there is deliberately no caller-selected port.
    // Read around inventory work and refuse a CEC/source transition. This
    // selects only the still-current HDMI source; never restores a cached one.
    var first=device.ReadSourceContext();
    if(first.Source<13||first.Source>16||first.SourceTransition)return new(false,"source_transition");
    if(!RefreshSources().Any(p=>p.Source==first.Source&&p.CanSelect))return new(false,"connection_unverified");
    var fresh=device.ReadSourceContext();
    if(fresh!=first||fresh.SourceTransition||foreground.IsCancellationRequested)return new(false,"foreground_or_source_changed");
    int code=device.ConnectHdmi(fresh.Source);sourceAccepted=code==1;var after=device.ReadSourceContext();
    return new(sourceAccepted&&after==fresh&&!after.SourceTransition,"current_source_return_readback",SourceRequestAccepted:sourceAccepted);
   }
   if(request.Action=="hdmi"&&request.Port is int port&&request.Appearance==null&&port>=1&&port<=4){
    profiles.Flush(true);
    if(!RefreshSources().Any(p=>p.Port==port&&p.CanSelect))return new(false,"connection_unverified");
    if(adjustableBrightness&&profiles.HasChoice){
     var source=device.ReadSourceContext();
     if(source.Source!=port+12&&!source.SourceTransition){
      // Carry either the ongoing explicit card request, or a currently
      // applied profile. A stored but unapplied choice must not override a
      // manual/external change merely because another card was selected.
      if(following!=null&&profiles.Matches(following))inputBrightness=profiles.FollowChoice(port+12);
      else{
       var before=ReadPicture();
       if(BrightnessPolicy.Eligible(before)&&BrightnessPolicy.Fresh(before,now())&&before.Source==source.Source&&before.ProfileSelected!=null)inputBrightness=profiles.FollowChoice(port+12);
      }
     }
    }
    if(foreground.IsCancellationRequested)return new(false,"foreground_interrupted");
    int code=device.ConnectHdmi(port+12);sourceAccepted=code==1;
    // Source acceptance is not picture readiness. Publish it immediately so
    // the UI can relinquish its window before any destination settings reads.
    if(sourceAccepted){following=inputBrightness;observation.ResetCandidate();}
    return new(false,sourceAccepted?"source_request_accepted":"source_request_refused",SourceRequestAccepted:sourceAccepted,InputBrightness:sourceAccepted?inputBrightness:null);
   }
   return new(false,"request_not_allowed");
  }catch{return new(false,"device_operation_unverified",SourceRequestAccepted:sourceAccepted,InputBrightness:sourceAccepted?inputBrightness:null);}finally{if(foreground.IsCancellationRequested)profiles.Flush(true);Volatile.Write(ref busy,0);}
 }
 internal ControlResult FollowInputBrightness(InputBrightnessPlan plan,CancellationToken cancellation,Action<int>? wait=null){
  try{
   if(!adjustableBrightness||plan.Source is <13 or >16||!BrightnessPolicy.InRange(plan.Value)||!profiles.Matches(plan))return new(false,"input_profile_changed");
   var settling=new InputBrightnessSettling(plan.Source,now());
   for(int sample=0;sample<InputBrightnessSettling.MaximumSamples&&!settling.Expired(now());sample++){
    lock(deviceGate){
     if(cancellation.IsCancellationRequested)return new(false,"input_profile_cancelled");
     if(!ReferenceEquals(following,plan)||!profiles.Matches(plan))return new(false,"input_profile_changed");
     var state=device.ReadPicture();
     if(settling.LeftDestination(state))return new(false,"input_destination_changed");
     bool signalReady=device.CanFollowBrightness(state);
     if(!signalReady)settling.Invalidate();
     if(signalReady&&settling.Ready(state,now())){
      if(!RefreshSources().Any(p=>p.Source==plan.Source&&p.CanSelect))return new(false,"connection_unverified");
      var result=ChangeBrightness(new(state,plan.Value,cancellation),cancellation,requireSignal:true);
      if(!result.Verified)return result; // Never retry an uncertain native write.
      var confirmed=FinishBrightness(result,plan.Profile,false);profiles.Flush(true);return confirmed;
     }
    }
    // Never reserve the native-operation lock during a settling delay. Home
    // can refresh and a newer explicit action can cancel before the next write.
    int delay=settling.NextWait(now());if(wait!=null)wait(delay);else cancellation.WaitHandle.WaitOne(delay);
   }
   if(cancellation.IsCancellationRequested)return new(false,"input_profile_cancelled");
   return new(false,"input_profile_unsettled");
  }catch{return new(false,"input_profile_unverified");}finally{lock(deviceGate){if(ReferenceEquals(following,plan)){following=null;observation.ResetCandidate();}}}
 }
 ControlResult ChangeAppearance(Appearance requested,BrightnessChange change,CancellationToken foreground){
  if(requested is not (Appearance.Day or Appearance.Night)||!BrightnessPolicy.Eligible(change.Original)||change.Value!=profiles.Target(change.Original,requested))return new(false,"profile_not_allowed");
  return FinishBrightness(ChangeBrightness(change,foreground),requested,false);
 }
 ControlResult FinishBrightness(ControlResult result,Appearance? selected,bool editLevel){
  if(result.State==null)return result;
  bool remembered=true;
  if(result.Verified&&selected is Appearance profile)remembered=profiles.Remember(result.State,profile,editLevel);
  else if(result.Verified&&editLevel)profiles.ClearChoice(result.State);
  if(result.Verified)observation.Accept(result.State);
  return result with{State=profiles.Describe(result.State),Status=remembered?result.Status:"profile_save_unavailable"};
 }
 ControlResult ChangeScope(PictureScopeChange change,CancellationToken foreground){
  if(foreground.IsCancellationRequested||change.Cancellation.IsCancellationRequested||!BrightnessPolicy.ScopeEligible(change.Original)||change.Target is not (PictureScope.CurrentSource or PictureScope.AllSources))return new(false,"scope_not_allowed");
  var first=device.ReadPicture();
  if(!BrightnessPolicy.ScopeEligible(first)||!BrightnessPolicy.SameContext(change.Original,first)||!BrightnessPolicy.Fresh(first,now()))return new(false,"context_changed",first);
  if(first.Scope==change.Target)return new(true,"already_selected",first);
  var fresh=device.ReadPicture();
  if(!BrightnessPolicy.ScopeEligible(fresh)||!BrightnessPolicy.SameContext(first,fresh)||!BrightnessPolicy.Fresh(fresh,now()))return new(false,"context_changed",fresh);
  if(foreground.IsCancellationRequested||change.Cancellation.IsCancellationRequested)return new(false,"brightness_interrupted",fresh);
  bool returned=device.SetPictureScope(change.Target);
  var after=device.ReadPicture();
  bool verified=returned&&BrightnessPolicy.Eligible(after)&&after.Source==first.Source&&after.Mode==first.Mode&&after.Scope==change.Target&&BrightnessPolicy.Fresh(after,now());
  if(verified)observation.Accept(after);
  return new(verified,verified?"scope_readback_verified":"scope_readback_unverified",profiles.Describe(after));
 }
 ControlResult ChangeBrightness(BrightnessChange change,CancellationToken foreground,bool requireSignal=false){
  if(foreground.IsCancellationRequested||change.Cancellation.IsCancellationRequested)return new(false,"brightness_interrupted");
  if(!BrightnessPolicy.InRange(change.Value)||!BrightnessPolicy.Eligible(change.Original))return new(false,"brightness_not_allowed");
  var first=device.ReadPicture();
  if(!BrightnessPolicy.SameContext(change.Original,first)||!BrightnessPolicy.Fresh(first,now()))return new(false,"context_changed",first);
  if(requireSignal&&!device.CanFollowBrightness(first))return new(false,"input_signal_unready",first);
  if(first.Brightness==change.Value)return new(true,"already_selected",first);
  if(!device.HasBrightnessRange())return new(false,"brightness_range_unverified",first);
  var fresh=device.ReadPicture();
  if(!BrightnessPolicy.SameContext(first,fresh)||!BrightnessPolicy.Fresh(fresh,now()))return new(false,"context_changed",fresh);
  // The live editor holds at most one latest target, not a queue of repeats.
  // An already executing native setter cannot be cancelled or made atomic
  // with a CEC transition. Stop unsent work when the editor is interrupted.
  if(foreground.IsCancellationRequested||change.Cancellation.IsCancellationRequested)return new(false,"brightness_interrupted",fresh);
  if(requireSignal&&!device.CanFollowBrightness(fresh))return new(false,"input_signal_unready",fresh);
  if(foreground.IsCancellationRequested||change.Cancellation.IsCancellationRequested)return new(false,"brightness_interrupted",fresh);
  bool returned=device.SetBrightness(change.Value);
  var after=device.ReadPicture();
  // Retry only reads of the same coherent context. The setter runs once;
  // delayed acknowledgement cannot trigger duplicate native writes.
  for(int attempt=0;returned&&attempt<3&&BrightnessPolicy.SameIdentity(first,after)&&after.Brightness!=change.Value&&!foreground.IsCancellationRequested&&!change.Cancellation.IsCancellationRequested;attempt++){
   // Foreground/editor cancellation sources may already have been disposed by
   // a fast reopen. Inspect tokens, never acquire their disposed wait handles.
   Thread.Sleep(60);if(foreground.IsCancellationRequested||change.Cancellation.IsCancellationRequested)break;
   after=device.ReadPicture();
  }
  bool verified=returned&&BrightnessPolicy.SameIdentity(first,after)&&after.Brightness==change.Value&&BrightnessPolicy.Fresh(after,now());
  return new(verified,verified?"brightness_readback_verified":"brightness_readback_unverified",after);
 }
}
