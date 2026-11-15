using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
namespace Cove.Launcher;
// Read-only compatibility with the first, per-context profile format.
internal sealed record BrightnessProfile(int Source,string Mode,PictureScope Scope,int Day=50,int Night=0,Appearance? Selected=null);
// Shared numbers do not change Samsung's native Apply Picture Settings scope.
internal sealed class BrightnessProfiles {
 const int MaximumBytes=65536;
 readonly object gate=new();readonly string? path,legacyPath;readonly Func<long> now;
 int day=50,night;Appearance? selected;bool loaded,dirty,unreadable,currentFormat;long changedAt;
 internal bool SaveFailed {get;private set;}
 internal bool HasChoice {get{lock(gate)return loaded&&!unreadable&&selected!=null;}}
 internal BrightnessProfiles(string? path=null,Func<long>? clock=null,string? legacyPath=null){this.path=path;this.legacyPath=legacyPath;now=clock??(()=>Environment.TickCount64);}
 static bool ValidSelection(Appearance? value)=>value is null or Appearance.Day or Appearance.Night;
 static bool Valid(BrightnessProfile p)=>(p.Source is >=13 and <=16&&p.Scope==PictureScope.CurrentSource||p.Source==0&&p.Scope==PictureScope.AllSources)&&BrightnessPolicy.ModeIdentity(p.Mode)&&BrightnessPolicy.InRange(p.Day)&&BrightnessPolicy.InRange(p.Night)&&ValidSelection(p.Selected);
 static JsonDocument Read(string file){using var stream=new FileStream(file,FileMode.Open,FileAccess.Read,FileShare.Read);if(stream.Length>MaximumBytes)throw new InvalidDataException();return JsonDocument.Parse(stream,new JsonDocumentOptions{MaxDepth=5});}
 void Load(DeviceSnapshot state){
  if(loaded)return;loaded=true;
  try{
   if(path!=null&&File.Exists(path)){
    using var doc=Read(path);var root=doc.RootElement;
    if(root.GetProperty("version").GetInt32()!=2)throw new InvalidDataException();
    int d=root.GetProperty("day").GetInt32(),n=root.GetProperty("night").GetInt32();
    Appearance? s=root.GetProperty("selected").ValueKind==JsonValueKind.Null?null:(Appearance)root.GetProperty("selected").GetInt32();
    if(!BrightnessPolicy.InRange(d)||!BrightnessPolicy.InRange(n)||!ValidSelection(s))throw new InvalidDataException();
    day=d;night=n;selected=s;currentFormat=true;return;
   }
   if(legacyPath==null||!File.Exists(legacyPath))return;
   using var legacy=Read(legacyPath);var old=legacy.RootElement;
   if(old.GetProperty("version").GetInt32()!=1)throw new InvalidDataException();
   var list=old.GetProperty("profiles");if(list.ValueKind!=JsonValueKind.Array||list.GetArrayLength()>128)throw new InvalidDataException();
   var rows=new List<BrightnessProfile>();var keys=new HashSet<(int,string,PictureScope)>();
   foreach(var row in list.EnumerateArray()){
    var p=JsonSerializer.Deserialize<BrightnessProfile>(row.GetRawText())??throw new InvalidDataException();
    if(!Valid(p)||!keys.Add((p.Source,p.Mode,p.Scope)))throw new InvalidDataException();rows.Add(p);
   }
   if(rows.Count==0)return;
   var chosen=rows.FirstOrDefault(p=>p.Source==(state.Scope==PictureScope.AllSources?0:state.Source)&&p.Mode==state.Mode&&p.Scope==state.Scope);
   // If previous custom pairs differ, retain the first active context's pair.
   // With identical pairs every context is equivalent. Keep ambiguous files.
   if(chosen==null&&rows.Select(p=>(p.Day,p.Night)).Distinct().Count()==1)chosen=rows[0];
   if(chosen==null)throw new InvalidDataException();
   day=chosen.Day;night=chosen.Night;selected=chosen.Selected;
  }catch{unreadable=true;SaveFailed=true;}
 }
 internal DeviceSnapshot Describe(DeviceSnapshot state){lock(gate){
  if(!BrightnessPolicy.Eligible(state))return state with{ProfileSelected=null};
  Load(state);Appearance? active=selected;
  if(active==Appearance.Day&&state.Brightness!=day||active==Appearance.Night&&state.Brightness!=night)active=null;
  return state with{DayBrightness=day,NightBrightness=night,ProfileSelected=active};
 }}
 internal void ClearChoice(DeviceSnapshot state){lock(gate){Load(state);if(selected==null)return;selected=null;dirty=true;changedAt=now();}}
 internal bool Matches(InputBrightnessPlan plan){lock(gate)return !unreadable&&selected==plan.Profile&&(plan.Profile==Appearance.Day?day:night)==plan.Value;}
 internal InputBrightnessPlan? FollowChoice(int source){lock(gate)return loaded&&!unreadable&&selected is Appearance choice?new(source,choice,choice==Appearance.Day?day:night):null;}
 internal int Target(DeviceSnapshot state,Appearance requested){lock(gate){Load(state);return requested==Appearance.Day?day:night;}}
 internal bool Remember(DeviceSnapshot state,Appearance value,bool editLevel){lock(gate){
  if(!BrightnessPolicy.Eligible(state)||value is not (Appearance.Day or Appearance.Night))return false;
  Load(state);int d=editLevel&&value==Appearance.Day?state.Brightness:day,n=editLevel&&value==Appearance.Night?state.Brightness:night;
  if(d==day&&n==night&&selected==value&&currentFormat)return !SaveFailed;
  day=d;night=n;selected=value;dirty=true;changedAt=now();return !unreadable;
 }}
 internal bool Flush(bool force=false){lock(gate){
  if(!dirty||!force&&now()-changedAt<750)return !SaveFailed;
  if(path==null){dirty=false;currentFormat=true;return true;}
  if(unreadable)return false;
  try{
   byte[] data=JsonSerializer.SerializeToUtf8Bytes(new{version=2,day,night,selected});
   using(var file=new FileStream(path+".pending",FileMode.Create,FileAccess.Write,FileShare.None)){file.Write(data);file.Flush(true);}
   File.Move(path+".pending",path,true);dirty=false;currentFormat=true;SaveFailed=false;return true;
  }catch{SaveFailed=true;return false;}
 }}
}
