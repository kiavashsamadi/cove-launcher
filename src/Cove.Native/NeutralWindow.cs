using System;using System.Collections.Concurrent;using System.Collections.Generic;using System.Diagnostics;using System.IO;using System.Linq;using System.Reflection;using System.Text.Json;using System.Threading;using System.Threading.Tasks;
using Tizen.NUI;using Tizen.NUI.BaseComponents;using Cove.Launcher;
internal sealed class NativeArt:IDisposable {
 readonly Stream source;readonly EncodedImageBuffer buffer;readonly ImageUrl url;
 internal NativeArt(string name){source=Assembly.GetExecutingAssembly().GetManifestResourceStream("Cove.art."+name+".png")??Assembly.GetExecutingAssembly().GetManifestResourceStream("Cove.art."+name+".jpg")??throw new InvalidDataException("missing_embedded_art");buffer=new EncodedImageBuffer(source);url=buffer.GenerateUrl();}
 internal string Url=>url.ToString();public void Dispose(){url.Dispose();buffer.Dispose();source.Dispose();}
}
internal sealed record ScreenState(PortState[] Ports,DeviceSnapshot? Picture,int CompletedId,bool Verified,string? CompletedAction=null,string? Status=null,int? CurrentSource=null,bool PicturePending=false,long Generation=0,bool SourceRequestAccepted=false);
// Pure native NUI: native surfaces and compact pre-rendered device illustrations. No web engine, HTML,
// JavaScript, URLs from the page, profile, cookie store, install or Home hook.
internal sealed partial class NeutralWindow:NUIApplication {
 partial void TestCreated();partial void TestTick();partial void TestRead(DeviceSnapshot? picture);partial void TestStopping();
 static readonly bool ControlsEnabled=true;
 readonly Dictionary<string,NativeArt> art=new(StringComparer.Ordinal);readonly Dictionary<ImageView,string> assigned=new();
 readonly List<View> views=new(),cards=new(),dots=new(),utilityCards=new();readonly List<ImageView> icons=new(),presetIcons=new();readonly List<TextLabel> names=new(),portLabels=new(),utilityNames=new();
 readonly ForegroundSession foreground=new();readonly ConcurrentQueue<ScreenState> updates=new();readonly IDevice device;ControlAdapter? controls;
 readonly BrightnessProfiles? suppliedProfiles;
 readonly InputHandoffSession inputHandoff=new();string? inputBrightnessNotice;int inputSelectionPending,inputReturnPreview;
 void CancelInputHandoff(){Volatile.Write(ref inputSelectionPending,0);inputHandoff.Cancel();}
 internal NeutralWindow(IDevice? device=null,BrightnessProfiles? profiles=null){this.device=device??new NativeDevice();suppliedProfiles=profiles;}
 ImageView? background,heroArt,settingsIcon;TextLabel? notice,heroName,heroCurrent;View? lastFocused,heroCurrentDot;
 Animation? heroFade;AlphaFunction? heroEase;long heroFadeUntil;string heroIdentity="";
 static Color Ink()=>new(.043f,.055f,.082f,1);
 static Color Paper()=>new(.945f,.941f,.925f,1);
 static Color Muted()=>new(.557f,.616f,.702f,1);
 static Color Surface()=>new(.075f,.106f,.149f,.60f);
 View? focusDecoration;readonly SettingsHandoff settingsHandoff=new();int previousInput,previousUtility;bool actionInFlight;long noticeUntil;string notification="";
 Tizen.NUI.Timer? tick;ScreenState state=new(Array.Empty<PortState>(),null,0,false);
 bool inventoryObserved,created,stopping,assetsReady,selectDown,hasState,inputFocusRequested;long inventoryGeneration=-1;int focusRow,selected,workerBusy,requestId,keys;long refreshed,picturePendingSince;
 Request? pending;string exitReason="";
 static long Now()=>Stopwatch.GetTimestamp()*1000/Stopwatch.Frequency;
 T Add<T>(T view)where T:View{Window.Default.Add(view);views.Add(view);return view;}
 TextLabel Label(string text,int x,int y,int w,int h,float size)=>new(){Text=text,Position2D=new Position2D(x,y),Size2D=new Size2D(w,h),PixelSize=size,FontFamily="SamsungOne",Ellipsis=true,MultiLine=false,ParentOrigin=ParentOrigin.TopLeft,PivotPoint=PivotPoint.TopLeft,PositionUsesPivotPoint=true,AccessibilityHidden=true,TextColor=Paper(),HorizontalAlignment=HorizontalAlignment.Center,VerticalAlignment=VerticalAlignment.Center};
 void Place(View view,int x,int y,int w,int h){view.Position2D=new Position2D(x,y);view.Size2D=new Size2D(w,h);}
 View SurfaceBox(int x,int y,int w,int h)=>new(){Position2D=new Position2D(x,y),Size2D=new Size2D(w,h),BackgroundColor=Surface(),CornerRadius=new Vector4(18,18,18,18)};
 string Asset(string name){if(!art.TryGetValue(name,out var value)){value=new NativeArt(name);art.Add(name,value);}return value.Url;}
 void Paint(ImageView image,string name){if(assigned.TryGetValue(image,out string? old)&&old==name)return;image.ResourceUrl=Asset(name);assigned[image]=name;}
 protected override void OnCreate(){
  base.OnCreate();Window.Default.Title="Cove";Window.Default.BackgroundColor=Ink();Window.Default.InterceptKeyEvent+=OnIntercept;Window.Default.SetAcceptFocus(true);
  var profiles=suppliedProfiles??new BrightnessProfiles(System.IO.Path.Combine(Tizen.Applications.Application.Current.DirectoryInfo.Data,"cove-brightness-profiles-v2.json"),legacyPath:System.IO.Path.Combine(Tizen.Applications.Application.Current.DirectoryInfo.Data,"cove-brightness-profiles-v1.json"));
  controls=new ControlAdapter(device,adjustableBrightness:true,profiles:profiles);QueueRefresh();
  focusDecoration=new View{Size2D=new Size2D(1,1),Opacity=0,AccessibilityHidden=true};FocusManager.Instance.FocusIndicator=focusDecoration;
  background=Add(new ImageView{Position2D=new Position2D(0,0),Size2D=new Size2D(1920,1080),AccessibilityHidden=true});Paint(background,"cove-cinematic-background");
  var title=Add(Label("Inputs",144,90,500,48,34));title.HorizontalAlignment=HorizontalAlignment.Begin;
  // SamsungOne resolves to One UI Sans APP on this TV: 92px needs a 123px line.
  // Keep the centre at y=464, with enough height to avoid whole-line ellipsis.
  heroName=Add(Label("",152,392,760,144,92));heroName.HorizontalAlignment=HorizontalAlignment.Begin;
  heroCurrent=Add(Label("Current input",168,540,320,28,19));heroCurrent.HorizontalAlignment=HorizontalAlignment.Begin;heroCurrent.TextColor=new Color(.753f,.816f,.773f,1);heroCurrent.Opacity=0;
  heroCurrentDot=Add(new View{Position2D=new Position2D(152,551),Size2D=new Size2D(6,6),CornerRadius=new Vector4(3,3,3,3),BackgroundColor=new Color(.753f,.816f,.773f,1),AccessibilityHidden=true,Opacity=0});
  heroArt=Add(new ImageView{Opacity=0,AccessibilityHidden=true});
  for(int i=0;i<4;i++){
   var card=Add(SurfaceBox(0,822,400,142));card.BorderlineWidth=1;card.BorderlineColor=new Color(.557f,.671f,.773f,.094f);card.CornerRadius=new Vector4(16,16,16,16);card.AccessibilityRole=Role.PushButton;card.AccessibilityHighlightable=true;cards.Add(card);
   icons.Add(Add(new ImageView{Opacity=0,AccessibilityHidden=true}));names.Add(Add(Label("",0,853,260,42,28)));portLabels.Add(Add(Label("",0,903,200,28,18)));
   dots.Add(Add(new View{Size2D=new Size2D(6,6),CornerRadius=new Vector4(3,3,3,3),BackgroundColor=new Color(.737f,.827f,.745f,1),AccessibilityHidden=true}));
  }
  var group=Add(SurfaceBox(1414,78,274,68));group.BackgroundColor=new Color(1,1,1,.024f);group.CornerRadius=new Vector4(17,17,17,17);group.BorderlineWidth=1;group.BorderlineColor=new Color(1,1,1,.039f);group.AccessibilityHidden=true;
  for(int i=0;i<3;i++){
   int x=i==0?1419:i==1?1551:1708,y=i==2?78:83,w=i==2?68:132,h=i==2?68:58;
   var tile=Add(SurfaceBox(x,y,w,h));tile.BackgroundColor=new Color(0,0,0,0);tile.CornerRadius=new Vector4(i==2?17:12,i==2?17:12,i==2?17:12,i==2?17:12);tile.Focusable=true;tile.AccessibilityRole=Role.PushButton;tile.AccessibilityHighlightable=true;tile.AccessibilityName=i==0?"Bright preset":i==1?"Dim preset":"TV settings";utilityCards.Add(tile);
   var label=Add(Label(i==0?"Bright":i==1?"Dim":"",x+56,y,w-60,h,18));label.HorizontalAlignment=HorizontalAlignment.Begin;utilityNames.Add(label);
  }
  for(int i=0;i<2;i++){var icon=Add(new ImageView{Position2D=new Position2D(i==0?1442:1574,101),Size2D=new Size2D(22,22),AccessibilityHidden=true});Paint(icon,i==0?"cove-day":"cove-night");presetIcons.Add(icon);}
  settingsIcon=Add(new ImageView{Position2D=new Position2D(1729,99),Size2D=new Size2D(26,26),AccessibilityHidden=true});Paint(settingsIcon,"cove-settings");
  notice=Add(Label("Reading HDMI inputs...",240,1016,1440,38,19));notice.TextColor=Muted();
  CreateBrightness();focusRow=1;selected=2;previousUtility=3;Draw();
  // The only repeating timer drains I/O and reclaims completed, bounded compositor animations.
  tick=new Tizen.NUI.Timer(100);tick.Tick+=(s,e)=>{if(!stopping&&foreground.Active)Tick();return !stopping&&foreground.Active;};tick.Start();created=true;TestCreated();
  Bootstrap.Emit(new{@event="window_created",automatic_exit=false,controls_enabled=ControlsEnabled,renderer="native_cinematic",web_engine=false});
 }
 void FocusSelected(){
  if(!inputFocusRequested||stopping||!foreground.Active)return;View target=brightnessEditor.IsOpen?(scopeFocused?scopeButtons[scopeChoice]:brightnessSlider!):focusRow==0&&state.Ports.Length>0?cards[Math.Clamp(selected,0,state.Ports.Length-1)]:utilityCards[Math.Clamp(selected,0,3)];
  if(ReferenceEquals(lastFocused,target))return;if(FocusManager.Instance.SetCurrentFocusView(target))lastFocused=target;
 }
 void CancelHeroFade(){
  var animation=heroFade;var easing=heroEase;heroFade=null;heroEase=null;
  if(animation!=null){try{animation.EndAction=Animation.EndActions.StopFinal;animation.Stop();animation.Clear();}catch{}finally{try{animation.Dispose();}catch{}}}
  if(easing!=null){try{easing.Dispose();}catch{}}
  if(heroArt!=null)heroArt.Opacity=state.Ports.Length>0?.93f:0;
 }
 void RefreshHero(PortState? port,bool animate){
  if(heroArt==null||heroName==null)return;
  string identity=port==null?"empty":port.Port+":"+port.Label;bool changed=identity!=heroIdentity;int icon=port==null?0:Presentation.Icon(port);
  if(changed){CancelHeroFade();heroIdentity=identity;}
  heroName.Text=port==null?(inventoryObserved?"No connected inputs":""):Presentation.Name(port);heroName.PixelSize=port==null?58:92;
  bool watching=port!=null&&state.Picture?.SourceTransition!=true&&port.Source==(state.Picture?.Source??state.CurrentSource);heroCurrent!.Opacity=watching?1:0;heroCurrentDot!.Opacity=watching?1:0;
  if(port==null){heroArt.Opacity=0;return;}
  int x=1168,y=264,w=400;if(icon==1){x=1160;y=256;w=416;}else if(icon==2||icon==4||icon==7){x=1198;y=294;w=340;}else if(icon==3){x=1226;y=322;w=284;}
  Place(heroArt,x,y,w,w);Paint(heroArt,"cove-cinematic-"+icon);heroArt.Opacity=.93f;
  if(changed&&animate){try{heroArt.Opacity=.84f;heroEase=new AlphaFunction();heroFade=new Animation(100){EndAction=Animation.EndActions.StopFinal};heroFade.AnimateTo(heroArt,"Opacity",.93f,heroEase);heroFade.Play();heroFadeUntil=Now()+140;}catch{CancelHeroFade();}}
 }
 void OpenTvSettings(){
  if(actionInFlight){Notify("Please wait for the current change.");return;}
  CancelHomeActivation();
  CancelInputHandoff();
  CancelHeroFade();
  try{
   settingsHandoff.Request();
   var request=new Tizen.Applications.AppControl{ApplicationId="org.tizen.menu",Operation="http://tizen.org/appcontrol/operation/default",LaunchMode=Tizen.Applications.AppControlLaunchMode.Single};
   Tizen.Applications.AppControl.SendLaunchRequest(request);
   Bootstrap.Emit(new{@event="settings_launch_requested",caller_kept_alive=true});
  }catch(Exception error){settingsHandoff.Cancel();Bootstrap.Emit(new{@event="settings_launch_failed",kind=error.GetType().Name});Notify("TV settings could not be opened. Use the remote Settings key.");}
 }
 void Notify(string text){notification=text;noticeUntil=Now()+4500;UpdateNotice();}
 void UpdateNotice(){if(notice==null)return;string text=actionInFlight&&!brightnessEditor.InFlight?"Working...":Now()<noticeUntil?notification:!inventoryObserved?"Reading HDMI inputs...":state.Ports.Length==0?"":state.Ports.Any(p=>!p.CanSelect)?"Checking input connections...":state.PicturePending?"Reading picture presets...":"";if(notice.Text!=text)notice.Text=text;}
 void Tick(){
  if(stopping||!foreground.Active)return;TestTick();if(stopping||!foreground.Active)return;
  if(returningToViewer){
   // Freeze the outgoing scene. In particular, a polling reply must not clear
   // the visible brightness caption while Back is returning to HDMI.
   while(foreground.TryTakeCurrent(updates,item=>item.Generation,out var reply)){
    if(reply.CompletedAction=="return_current"){CompleteViewerReturn(!reply.SourceRequestAccepted);return;}
   }
   if(pending!=null&&QueueAction(pending))pending=null;
   return;
  }
  if(brightnessEditor.Expire(Now())){Notify("Brightness response timed out. Further adjustments stopped.");DrawBrightness();FocusSelected();}
  if(foreground.TryTakeCurrent(updates,item=>item.Generation,out var fresh)){
   bool scopeCompletion=fresh.CompletedId>0&&fresh.CompletedAction=="picture_scope";
   bool brightnessCompletion=fresh.CompletedId>0&&fresh.CompletedAction=="brightness";
   bool brightnessOnly=brightnessCompletion&&fresh.Verified&&state.Picture!=null&&BrightnessPolicy.SameIdentity(state.Picture,fresh.Picture)&&state.Ports.SequenceEqual(fresh.Ports);
   bool redraw=!state.Ports.SequenceEqual(fresh.Ports)||!Presentation.SamePicture(state.Picture,fresh.Picture)||state.CurrentSource!=fresh.CurrentSource||state.PicturePending!=fresh.PicturePending||fresh.CompletedId>0;
   int input=focusRow==0?selected:previousInput;input=Presentation.KeepPort(state.Ports,fresh.Ports,input);state=fresh;
   if(state.CompletedId>0){actionInFlight=false;if(state.CompletedAction=="hdmi")Volatile.Write(ref inputSelectionPending,0);
    if(state.Verified&&(brightnessCompletion||state.CompletedAction=="appearance"))profileSavePending=true;
    if(scopeCompletion){if(!brightnessEditor.CompleteScope(new(state.Verified,state.Status??"scope_readback_unverified",state.Picture)))Notify(Presentation.Failure(state.Status));}
    else if(brightnessCompletion){if(!brightnessEditor.Complete(new(state.Verified,state.Status??"brightness_readback_unverified",state.Picture)))Notify(Presentation.Failure(state.Status));}
    else if(!state.Verified&&!(state.CompletedAction=="hdmi"&&state.SourceRequestAccepted))Notify(state.CompletedAction=="profiles_save"?"The brightness profile could not be saved.":Presentation.Failure(state.Status));
    if(state.Status=="profile_save_unavailable")Notify(Presentation.Failure(state.Status));
   }
   if(brightnessEditor.IsOpen&&!brightnessEditor.Observe(state.Picture)){Notify("Picture context changed. Brightness adjustment stopped.");redraw=true;brightnessOnly=false;}
   if(focusRow==0)selected=input;previousInput=input;inventoryObserved=true;
   if(!hasState&&state.Ports.Length>0){focusRow=0;int current=Array.FindIndex(state.Ports,p=>p.Source==(state.Picture?.Source??state.CurrentSource));selected=current>=0?current:0;hasState=true;}
   if(state.Ports.Length==0){focusRow=1;selected=2;}
   if(state.CompletedId>0&&state.SourceRequestAccepted&&state.CompletedAction=="hdmi"){
    // If Back is held, its release owns the return. Do not expose that release
    // to the viewer just because an earlier input request finished meanwhile.
    if(!backGesture.Busy)HideToViewer("hdmi_selected");return;
   }
   selected=Math.Clamp(selected,0,focusRow==0?Math.Max(0,state.Ports.Length-1):3);
   if(redraw){if(brightnessOnly){DrawBrightness();DrawProfileButtons();UpdateNotice();FocusSelected();}else Draw();}
  }
  if(!inputFocusRequested){inputFocusRequested=true;Window.Default.Raise();FocusSelected();Bootstrap.Emit(new{@event="window_focus_requested",accepts_focus=Window.Default.IsFocusAcceptable(),actor_focus_set=lastFocused!=null});}
  if(heroFade!=null&&Now()>=heroFadeUntil)CancelHeroFade();UpdateNotice();
  if(inventoryObserved&&!assetsReady&&background!.IsResourceReady()&&(state.Ports.Length==0||heroArt!.IsResourceReady()&&icons.Take(state.Ports.Length).All(i=>i.IsResourceReady()))&&settingsIcon!.IsResourceReady()&&presetIcons.All(i=>i.IsResourceReady())){assetsReady=true;Bootstrap.Emit(new{@event="assets_ready",renderer="native_cinematic",connected_ports=state.Ports.Length});}
  if(pending!=null&&QueueAction(pending))pending=null;
  PumpBrightness();
  if(state.PicturePending){if(picturePendingSince==0)picturePendingSince=Now();}else picturePendingSince=0;
  bool settlingPicture=state.PicturePending&&Now()-picturePendingSince<InputBrightnessSettling.Budget;
  if(pending==null&&!actionInFlight&&Now()-refreshed>=(settlingPicture?250:1500)&&Volatile.Read(ref workerBusy)==0)QueueRefresh();
 }
 void Draw(){
  if(heroName==null)return;int count=state.Ports.Length;if(count>4)throw new InvalidDataException("port_count_invalid");
  int? source=state.Picture?.Source??state.CurrentSource;int width=400,start=(1920-(width*count+20*Math.Max(0,count-1)))/2;
  for(int i=0;i<4;i++){
   bool visible=i<count;foreach(var v in new View[]{cards[i],icons[i],names[i],portLabels[i],dots[i]})v.Opacity=visible?1:0;cards[i].Focusable=visible;cards[i].AccessibilityHidden=!visible;if(!visible)continue;
   int x=start+i*(width+20);bool focused=focusRow==0&&selected==i;bool watching=state.Ports[i].Source==source;int y=focused?819:822;
   Place(cards[i],x,y,width,142);cards[i].BackgroundColor=focused?new Color(.149f,.208f,.290f,.85f):Surface();cards[i].BorderlineWidth=focused?2:1;cards[i].BorderlineColor=focused?new Color(.765f,.824f,.886f,1):new Color(.557f,.671f,.773f,.094f);
   cards[i].AccessibilityName=Presentation.Name(state.Ports[i])+", HDMI "+state.Ports[i].Port+(watching?", current input":"");cards[i].AccessibilityDescription=state.Ports[i].CanSelect?"Open this input":"Connection is being checked";
   int icon=Presentation.Icon(state.Ports[i]);Place(icons[i],x+(icon==1?22:25),y+(icon==1?33:36),icon==1?70:64,icon==1?70:64);Paint(icons[i],"cove-cinematic-"+icon);icons[i].Opacity=.88f;
   names[i].Text=Presentation.Name(state.Ports[i]);names[i].TextColor=Paper();names[i].HorizontalAlignment=HorizontalAlignment.Begin;Place(names[i],x+113,y+31,260,42);
   portLabels[i].Text="HDMI "+state.Ports[i].Port;portLabels[i].TextColor=Muted();portLabels[i].HorizontalAlignment=HorizontalAlignment.Begin;Place(portLabels[i],x+113,y+81,200,28);Place(dots[i],x+368,y+87,6,6);dots[i].Opacity=watching?1:0;
  }
  int heroIndex=focusRow==0?selected:Array.FindIndex(state.Ports,p=>p.Source==source);
  RefreshHero(count>0&&heroIndex>=0?state.Ports[Math.Clamp(heroIndex,0,count-1)]:null,created&&hasState);
  DrawProfileButtons();DrawBrightness();UpdateNotice();FocusSelected();
 }
 void DrawProfileButtons(){
  string? appearance=Presentation.AppearanceOf(state.Picture);
  for(int i=0;i<3;i++){
   bool focused=focusRow==1&&selected==i;bool available=i==2||Presentation.PresetAvailable(state.Picture,i==0?Appearance.Day:Appearance.Night);bool active=i==0&&appearance=="day"||i==1&&appearance=="night";
   utilityCards[i].BackgroundColor=active?new Color(.220f,.282f,.365f,.50f):new Color(0,0,0,0);utilityNames[i].TextColor=available?Paper():Muted();utilityNames[i].Opacity=available?1:.38f;
   utilityCards[i].AccessibilityDescription=i==2?"Open Samsung picture and sound settings":available?(active?"Selected":"Select saved brightness level"):"Brightness is unavailable for the current picture";
   if(i<2)presetIcons[i].Opacity=available?1:.38f;utilityCards[i].BorderlineWidth=focused?2:i==2?1:0;utilityCards[i].BorderlineColor=focused?new Color(.765f,.824f,.886f,1):new Color(1,1,1,.043f);
  }
 }
 void QueueRefresh(){
  if(stopping||returningToViewer||!foreground.Active||Interlocked.CompareExchange(ref workerBusy,1,0)!=0)return;
  refreshed=Now();var lease=foreground.Lease;var ports=state.Ports;
  Task.Run(()=>{try{ReadState(lease,0,false);}catch(Exception e){Bootstrap.Emit(new{@event="state_read_unavailable",kind=e.GetType().Name});updates.Enqueue(new(ports.Select(p=>p with{CanSelect=false}).ToArray(),null,0,false,PicturePending:true,Generation:lease.Generation));}finally{Volatile.Write(ref workerBusy,0);}});
 }
 void ReadState(ForegroundLease lease,int completed,bool verified,string? action=null,string? status=null){
  if(lease.Cancellation.IsCancellationRequested)return;
  var ports=controls!.RefreshSources().ToArray();int? currentSource=null;
  if(lease.Cancellation.IsCancellationRequested)return;
  if(inventoryGeneration!=lease.Generation){inventoryGeneration=lease.Generation;try{var source=controls!.ReadSourceContext();if(!source.SourceTransition)currentSource=source.Source;}catch{}
   updates.Enqueue(new(ports,null,0,false,CurrentSource:currentSource,PicturePending:true,Generation:lease.Generation));
  }
  if(lease.Cancellation.IsCancellationRequested)return;
  DeviceSnapshot? picture=null;try{picture=controls!.ReadPicture();}catch{}
  if(lease.Cancellation.IsCancellationRequested)return;TestRead(picture);
  // Only one worker exists. Old-session replies are rejected on the UI thread.
  while(updates.TryDequeue(out _)){}updates.Enqueue(new(ports,picture,completed,verified,action,status,picture?.Source??currentSource,PicturePending:picture==null||picture.SourceTransition,Generation:lease.Generation));
  Bootstrap.Emit(new{@event="state_updated",connected_ports=ports.Length,source=picture?.Source,mode=picture?.Mode,controls_enabled=ControlsEnabled});
 }
 bool QueueAction(Request request){
  if(stopping||!foreground.Active||!ControlsEnabled||Interlocked.CompareExchange(ref workerBusy,1,0)!=0)return false;settingsHandoff.Cancel();
  if(request.Action is "hdmi" or "return_current")CancelHomeActivation();
  if(request.Action is "appearance" or "brightness" or "picture_scope")CancelInputHandoff();
  var lease=foreground.Lease;var ports=state.Ports;
  var handoff=request.Action=="hdmi"?inputHandoff.Begin():null;
  if(handoff!=null)Volatile.Write(ref inputSelectionPending,1);
  Task.Run(()=>{bool followStarted=false;try{var result=controls!.Execute(request,lease.Cancellation);
    // Accepted destination is a first-frame artwork hint only. Fresh native
    // state still gates the current badge and every control after reopening.
    if(handoff!=null&&!handoff.IsCancellationRequested&&result.SourceRequestAccepted&&request.Port is int acceptedPort)Interlocked.Exchange(ref inputReturnPreview,acceptedPort+12);
    Bootstrap.Emit(new{@event="control_result",id=request.Id,action=request.Action,verified=result.Verified,status=result.Status,port=request.Port,source=result.State?.Source,mode=result.State?.Mode,brightness=result.State?.Brightness});
    if(!lease.Cancellation.IsCancellationRequested){
     if(request.Action is "appearance" or "brightness" or "picture_scope" or "return_current" or "hdmi")updates.Enqueue(new(ports,result.State,request.Id,result.Verified,request.Action,result.Status,result.State?.Source,PicturePending:result.State==null||result.State.SourceTransition,Generation:lease.Generation,SourceRequestAccepted:result.SourceRequestAccepted));else ReadState(lease,request.Id,result.Verified,request.Action,result.Status);
    }
    // connect_source can pause Cove before returning. Carry only this explicit
    // input request through that pause; never raise/redraw the hidden window.
    if(handoff!=null&&result.SourceRequestAccepted&&result.InputBrightness is InputBrightnessPlan plan){
     _=Task.Run(()=>{try{
      var followed=controls.FollowInputBrightness(plan,handoff.Token);
      Bootstrap.Emit(new{@event="input_brightness_completed",verified=followed.Verified,status=followed.Status,source=plan.Source});
      if(!followed.Verified&&!handoff.IsCancellationRequested&&followed.Status is not ("input_destination_changed" or "input_profile_changed"))Interlocked.Exchange(ref inputBrightnessNotice,"Brightness could not follow this input. Select Bright or Dim.");
     }finally{inputHandoff.End(handoff);}});followStarted=true;
    }
   }catch(Exception e){Bootstrap.Emit(new{@event="control_exception",kind=e.GetType().Name});updates.Enqueue(new(ports,null,request.Id,false,request.Action,"device_operation_unverified",Generation:lease.Generation));}finally{if(handoff!=null&&!followStarted)inputHandoff.End(handoff);Volatile.Write(ref workerBusy,0);}});return true;
 }
 bool OnIntercept(object sender,Window.KeyEventArgs args){
  string key=args.Key?.KeyPressedName??"";OnKey(sender,args);
  return key=="Return"||key=="KP_Enter"||key=="Enter"||key=="Left"||key=="ArrowLeft"||key=="Right"||key=="ArrowRight"||key=="Up"||key=="ArrowUp"||key=="Down"||key=="ArrowDown"||key=="XF86Back"||key=="Back"||key=="Escape"||key=="XF86Exit";
 }
 void OnKey(object? sender,Window.KeyEventArgs args){
  if(args.Key==null||stopping||returningToViewer||!foreground.Active)return;string key=args.Key.KeyPressedName??"";bool select=key=="Return"||key=="KP_Enter"||key=="Enter";
  if(IsBackKey(key)){HandleBackEvent(key,args.Key.State);return;}
  if(args.Key.State==Key.StateType.Up){if(select)selectDown=false;return;}if(args.Key.State!=Key.StateType.Down)return;
  if(backGesture.Busy)return;
  if(++keys<=8)Bootstrap.Emit(new{@event="key_observed",key=key.Length<=64?key:"name_too_long"});
  if(select){if(selectDown)return;selectDown=true;}
  if(HandleBrightnessKey(key,select,false))return;
  if(key=="Up"||key=="ArrowUp"){if(focusRow==0){previousInput=selected;focusRow=1;selected=Math.Clamp(previousUtility,0,3);}}
  else if(key=="Down"||key=="ArrowDown"){if(focusRow==1&&state.Ports.Length>0){previousUtility=selected;focusRow=0;selected=Math.Clamp(previousInput,0,state.Ports.Length-1);}}
  else if(key=="Left"||key=="ArrowLeft")selected=focusRow==1?MoveUtility(-1):Math.Max(0,selected-1);
  else if(key=="Right"||key=="ArrowRight")selected=focusRow==1?MoveUtility(1):Math.Min(Math.Max(0,state.Ports.Length-1),selected+1);
  else if(select){
   CancelHomeActivation();
   if(focusRow==1&&selected==2){OpenTvSettings();return;}
   if(focusRow==1&&selected==3){OpenBrightness();return;}
   if(!ControlsEnabled){notice!.Text="This control is unavailable.";return;}
   if(pending!=null||actionInFlight){Notify("Please wait for the current change.");return;}if(requestId==int.MaxValue){Notify("Please close and reopen the launcher.");return;}
   if(focusRow==0&&selected<state.Ports.Length){if(!state.Ports[selected].CanSelect){Notify("That input is being checked. Please try again.");return;}pending=new(++requestId,"hdmi",state.Ports[selected].Port,null);}
   else if(focusRow==1){var mode=selected==0?Appearance.Day:Appearance.Night;if(!Presentation.PresetAvailable(state.Picture,mode)){Notify("Unavailable for this input.");return;}pending=new(++requestId,"appearance",null,mode,new BrightnessChange(state.Picture!,mode==Appearance.Day?state.Picture!.DayBrightness:state.Picture!.NightBrightness));}if(pending!=null){actionInFlight=true;if(QueueAction(pending))pending=null;}
  }
  Draw();
 }
 internal static int RunDisplay(string[] args){var elapsed=Stopwatch.StartNew();using var app=new NeutralWindow();app.Run(args);bool complete=Presentation.CompletedDisplay(app.created,app.stopping,app.assetsReady,app.exitReason);Bootstrap.Emit(new{@event="complete",status=complete?"ok":"unverified",window_created=app.created,assets_ready=app.assetsReady,exit_reason=app.exitReason,elapsed_ms=elapsed.ElapsedMilliseconds});return complete?0:3;}
}
