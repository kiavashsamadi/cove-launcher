using System;
using System.Collections.Generic;
using Tizen.NUI;
using Tizen.NUI.BaseComponents;
using Cove.Launcher;

internal sealed partial class NeutralWindow {
 readonly BrightnessEditor brightnessEditor=new();
 readonly List<View> brightnessPanel=new();
 TextLabel? brightnessButtonLabel,brightnessValue,brightnessTitle,scopeReadOnly;bool profileSavePending;
 readonly List<View> scopeButtons=new();readonly List<TextLabel> scopeLabels=new();bool scopeFocused;int scopeChoice;
 View? brightnessFill,brightnessThumb,brightnessSlider,scopeGroup;
 int[] UtilityOrder=>AudioVisible?new[]{4,3,0,1,2}:new[]{3,0,1,2};
 int MoveUtility(int direction){var order=UtilityOrder;int i=Array.IndexOf(order,selected);return order[Math.Clamp(i+direction,0,order.Length-1)];}
 void CreateBrightness(){
  var button=Add(SurfaceBox(1168,78,226,68));button.BackgroundColor=new Color(0,0,0,0);button.Focusable=true;button.AccessibilityRole=Role.PushButton;button.AccessibilityHighlightable=true;button.AccessibilityName="Display brightness";utilityCards.Add(button);
  brightnessButtonLabel=Add(Label("Brightness",1180,78,202,68,18));utilityNames.Add(brightnessButtonLabel);
  var panel=Add(SurfaceBox(1168,168,608,212));panel.BackgroundColor=new Color(.067f,.090f,.129f,1);panel.BorderlineWidth=1;panel.BorderlineColor=new Color(.30f,.39f,.50f,.65f);panel.AccessibilityHidden=true;brightnessPanel.Add(panel);
  brightnessTitle=Add(Label("Brightness",1200,190,370,44,26));brightnessTitle.HorizontalAlignment=HorizontalAlignment.Begin;brightnessPanel.Add(brightnessTitle);
  brightnessValue=Add(Label("",1654,184,90,52,32));brightnessValue.HorizontalAlignment=HorizontalAlignment.End;brightnessPanel.Add(brightnessValue);
  brightnessSlider=Add(new View{Position2D=new Position2D(1200,252),Size2D=new Size2D(544,42),Focusable=false,AccessibilityRole=Role.Slider,AccessibilityHighlightable=true,AccessibilityName="Brightness",AccessibilityDescription="Left and Right adjust live. Select or Back closes and keeps the value."});brightnessPanel.Add(brightnessSlider);
  var track=Add(SurfaceBox(1208,269,528,6));track.BackgroundColor=new Color(.20f,.26f,.34f,1);track.CornerRadius=new Vector4(3,3,3,3);brightnessPanel.Add(track);
  brightnessFill=Add(SurfaceBox(1208,269,528,6));brightnessFill.BackgroundColor=new Color(.76f,.82f,.89f,1);brightnessFill.CornerRadius=new Vector4(3,3,3,3);brightnessPanel.Add(brightnessFill);
  brightnessThumb=Add(SurfaceBox(1726,262,20,20));brightnessThumb.BackgroundColor=Paper();brightnessThumb.CornerRadius=new Vector4(10,10,10,10);brightnessPanel.Add(brightnessThumb);
  scopeGroup=Add(SurfaceBox(1200,312,544,44));scopeGroup.BackgroundColor=new Color(1,1,1,.035f);scopeGroup.CornerRadius=new Vector4(12,12,12,12);brightnessPanel.Add(scopeGroup);
  for(int i=0;i<2;i++){
   var option=Add(SurfaceBox(1202+i*272,314,268,40));option.CornerRadius=new Vector4(10,10,10,10);option.AccessibilityRole=Role.PushButton;option.AccessibilityHighlightable=true;option.AccessibilityName=i==0?"Current source":"All sources";scopeButtons.Add(option);brightnessPanel.Add(option);
   var label=Add(Label(i==0?"Current source":"All sources",1202+i*272,314,268,40,18));scopeLabels.Add(label);brightnessPanel.Add(label);
  }
  scopeReadOnly=Add(Label("",1200,312,544,44,18));scopeReadOnly.TextColor=Muted();brightnessPanel.Add(scopeReadOnly);
  DrawBrightness();
 }
 void DrawBrightness(){
  bool open=brightnessEditor.IsOpen,available=BrightnessPolicy.Eligible(state.Picture);
  foreach(var view in brightnessPanel){view.Opacity=open?1:0;view.AccessibilityHidden=!open;}
  bool canChangeScope=open&&BrightnessPolicy.ScopeEligible(brightnessEditor.Original);
  if(scopeGroup!=null){scopeGroup.Opacity=canChangeScope?1:0;scopeGroup.AccessibilityHidden=true;}
  foreach(var option in scopeButtons)option.Focusable=canChangeScope;
  if(!canChangeScope)scopeFocused=false;
  if(brightnessSlider!=null)brightnessSlider.Focusable=open;
  if(brightnessButtonLabel==null)return;
  // The outgoing Back frame is already frozen. A new frame must not reuse a
  // number from another source, mode, or scope while its reading is pending.
  brightnessButtonLabel.Text=available?"Brightness  "+state.Picture!.Brightness:state.PicturePending?"Brightness  …":"Brightness";
  brightnessButtonLabel.Opacity=available?1:.38f;
  var button=utilityCards[3];button.BorderlineWidth=focusRow==1&&selected==3?2:1;button.BorderlineColor=focusRow==1&&selected==3?new Color(.765f,.824f,.886f,1):new Color(1,1,1,.043f);
  button.AccessibilityDescription=available?"Adjust brightness live. "+(state.Picture!.ProfileSelected is Appearance a?$"Updates your {Presentation.ProfileName(a)} level. ":"")+BrightnessPolicy.ScopeLabel(state.Picture.Scope):state.PicturePending?"Checking picture settings; adjustment unavailable":"Brightness is unavailable for the current picture";
  if(!open)return;
  int value=brightnessEditor.Value,width=(int)Math.Round(528*value/50.0);
  brightnessTitle!.Text=brightnessEditor.Original!.ProfileSelected is Appearance profile?Presentation.ProfileName(profile)+" level":"Brightness";
  brightnessValue!.Text=value.ToString();brightnessSlider!.AccessibilityName=brightnessTitle.Text+", "+value+" of 50, "+BrightnessPolicy.ScopeLabel(brightnessEditor.Original!.Scope);
  for(int i=0;i<2;i++){
   bool active=brightnessEditor.Original.Scope==(i==0?PictureScope.CurrentSource:PictureScope.AllSources),focused=scopeFocused&&scopeChoice==i;
   scopeButtons[i].BackgroundColor=active?new Color(.220f,.282f,.365f,.65f):new Color(0,0,0,0);scopeButtons[i].BorderlineWidth=focused?2:0;scopeButtons[i].BorderlineColor=new Color(.765f,.824f,.886f,1);scopeLabels[i].TextColor=active?Paper():Muted();scopeLabels[i].Opacity=brightnessEditor.Original.ScopeAvailable?1:.45f;
   scopeButtons[i].AccessibilityDescription=(active?"Selected. ":"")+"Samsung Apply Picture Settings. "+(i==0?"Apply to this source.":"Apply across sources; affects more than brightness.");
   scopeButtons[i].Opacity=scopeLabels[i].Opacity=canChangeScope?1:0;scopeButtons[i].AccessibilityHidden=scopeLabels[i].AccessibilityHidden=!canChangeScope;
  }
  scopeReadOnly!.Text=BrightnessPolicy.ScopeLabel(brightnessEditor.Original.Scope);scopeReadOnly.Opacity=canChangeScope?0:1;scopeReadOnly.AccessibilityHidden=canChangeScope;
  Place(brightnessFill!,1208,269,Math.Max(1,width),6);brightnessFill!.Opacity=value==0?0:1;
  Place(brightnessThumb!,1198+width,262,20,20);
 }
 bool HandleBrightnessKey(string key,bool select,bool back){
  if(!brightnessEditor.IsOpen)return false;
  if(back){brightnessEditor.Close();PumpBrightness();Draw();return true;}
  if(brightnessEditor.ChangingScope||brightnessEditor.Closing)return true;
  if(key=="Up"||key=="ArrowUp")scopeFocused=false;
  else if(key=="Down"||key=="ArrowDown")scopeFocused=BrightnessPolicy.ScopeEligible(brightnessEditor.Original);
  else if(key=="Left"||key=="ArrowLeft"){if(scopeFocused)scopeChoice=Math.Max(0,scopeChoice-1);else brightnessEditor.Move(-1);}
  else if(key=="Right"||key=="ArrowRight"){if(scopeFocused)scopeChoice=Math.Min(1,scopeChoice+1);else brightnessEditor.Move(1);}
  else if(select){if(scopeFocused)ChangePictureScope();else brightnessEditor.Close();}
  // Update only the slider primitives. Remote repeats do not redraw the hero,
  // start animations or timers. Pump sends at most one guarded write at a time.
  DrawBrightness();FocusSelected();PumpBrightness();return true;
 }
 void ChangePictureScope(){
  if(!BrightnessPolicy.ScopeEligible(brightnessEditor.Original)){Notify("Picture settings scope is unavailable here.");return;}
  if(pending!=null||actionInFlight||System.Threading.Volatile.Read(ref workerBusy)!=0){Notify("Please wait for the current adjustment.");return;}
  if(requestId==int.MaxValue){Notify("Please close and reopen the launcher.");return;}
  var target=scopeChoice==0?PictureScope.CurrentSource:PictureScope.AllSources;
  if(brightnessEditor.Original?.Scope==target)return;
  var change=brightnessEditor.BeginScope(target,Now());if(change==null){Notify("Please wait for the current adjustment.");return;}
  if(QueueAction(new(++requestId,"picture_scope",null,null,null,change)))actionInFlight=true;
  else brightnessEditor.ReleaseUnsent(change);
 }
 void PumpBrightness(){
  if(stopping||!foreground.Active||pending!=null||actionInFlight||System.Threading.Volatile.Read(ref workerBusy)!=0)return;
  if(requestId==int.MaxValue){brightnessEditor.Cancel();Notify("Please close and reopen the launcher.");DrawBrightness();return;}
  if(profileSavePending&&!brightnessEditor.IsOpen){if(QueueAction(new(++requestId,"profiles_save",null,null))){profileSavePending=false;actionInFlight=true;}return;}
  var change=brightnessEditor.Begin(Now());if(change==null)return;
  if(QueueAction(new(++requestId,"brightness",null,null,change)))actionInFlight=true;
  else brightnessEditor.ReleaseUnsent(change);
 }
 void OpenBrightness(){
  if(pending!=null||actionInFlight){Notify("Please wait for the current change.");return;}
  if(!brightnessEditor.Open(state.Picture)){Notify(state.Picture?.Scope==PictureScope.Unknown?"Picture settings scope is unavailable. Try again.":"Brightness is unavailable for the current picture.");return;}
  scopeFocused=false;scopeChoice=state.Picture!.Scope==PictureScope.CurrentSource?0:1;CancelHeroFade();Draw();
 }
}
