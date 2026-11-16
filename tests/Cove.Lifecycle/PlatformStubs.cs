// Only the platform boundary is simulated. Tests compile the real window,
// lifecycle, key dispatch, async worker, presentation and control code.
using System;
using System.Collections.Generic;
using System.IO;
namespace Tizen.Applications {
 public class Application {public static Application Current {get;}=new();public AppDirectory DirectoryInfo {get;}=new();}
 public class AppDirectory {public string Data=>throw new InvalidOperationException("Host tests must inject an in-memory profile store");}
 public class LowMemoryEventArgs:EventArgs{}
 public class AppControlReceivedEventArgs:EventArgs {public ReceivedAppControl ReceivedAppControl {get;set;}=new();}
 public enum AppControlLaunchMode {Single}
 public class AppControl {
  public string? ApplicationId {get;set;} public string? Operation {get;set;} public AppControlLaunchMode LaunchMode {get;set;}
  public ExtraDataCollection ExtraData {get;}=new();
  public class ExtraDataCollection {
   readonly Dictionary<string,string> values=new();
   public void Add(string key,string value)=>values[key]=value;
   public bool TryGet(string key,out string value)=>values.TryGetValue(key,out value!);
  }
  public static readonly List<string?> Launches=new();public static AppControl? LastRequest;
  public static void SendLaunchRequest(AppControl request){LastRequest=request;Launches.Add(request.ApplicationId);}
 }
 public class ReceivedAppControl:AppControl {public string? CallerApplicationId{get;set;}}
}
namespace Tizen.NUI {
 public class NUIApplication:IDisposable {
  public bool Exited{get;private set;}
  protected virtual void OnCreate(){} protected virtual void OnPause(){} protected virtual void OnResume(){}
  protected virtual void OnAppControlReceived(Tizen.Applications.AppControlReceivedEventArgs e){}
  protected virtual void OnLowMemory(Tizen.Applications.LowMemoryEventArgs e){} protected virtual void OnTerminate(){}
  public void Run(string[] args)=>OnCreate(); public void Exit()=>Exited=true; public void Dispose()=>OnTerminate();
 }
 public class Window {
  public static Window Default {get;private set;}=new();
  public static void Reset(){Default=new();Timer.Reset();Tizen.Applications.AppControl.Launches.Clear();}
  public string? Title{get;set;} public Color? BackgroundColor{get;set;} public bool Visible=true,Minimized;public int Raises,Shows,Hides,Activations,IgnoredActivations;public Action? BeforeShow,AfterActivate;
  public event Func<object,KeyEventArgs,bool>? InterceptKeyEvent;
  public class KeyEventArgs:EventArgs {public Key? Key{get;set;}}
  public bool SendKey(string name,Key.StateType state)=>InterceptKeyEvent?.Invoke(this,new(){Key=new(){KeyPressedName=name,State=state}})??false;
  public void SetAcceptFocus(bool v){} public bool IsFocusAcceptable()=>true;
  public void Add(BaseComponents.View v){} public void Hide(){Visible=false;Hides++;}public void Show(){BeforeShow?.Invoke();Visible=!Minimized;Shows++;}public void Raise(){Visible=!Minimized;Raises++;}public void Activate(){Activations++;Raises++;if(IgnoredActivations>0){IgnoredActivations--;return;}Minimized=false;Visible=true;AfterActivate?.Invoke();}
 }
 public class Key {public enum StateType{Down,Up} public string KeyPressedName{get;set;}=""; public StateType State{get;set;}}
 public class Color{public Color(float r,float g,float b,float a){}}
 public class Vector4{public Vector4(float a,float b,float c,float d){}}
 public class Position2D{public Position2D(int x,int y){}}
 public class Size2D{public Size2D(int w,int h){}}
 public enum ParentOrigin{TopLeft} public enum PivotPoint{TopLeft} public enum Role{PushButton,Slider}
 public enum HorizontalAlignment{Begin,Center,End}public enum VerticalAlignment{Center}
 public class FocusManager {
  public static FocusManager Instance{get;}=new();public BaseComponents.View? FocusIndicator{get;set;}
  public bool SetCurrentFocusView(BaseComponents.View view)=>true;public void ClearFocus(){}
 }
 public class Timer:IDisposable {
  static readonly List<Timer> all=new(); public bool Running;bool dispatching;public static int DisposalsDuringCallback;public event Func<object,EventArgs,bool>? Tick;
  public Timer(uint interval){all.Add(this);}public void Start()=>Running=true;public void Stop()=>Running=false;
  public void Dispose(){if(dispatching)DisposalsDuringCallback++;Running=false;all.Remove(this);}public static void Reset(){all.Clear();DisposalsDuringCallback=0;}
  public static void Pump(){foreach(var timer in all.ToArray())if(timer.Running){timer.dispatching=true;try{if(timer.Tick?.Invoke(timer,EventArgs.Empty)!=true)timer.Running=false;}finally{timer.dispatching=false;}}}
 }
 public class AlphaFunction:IDisposable {public void Dispose(){}}
 public class Animation:IDisposable {
  public enum EndActions{StopFinal}public EndActions EndAction{get;set;}public Animation(int ms){}
  public void AnimateTo(BaseComponents.View v,string p,float value,AlphaFunction f){} public void Play(){}public void Stop(){}public void Clear(){}public void Dispose(){}
 }
 public class EncodedImageBuffer:IDisposable {public EncodedImageBuffer(Stream s){}public ImageUrl GenerateUrl()=>new();public void Dispose(){}}
 public class ImageUrl:IDisposable {public override string ToString()=>"memory-art";public void Dispose(){}}
}
namespace Tizen.NUI.BaseComponents {
 public class View:IDisposable {
  public Tizen.NUI.Position2D? Position2D{get;set;}public Tizen.NUI.Size2D? Size2D{get;set;}
  public Tizen.NUI.Color? BackgroundColor{get;set;}public Tizen.NUI.Vector4? CornerRadius{get;set;}public float BorderlineWidth{get;set;}public Tizen.NUI.Color? BorderlineColor{get;set;}
  public bool AccessibilityHidden{get;set;}public bool AccessibilityHighlightable{get;set;}public Tizen.NUI.Role AccessibilityRole{get;set;}public string? AccessibilityName{get;set;}public string? AccessibilityDescription{get;set;}
  public float Opacity{get;set;}public bool Focusable{get;set;}public void Dispose(){}
 }
 public class ImageView:View {public string? ResourceUrl{get;set;}public bool IsResourceReady()=>true;}
 public class TextLabel:View {
  public string Text{get;set;}="";public float PixelSize{get;set;}public string? FontFamily{get;set;}public bool Ellipsis{get;set;}public bool MultiLine{get;set;}
  public Tizen.NUI.ParentOrigin ParentOrigin{get;set;}public Tizen.NUI.PivotPoint PivotPoint{get;set;}public bool PositionUsesPivotPoint{get;set;}
  public Tizen.NUI.Color? TextColor{get;set;}public Tizen.NUI.HorizontalAlignment HorizontalAlignment{get;set;}public Tizen.NUI.VerticalAlignment VerticalAlignment{get;set;}
 }
}
internal static class Bootstrap {
 internal static bool ExactFirmwareValidated=true;
 internal static readonly System.Collections.Concurrent.ConcurrentQueue<string> Events=new();
 internal static void Emit(object value)=>Events.Enqueue(System.Text.Json.JsonSerializer.Serialize(value));
}
