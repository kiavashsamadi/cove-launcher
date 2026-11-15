using System;
using System.Collections.Generic;
using System.IO;
using System.Text.Json;
namespace Cove.Launcher;
internal static class ProfileChecks {
 internal static int Run(){
  int count=0;void Check(bool value){count++;if(!value)throw new Exception("profile_check_"+count);}
  DeviceSnapshot State(int source=13,string mode="655360",int value=50,PictureScope scope=PictureScope.CurrentSource)=>new(source,mode,value,new HashSet<string>(),100,false,scope,true,true);
  var profiles=new BrightnessProfiles();
  foreach(int source in new[]{13,14,15,16})foreach(string mode in new[]{"655360","655361","65538","393217","65547","393222","393225","458769"}){
   var initial=profiles.Describe(State(source,mode));Check(initial.DayBrightness==50&&initial.NightBrightness==0&&initial.ProfileSelected==null);
   foreach(var profile in new[]{Appearance.Day,Appearance.Night}){
    int target=profile==Appearance.Day?50:0;var first=State(source,mode,value:23);var fake=new Fake();fake.Reads.Enqueue(first);fake.Reads.Enqueue(first);fake.Reads.Enqueue(first with{Brightness=target});
    var adapter=new ControlAdapter(fake,()=>100,true,profiles);var result=adapter.Execute(new(1,"appearance",null,profile,new(first,target)));
    Check(result.Verified&&fake.Writes.Count==1&&fake.Writes[0]==target&&result.State!.Mode==mode&&result.State.Source==source&&result.State.ProfileSelected==profile);
   }
  }
  var day=profiles.Describe(State());Check(profiles.Remember(day with{Brightness=36},Appearance.Day,true));
  Check(profiles.Describe(State(value:36)).ProfileSelected==Appearance.Day);Check(profiles.Target(State(),Appearance.Day)==36);
  Check(profiles.Target(State(source:14),Appearance.Day)==36);Check(profiles.Target(State(mode:"655361"),Appearance.Day)==36);
  Check(profiles.Target(State(scope:PictureScope.AllSources),Appearance.Day)==36);
  Check(profiles.Describe(State(value:17)).ProfileSelected==null);Check(profiles.Target(State(),Appearance.Day)==36);
  var edit=profiles.Describe(State(value:36));var f=new Fake();f.Reads.Enqueue(edit);f.Reads.Enqueue(edit);f.Reads.Enqueue(edit with{Brightness=35});
  var a=new ControlAdapter(f,()=>100,true,profiles);var edited=a.Execute(new(1,"brightness",null,null,new(edit,35)));
  Check(edited.Verified&&edited.State!.DayBrightness==35&&edited.State.ProfileSelected==Appearance.Day&&edited.State.Mode==edit.Mode);
  Check(profiles.Target(State(),Appearance.Night)==0);
  f=new();f.Reads.Enqueue(State(value:17));f.Reads.Enqueue(State(value:17));f.Reads.Enqueue(State(value:18));
  Check(new ControlAdapter(f,()=>100,true,profiles).Execute(new(1,"brightness",null,null,new(State(value:17),18))).Verified);
  Check(profiles.Target(State(),Appearance.Day)==35);
  profiles.Remember(State(scope:PictureScope.AllSources,value:44),Appearance.Day,true);
  Check(profiles.Target(State(source:16,scope:PictureScope.AllSources),Appearance.Day)==44);
  Check(profiles.Target(State(source:16),Appearance.Day)==44);
  profiles.Remember(State(value:44),Appearance.Night,true);Check(profiles.Describe(State(value:44)).ProfileSelected==Appearance.Night);
  foreach(int source in new[]{13,14,15,16})foreach(string mode in new[]{"655360","655361","458769"})foreach(var scope in new[]{PictureScope.CurrentSource,PictureScope.AllSources}){
   Check(profiles.Target(State(source,mode,scope:scope),Appearance.Day)==44&&profiles.Target(State(source,mode,scope:scope),Appearance.Night)==44);
  }
  foreach(var changed in new[]{State(source:14),State(mode:"655361"),State(value:49),State(scope:PictureScope.AllSources),State() with{SourceTransition=true},State() with{BrightnessAvailable=false},State() with{ObservedAt=-151}}){
   f=new();f.Reads.Enqueue(State());f.Reads.Enqueue(changed);
   var freshProfiles=new BrightnessProfiles();var result=new ControlAdapter(f,()=>100,true,freshProfiles).Execute(new(1,"appearance",null,Appearance.Night,new(State(),0)));
   Check(!result.Verified&&f.Writes.Count==0&&freshProfiles.Target(State(),Appearance.Night)==0);
  }
  f=new();Check(!new ControlAdapter(f,()=>100,true).Execute(new(1,"appearance",null,Appearance.Night)).Verified&&f.Writes.Count==0);
  f=new();Check(!new ControlAdapter(f,()=>100,true).Execute(new(1,"appearance",null,Appearance.Night,new(State(),11))).Verified&&f.Writes.Count==0);
  f=new();var disabled=State() with{ScopeAvailable=false};f.Reads.Enqueue(disabled);
  Check(!new ControlAdapter(f,()=>100,true).Execute(new(1,"picture_scope",null,null,null,new(disabled,PictureScope.AllSources))).Verified&&f.Writes.Count==0);
  foreach(var invalid in new[]{State(source:12),State(source:17),State(mode:""),State(mode:"0655360"),State(mode:"0"),State() with{BrightnessAvailable=false}})Check(!BrightnessPolicy.Eligible(invalid));
  string directory=Path.Combine(Path.GetTempPath(),"cove-profiles-"+Guid.NewGuid().ToString("N"));Directory.CreateDirectory(directory);string path=Path.Combine(directory,"profiles.json"),legacy=Path.Combine(directory,"legacy.json");
  try{
   long clock=0;var store=new BrightnessProfiles(path,()=>clock);store.Describe(State());Check(!File.Exists(path));
   store.Remember(State(value:42),Appearance.Day,true);Check(store.Flush()&&!File.Exists(path));clock=750;Check(store.Flush()&&File.Exists(path));
   var reloaded=new BrightnessProfiles(path);Check(reloaded.Describe(State(value:42)).ProfileSelected==Appearance.Day&&reloaded.Target(State(),Appearance.Day)==42);
   store.Remember(State(value:3),Appearance.Night,true);Check(store.Flush(true));Check(new BrightnessProfiles(path).Target(State(source:14,mode:"458769",scope:PictureScope.AllSources),Appearance.Night)==3);
   File.Delete(path);string original=JsonSerializer.Serialize(new{version=1,profiles=new[]{new BrightnessProfile(13,"655360",PictureScope.CurrentSource,42,3),new BrightnessProfile(0,"458769",PictureScope.AllSources,42,3)}});File.WriteAllText(legacy,original);
   var migrated=new BrightnessProfiles(path,legacyPath:legacy);Check(migrated.Target(State(source:16),Appearance.Night)==3&&!File.Exists(path));migrated.Remember(State(value:42),Appearance.Day,false);Check(migrated.Flush(true)&&File.ReadAllText(legacy)==original);
   Check(new BrightnessProfiles(path,legacyPath:legacy).Target(State(source:14,mode:"458769"),Appearance.Day)==42);
   File.Delete(path);File.WriteAllText(legacy,JsonSerializer.Serialize(new{version=1,profiles=new[]{new BrightnessProfile(13,"655360",PictureScope.CurrentSource,41,2),new BrightnessProfile(14,"458769",PictureScope.CurrentSource,40,4)}}));
   var activeMigration=new BrightnessProfiles(path,legacyPath:legacy);Check(activeMigration.Target(State(source:14,mode:"458769"),Appearance.Night)==4&&activeMigration.Target(State(),Appearance.Day)==40);
   var ambiguous=new BrightnessProfiles(path,legacyPath:legacy);Check(ambiguous.Target(State(source:16),Appearance.Day)==50&&ambiguous.SaveFailed);ambiguous.Remember(State(value:20),Appearance.Day,true);Check(!ambiguous.Flush(true)&&!File.Exists(path));
   File.WriteAllText(path,"broken");var broken=new BrightnessProfiles(path);Check(broken.Target(State(),Appearance.Day)==50);broken.Remember(State(value:31),Appearance.Day,true);Check(!broken.Flush(true)&&File.ReadAllText(path)=="broken");
   File.WriteAllText(path,JsonSerializer.Serialize(new{version=2,day=51,night=0,selected=(int?)null}));
   var invalidStore=new BrightnessProfiles(path);Check(invalidStore.Target(State(),Appearance.Day)==50&&invalidStore.SaveFailed);
   File.WriteAllText(path,new string('x',65537));var tooLarge=new BrightnessProfiles(path);Check(tooLarge.Target(State(),Appearance.Day)==50&&tooLarge.SaveFailed);
  }finally{foreach(string file in new[]{path,path+".pending",legacy})if(File.Exists(file))File.Delete(file);Directory.Delete(directory);}
  return count;
 }
 sealed class Fake:IDevice {
  internal readonly Queue<DeviceSnapshot> Reads=new();internal readonly List<int> Writes=new();
  public DeviceSnapshot ReadPicture()=>Reads.Dequeue();public string ReadSources()=>throw new Exception("unexpected inventory");
  public bool SetBrightness(int value){Writes.Add(value);return true;}public bool HasBrightnessRange()=>true;
  public bool SetPictureScope(PictureScope scope)=>throw new Exception("unexpected scope write");
  public int ConnectHdmi(int source)=>throw new Exception("unexpected input change");
 }
}
