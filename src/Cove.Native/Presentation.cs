using System;
using System.Linq;
using Cove.Launcher;

// Pure presentation decisions: no native APIs or TV configuration setters.
internal static class Presentation {
 internal static bool CompletedDisplay(bool created,bool stopping,bool assetsReady,string reason)=>created&&stopping&&(assetsReady||reason=="remote_exit"||reason=="hdmi_selected"||reason=="background_memory_pressure"||reason=="system_termination");
 internal static bool SamePicture(DeviceSnapshot? a,DeviceSnapshot? b)=>ReferenceEquals(a,b)||a!=null&&b!=null&&a.Source==b.Source&&a.Mode==b.Mode&&a.Brightness==b.Brightness&&a.SourceTransition==b.SourceTransition&&a.Scope==b.Scope&&a.BrightnessAvailable==b.BrightnessAvailable&&a.ScopeAvailable==b.ScopeAvailable&&a.DayBrightness==b.DayBrightness&&a.NightBrightness==b.NightBrightness&&a.ProfileSelected==b.ProfileSelected&&a.AvailableModes.SetEquals(b.AvailableModes);
 internal static string Name(PortState port)=>string.IsNullOrWhiteSpace(port.Label)?$"HDMI {port.Port}":port.Label;
 internal static int Icon(PortState port){
  string name=Name(port).Trim().ToLowerInvariant();
  if(name.Contains("apple tv")||name.Contains("appletv"))return 1;
  if(name.Contains("playstation 5")||name=="ps5"||name.StartsWith("ps5 ")||name.EndsWith(" ps5"))return 2;
  if(name is "switch" or "switch 2" or "switch oled" or "switch lite"||HasNamedDevice(name,"nintendo switch")||HasNamedDevice(name,"nintendoswitch"))return 3;
  if(name.Contains("xbox"))return 4;
  if(name=="pc"||name.StartsWith("pc ")||name.EndsWith(" pc")||name.Contains("computer")||name.Contains("laptop")||name.Contains("desktop"))return 5;
  if(name.Contains("blu-ray")||name.Contains("bluray")||name.Contains("blu ray")||name.Contains("dvd")||name.Contains("disc player"))return 6;
  if(name.Contains("playstation")||name=="ps4"||name.StartsWith("ps4 ")||name.Contains("nintendo")||name.Contains("wii")||name.Contains("console"))return 7;
  return 0; // Product artwork comes only from the reported name, never a port guess.
 }
 // A bare Switch nickname is valid; HDMI switches and splitters are not consoles.
 static bool HasNamedDevice(string name,string token)=>name==token||name.StartsWith(token+" ")||name.EndsWith(" "+token)||name.Contains(" "+token+" ");
 internal static string ProfileName(Appearance profile)=>profile switch{Appearance.Day=>"Bright",Appearance.Night=>"Dim",_=>throw new ArgumentOutOfRangeException(nameof(profile))};
 internal static string? AppearanceOf(DeviceSnapshot? state)=>BrightnessPolicy.Eligible(state)?state!.ProfileSelected switch{Appearance.Day=>"day",Appearance.Night=>"night",_=>null}:null;
 internal static bool PresetAvailable(DeviceSnapshot? state,Appearance requested)=>requested is Appearance.Day or Appearance.Night&&BrightnessPolicy.Eligible(state);
 internal static int KeepPort(PortState[] oldPorts,PortState[] newPorts,int previous){
  if(newPorts.Length==0)return 0;
  int physical=oldPorts.Length==0?0:oldPorts[Math.Clamp(previous,0,oldPorts.Length-1)].Port;
  int same=Array.FindIndex(newPorts,p=>p.Port==physical);
  return same>=0?same:Math.Clamp(previous,0,newPorts.Length-1);
 }
 internal static string Failure(string? status)=>status switch{
  "connection_unverified"=>"That input is no longer available.",
  "source_transition" or "context_changed"=>"The input changed. Please try again.",
  "brightness_not_allowed" or "scope_not_allowed"=>"This adjustment is unavailable for the current picture.",
  "profile_save_unavailable"=>"Brightness applied; the profile could not be saved.",
  "profile_not_allowed"=>"The brightness profile changed. Please try again.",
  _=>"The change could not be confirmed. Please try again."};
}

// Native Settings may depend on the caller remaining alive. Keep the launcher
// paused, without polling or raising its window, until the OS resumes it.
internal sealed class SettingsHandoff {
 enum Phase { Idle,Requested,Background }
 Phase phase;
 internal bool IsBackground=>phase==Phase.Background;
 internal void Request()=>phase=Phase.Requested;
 internal void Cancel()=>phase=Phase.Idle;
 internal bool Pause(){if(phase==Phase.Idle)return false;phase=Phase.Background;return true;}
 internal bool Resume(){if(phase!=Phase.Background)return false;phase=Phase.Idle;return true;}
}
