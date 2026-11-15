using System;
using System.Collections.Generic;
using Cove.Launcher;

internal static class PresentationChecks {
 static int count;
 static void Check(bool ok){if(!ok)throw new Exception("Presentation check "+count);count++;}
 static PortState Port(int number,string name)=>new(number,number+12,name,true,true);
 static DeviceSnapshot Picture(int source=13,string mode="655361",int brightness=50,bool changing=false)=>new(source,mode,brightness,new HashSet<string>{"655361","393217"},0,changing,PictureScope.CurrentSource,true,true);
 static void Main(){
  BackChecks.Run(Check);
  var apple=Port(4,"Apple TV 4K");var ps5=Port(1,"PlayStation 5");var other=Port(2,"Blu-ray");
  Check(Presentation.Icon(apple)==1);Check(Presentation.Icon(ps5)==2);Check(Presentation.Icon(Port(1,"Nintendo Switch"))==3);Check(Presentation.Icon(other)==6);Check(Presentation.Name(Port(2," "))=="HDMI 2");
  Check(Presentation.Icon(Port(3,"HDMI 3"))==0);Check(Presentation.Icon(Port(4,"Unknown device"))==0);
  Check(Presentation.Icon(Port(1,"Xbox"))==4);Check(Presentation.Icon(Port(1,"Gaming PC"))==5);
  Check(Presentation.Icon(Port(1,"Laptop"))==5);Check(Presentation.Icon(Port(1,"DVD player"))==6);
  Check(Presentation.Icon(Port(1,"PlayStation 4"))==7);Check(Presentation.Icon(Port(1,"Nintendo Wii"))==7);
  Check(Presentation.Icon(Port(1,"PlayStation"))==7);Check(Presentation.Icon(Port(1,"Living room PS5"))==2);
  Check(Presentation.Icon(Port(1,"HDMI switch"))==0);Check(Presentation.Icon(Port(1,"Switch splitter"))==0);
  foreach(string name in new[]{"Switch","Switch OLED","Switch Lite","Switch 2","Nintendo Switch","NintendoSwitch","Nintendo Switch OLED"})Check(Presentation.Icon(Port(4,name))==3);
  Check(Presentation.Icon(Port(4,"Nintendo Wii"))==7);Check(Presentation.Icon(Port(4,"Nintendo Switcher"))==7);
  Check(Presentation.KeepPort(new[]{ps5,other,apple},new[]{other,apple},2)==1);
  Check(Presentation.KeepPort(new[]{ps5,other,apple},new[]{ps5,apple},1)==1);
  Check(Presentation.KeepPort(new[]{apple},Array.Empty<PortState>(),0)==0);
  Check(Presentation.AppearanceOf(Picture() with{ProfileSelected=Appearance.Day})=="day");
  Check(Presentation.AppearanceOf(Picture() with{ProfileSelected=Appearance.Night})=="night");
  Check(Presentation.AppearanceOf(Picture())==null);
  Check(Presentation.PresetAvailable(Picture(source:14,mode:"393225"),Appearance.Night));
  Check(Presentation.PresetAvailable(Picture(brightness:49),Appearance.Night));
  Check(!Presentation.PresetAvailable(Picture(brightness:51),Appearance.Night));
  Check(!Presentation.PresetAvailable(Picture(changing:true),Appearance.Day));
  Check(!Presentation.PresetAvailable(Picture() with{BrightnessAvailable=false},Appearance.Day));
  Check(Presentation.SamePicture(Picture(),Picture() with{ObservedAt=999}));
  Check(!Presentation.SamePicture(Picture(),Picture(source:14)));
  Check(!Presentation.SamePicture(Picture(),Picture(mode:"393217",brightness:0)));
  Check(!Presentation.SamePicture(Picture(),Picture(changing:true)));
  Check(!Presentation.SamePicture(Picture(),Picture() with{AvailableModes=new HashSet<string>()}));
  Check(!Presentation.SamePicture(Picture(),Picture() with{Scope=PictureScope.Unknown}));
  Check(!Presentation.SamePicture(Picture() with{Scope=PictureScope.CurrentSource},Picture() with{Scope=PictureScope.AllSources}));
  Check(!Presentation.SamePicture(Picture(),null));Check(Presentation.SamePicture(null,null));
  Check(Presentation.CompletedDisplay(true,true,false,"remote_exit"));Check(Presentation.CompletedDisplay(true,true,false,"hdmi_selected"));
  Check(!Presentation.CompletedDisplay(false,true,false,"remote_exit"));Check(!Presentation.CompletedDisplay(true,false,true,""));
  Check(!Presentation.CompletedDisplay(true,true,false,"paused"));Check(Presentation.CompletedDisplay(true,true,true,"paused"));
  Check(Presentation.CompletedDisplay(true,true,false,"background_memory_pressure"));
  Check(Presentation.CompletedDisplay(true,true,false,"system_termination"));
  // A late HDMI success from before Back must not dismiss a new Home session;
  // a late picture reply must not re-enable stale controls after an input change.
  using(var session=new ForegroundSession()){
   var initial=session.Lease;Check(session.Accepts(initial.Generation));Check(!session.Resume());
   Check(session.Pause());Check(initial.Cancellation.IsCancellationRequested);
   Check(!session.Active&&!session.Accepts(initial.Generation));Check(!session.Pause());
   Check(session.Resume());var reopened=session.Lease;
   Check(!session.Accepts(initial.Generation));Check(session.Accepts(reopened.Generation));
   Check(!reopened.Cancellation.IsCancellationRequested);Check(!session.Resume());
   var replies=new System.Collections.Concurrent.ConcurrentQueue<(long Generation,string Result)>();
   Check(!session.TryTakeCurrent(replies,r=>r.Generation,out _));
   // A cancelled worker can finish after an empty-queue observation or after
   // the next Home press. Inspect the dequeued item, not a prior queue head.
   replies.Enqueue((initial.Generation,"old_hdmi_success"));
   Check(!session.TryTakeCurrent(replies,r=>r.Generation,out _));
   replies.Enqueue((initial.Generation,"old_brightness_failure"));
   replies.Enqueue((reopened.Generation,"fresh_inventory"));
   replies.Enqueue((initial.Generation,"late_old_picture"));
   Check(session.TryTakeCurrent(replies,r=>r.Generation,out var reply)&&reply.Result=="fresh_inventory");
   Check(!session.TryTakeCurrent(replies,r=>r.Generation,out _));
   replies.Enqueue((reopened.Generation,"reply_after_pause"));
   Check(session.Pause());Check(!session.TryTakeCurrent(replies,r=>r.Generation,out _));Check(session.Resume());
   // Repeated Home/Back and Settings pauses do not accumulate active leases.
   for(int i=0;i<200;i++){
    var old=session.Lease;Check(session.Pause());Check(old.Cancellation.IsCancellationRequested);
    Check(session.Resume());Check(!session.Accepts(old.Generation));Check(session.Accepts(session.Lease.Generation));
   }
  }
  // Unsolicited resumes during HDMI handoff cannot revive or redraw Cove.
  var viewer=new ViewerReturn();Check(viewer.AllowsResume(false));
  Check(viewer.Begin());Check(!viewer.Begin());Check(viewer.AwaitingHome);
  for(int n=0;n<10;n++)Check(!viewer.AllowsResume(false));
  Check(viewer.AllowsResume(true));viewer.Home();Check(!viewer.AwaitingHome);Check(viewer.AllowsResume(false));
  using(var session=new ForegroundSession()){
   var inFlight=session.Lease;viewer.Begin();
   // Home during an in-flight return cancels the old generation first.
   session.Pause();viewer.Home();session.Resume();
   Check(inFlight.Cancellation.IsCancellationRequested);Check(!session.Accepts(inFlight.Generation));
   Check(viewer.AllowsResume(true));Check(viewer.AllowsResume(false));
  }
  Console.WriteLine(System.Text.Json.JsonSerializer.Serialize(new{checks=count,passed=true,tv_contacted=false,native_executed=false}));
 }
}
