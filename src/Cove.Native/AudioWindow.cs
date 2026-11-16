using System;
using System.Linq;
using System.Threading;
using Tizen.NUI;
using Tizen.NUI.BaseComponents;
using Cove.Launcher;

internal sealed partial class NeutralWindow {
 SourceMonitor? sourceMonitor;SourceSnapshot? currentInventory,lastAppliedInventory;long inventoryRequested;
 readonly System.Collections.Generic.List<View> audioViews=new();TextLabel? audioName,audioConnection;
 bool AudioVisible=>currentInventory?.Audio.Length>0;
 void CreateAudio(){
  var button=Add(SurfaceBox(870,78,278,68));button.CornerRadius=new Vector4(17,17,17,17);button.BackgroundColor=new Color(1,1,1,.012f);button.AccessibilityRole=Role.PushButton;button.AccessibilityHighlightable=true;utilityCards.Add(button);audioViews.Add(button);
  var symbol=Add(SurfaceBox(892,105,42,14));symbol.BackgroundColor=new Color(0,0,0,0);symbol.CornerRadius=new Vector4(7,7,7,7);symbol.BorderlineWidth=1.5f;symbol.BorderlineColor=new Color(.706f,.757f,.820f,1);symbol.AccessibilityHidden=true;audioViews.Add(symbol);
  foreach(int x in new[]{899,903,907,919,923,927}){var line=Add(SurfaceBox(x,110,1,4));line.BackgroundColor=new Color(.706f,.757f,.820f,.6f);line.AccessibilityHidden=true;audioViews.Add(line);}
  audioName=Add(Label("",952,79,176,37,22));audioName.HorizontalAlignment=HorizontalAlignment.Begin;audioViews.Add(audioName);
  audioConnection=Add(Label("",952,109,176,30,17));audioConnection.TextColor=new Color(.608f,.667f,.745f,1);audioConnection.HorizontalAlignment=HorizontalAlignment.Begin;audioViews.Add(audioConnection);
 }
 void DrawAudio(){
  if(audioName==null)return;bool visible=AudioVisible;
  foreach(var view in audioViews)view.Opacity=visible?1:0;
  var button=utilityCards[4];button.Focusable=visible;button.AccessibilityHidden=!visible;
  if(!visible)return;
  var devices=currentInventory!.Audio;var audio=devices[0];
  audioName.Text=devices.Length==1?(audio.Label==$"HDMI {audio.Port}"?"Sound system":audio.Label):"Sound settings";
  audioConnection!.Text=devices.Length==1?$"HDMI {audio.Port}"+(currentInventory.AudioReturnChannel=="eARC"?" · eARC":""):$"{devices.Length} connected";
  button.AccessibilityName="Sound settings, "+audioName.Text+", "+audioConnection.Text;
  button.AccessibilityDescription="Open Samsung Sound settings";
  bool focused=focusRow==1&&selected==4;button.BorderlineWidth=focused?2:1;button.BorderlineColor=focused?new Color(.765f,.824f,.886f,1):new Color(1,1,1,.043f);
 }
 void ApplyInventory(){
  var next=sourceMonitor?.Latest;if(next==null||ReferenceEquals(next,lastAppliedInventory))return;
  bool redraw=currentInventory==null||!state.Ports.SequenceEqual(next.Video)||!currentInventory.Audio.SequenceEqual(next.Audio)||currentInventory.AudioReturnChannel!=next.AudioReturnChannel||currentInventory.Verified!=next.Verified;
  int input=Presentation.KeepPort(state.Ports,next.Video,focusRow==0?selected:previousInput);
  currentInventory=lastAppliedInventory=next;inventoryObserved=true;state=state with{Ports=next.Video};previousInput=input;
  if(focusRow==0)selected=input;
  if(!AudioVisible&&focusRow==1&&selected==4)selected=3;
  if(state.Ports.Length==0&&focusRow==0){focusRow=1;selected=AudioVisible?4:2;}
  if(next.Verified&&state.Picture!=null&&!next.Video.Any(p=>p.Source==state.Picture.Source))state=state with{Picture=null,PicturePending=false};
  if(next.Verified&&pending?.Action=="hdmi"&&!next.Video.Any(p=>p.Port==pending.Port)){pending=null;actionInFlight=false;Volatile.Write(ref inputSelectionPending,0);Notify("Input disconnected.");}
  if(redraw)Draw();
 }
}
